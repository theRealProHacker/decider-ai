"""HTTP adapter: maps routes onto ``Decider`` (issues/0010 Resolution). No logic of its own."""

from __future__ import annotations

import dataclasses
import hmac
import json
import os
from typing import Any, Literal

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from decider import sheets
from decider.core import Decider, DeciderError, Example, Frozen
from decider.sheets import XLSX

DEFAULT_MAX_BODY_BYTES = 16 * 1024 * 1024

STATUS = {
    "INPUT_TOO_LONG": 413,
    "PAYLOAD_TOO_LARGE": 413,
    "MODEL_NOT_TRAINED": 503,
    "BUSY": 409,
    "TOO_FEW_EXAMPLES": 422,
    "LABEL_NOT_IN_TASK": 422,
    "VALIDATION_FAILED": 422,
    "TASK_NOT_FOUND": 404,
    "NOT_FOUND": 404,
    "UNAUTHORIZED": 401,
    "ACTIVATION_FAILED": 500,
}


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int | None = None, **fields: Any) -> None:
        self.code, self.message, self.fields = code, message, fields
        self.status = status or STATUS.get(code, 500)


def error(code: str, message: str, status: int, headers: dict | None = None, **fields: Any):
    body = {"error": {"code": code, "message": message, **fields}}
    return JSONResponse(body, status_code=status, headers=headers)


class DecisionIn(BaseModel):
    task: str
    text: str
    external_id: str | None = None


class FeedbackIn(BaseModel):
    task: str
    text: str
    label: str
    external_id: str
    request_id: str | None = None
    group_id: str | None = None
    label_mode: Literal["blind", "assisted"] = "assisted"


class SheetIn(BaseModel):
    """Query parameters for a CSV or xlsx import: which task, and which columns hold what."""

    task: str
    text_column: str = "text"
    label_column: str = "label"
    id_column: str = "external_id"
    label_mode: Literal["blind", "assisted"] = "blind"


class RetrainIn(BaseModel):
    task: str
    refresh_split: bool = False


class BodyCap:
    """Rejects a body over ``limit`` bytes before anything parses it, counted on streamed bytes."""

    def __init__(self, app, limit: int) -> None:
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        too_large = error("PAYLOAD_TOO_LARGE", f"request body exceeds {self.limit} bytes", 413,
                          limit=self.limit)
        length = dict(scope["headers"]).get(b"content-length")
        if length is not None and length.isdigit() and int(length) > self.limit:
            return await too_large(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                break
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.limit:
                return await too_large(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body"):
                break
        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


def _outcome(o) -> dict:
    out = {"index": o.index, "outcome": o.kind}
    if o.reason:
        out["code"] = o.reason
    return out


def _example(fields: FeedbackIn) -> Example:
    return Example(**fields.model_dump())


def _sheet_examples(rows: list[dict[str, str]], q: SheetIn) -> list[dict]:
    columns = list(rows[0]) if rows else []
    missing = [c for c in (q.text_column, q.label_column) if c not in columns]
    if missing:
        raise ApiError("VALIDATION_FAILED", f"missing column(s): {', '.join(missing)}",
                       columns=columns)
    out = []
    for row in rows:
        text = row.get(q.text_column, "")
        external_id = sheets.external_id(row, q.id_column, text)
        out.append({"task": q.task, "text": text or None, "label": row.get(q.label_column, ""),
                    "external_id": external_id, "label_mode": q.label_mode})
    return out


def create_app(decider: Decider, api_key: str, max_body_bytes: int | None = None) -> FastAPI:
    if max_body_bytes is None:
        max_body_bytes = int(os.environ.get("DECIDER_MAX_BODY_BYTES", DEFAULT_MAX_BODY_BYTES))

    def auth(request: Request) -> None:
        scheme, _, key = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(key.encode(), api_key.encode()):
            raise ApiError("UNAUTHORIZED", "missing or wrong API key")

    app = FastAPI(title="decider-ai", openapi_url=None, docs_url=None, redoc_url=None)
    app.add_middleware(BodyCap, limit=max_body_bytes)
    v1 = APIRouter(dependencies=[Depends(auth)])

    @app.exception_handler(ApiError)
    async def _api_error(request, exc: ApiError):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status == 401 else None
        return error(exc.code, exc.message, exc.status, headers, **exc.fields)

    @app.exception_handler(DeciderError)
    async def _decider_error(request, exc: DeciderError):
        return error(exc.code, str(exc), STATUS.get(exc.code, 500), **vars(exc))

    @app.exception_handler(RequestValidationError)
    async def _validation(request, exc: RequestValidationError):
        problems = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        return error("VALIDATION_FAILED", "request validation failed", 422, problems=problems)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request, exc: StarletteHTTPException):
        code = "NOT_FOUND" if exc.status_code == 404 else f"HTTP_{exc.status_code}"
        return error(code, str(exc.detail), exc.status_code)

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @v1.get("/health/ready")
    def ready():
        tasks = {}
        for name, s in decider.status().items():
            d = dataclasses.asdict(s)
            d["split"]["state"] = "frozen" if isinstance(s.split, Frozen) else "pending"
            tasks[name] = d
        return {"tasks": tasks}

    @v1.get("/openapi.json", include_in_schema=False)
    def openapi():
        return app.openapi()

    @v1.post("/v1/decisions")
    def decisions(body: DecisionIn):
        return dataclasses.asdict(decider.decide(body.task, body.text, external_id=body.external_id))

    @v1.post("/v1/feedback")
    def feedback(body: FeedbackIn):
        [o] = decider.confirm([_example(body)])
        if o.kind == "rejected":
            fields = {}
            if o.reason == "LABEL_NOT_IN_TASK":
                fields["allowed"] = list(decider.tasks[body.task].labels)
            if o.reason == "TASK_NOT_FOUND":
                fields["task"] = body.task
            raise ApiError(o.reason or "VALIDATION_FAILED", f"feedback rejected: {o.reason}",
                           **fields)
        return {"outcome": o.kind}

    @v1.post("/v1/examples:batch")
    async def batch(request: Request):
        ctype = request.headers.get("content-type", "").split(";")[0].strip()
        body = await request.body()
        if ctype == "application/x-ndjson":
            items = [ln for ln in body.splitlines() if ln.strip()]
        elif ctype in ("text/csv", XLSX):
            try:
                q = SheetIn.model_validate(dict(request.query_params))
            except ValidationError as exc:
                raise ApiError("VALIDATION_FAILED", "CSV and xlsx imports need ?task=") from exc
            try:
                rows = sheets.read(body, xlsx=ctype == XLSX)
            except sheets.SheetError as exc:
                raise ApiError("VALIDATION_FAILED", str(exc)) from exc
            items = _sheet_examples(rows, q)
        else:
            raise ApiError("VALIDATION_FAILED",
                           f"Content-Type must be application/x-ndjson, text/csv or {XLSX}")
        examples: list[tuple[int, Example]] = []
        outcomes: list[dict | None] = [None] * len(items)
        for i, item in enumerate(items):
            try:
                fields = json.loads(item) if isinstance(item, bytes) else item
                examples.append((i, _example(FeedbackIn.model_validate(fields))))
            except (ValueError, ValidationError):
                outcomes[i] = {"index": i, "outcome": "rejected", "code": "VALIDATION_FAILED"}
        for (i, _), o in zip(examples, decider.confirm(e for _, e in examples)):
            outcomes[i] = _outcome(dataclasses.replace(o, index=i))
        return {"outcomes": outcomes}

    @v1.delete("/v1/examples/{external_id}")
    def forget(external_id: str):
        return dataclasses.asdict(decider.forget(external_id))

    @v1.post("/v1/retrain", status_code=202)
    def retrain(body: RetrainIn):
        return {"job_id": decider.retrain(body.task, refresh_split=body.refresh_split)}

    @v1.get("/v1/jobs/{job_id}")
    def job(job_id: str):
        return dataclasses.asdict(decider.job(job_id))

    @v1.get("/v1/tasks/{task}/models")
    def models(task: str):
        return {"models": [dataclasses.asdict(m) for m in decider.models(task)]}

    @v1.post("/v1/tasks/{task}/models/{version}/activate")
    def activate(task: str, version: str):
        return dataclasses.asdict(decider.activate(task, version))

    app.include_router(v1)
    return app
