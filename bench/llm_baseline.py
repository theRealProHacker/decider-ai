"""Baseline (b): zero-shot Gemini predictions on a public test set (T1.3).

Lives outside src/decider on purpose: the product never calls an LLM.

    uv run --group bench python bench/llm_baseline.py \
        --records data/massive/test.jsonl --tasks bench/tasks/massive_de_scenario.yaml \
        --dataset massive_de_scenario --out predictions/ --limit 20

Reads GEMINI_API_KEY. Resumes: external_ids already in the output file are skipped.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Callable, NamedTuple

import yaml

SYSTEM = "gemini-3.5-flash-lite"
MODEL = "gemini-3.5-flash-lite"
TEMPERATURE = 0.0
THINKING_LEVEL = "MINIMAL"  # google-genai ThinkingConfig.thinking_level; lowest the model allows
# docs/briefs/0005-phase-0-report-scope.md section 1.1, standard synchronous tier.
PRICE_INPUT_PER_M_USD = 0.30
PRICE_OUTPUT_PER_M_USD = 2.50
PRICE_DATE = "2026-10-08"
# Zero-shot: no training labels. Written as budget 0 / seed 0 to fit the shared prediction format.
BUDGET = 0
SEED = 0

PROMPT_TEMPLATE = """Classify the message. Choose exactly one label from the list.

Question: {question}

Labels:
{labels}

Message:
{text}"""


class Reply(NamedTuple):
    text: str
    input_tokens: int
    output_tokens: int  # includes thinking tokens (billed as output)


# A client takes (prompt, allowed labels) and returns a Reply. Tests inject a stub.
Client = Callable[[str, list[str]], Reply]


def gemini_client() -> Client:
    from google import genai
    from google.genai import types

    api = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def call(prompt: str, labels: list[str]) -> Reply:
        resp = api.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=TEMPERATURE,
                thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVEL),
                response_mime_type="text/x.enum",
                response_schema={"type": "STRING", "enum": labels},
            ),
        )
        u = resp.usage_metadata
        return Reply(
            text=resp.text or "",
            input_tokens=u.prompt_token_count or 0,
            output_tokens=(u.candidates_token_count or 0) + (u.thoughts_token_count or 0),
        )

    return call


def build_prompt(task: dict, text: str) -> str:
    labels = "\n".join(f"- {name}: {desc}" for name, desc in task["labels"].items())
    return PROMPT_TEMPLATE.format(question=task["question"], labels=labels, text=text)


def load_task(path: Path, name: str | None) -> dict:
    tasks = yaml.safe_load(path.read_text())["tasks"]
    if name:
        return next(t for t in tasks if t["name"] == name)
    return next((t for t in tasks if t.get("zero_shot")), tasks[0])


def run(records_path, tasks_path, dataset, out_dir, limit=None, task_name=None, client=None) -> dict:
    task = load_task(Path(tasks_path), task_name)
    labels = list(task["labels"])
    records = [json.loads(line) for line in Path(records_path).read_text().splitlines() if line.strip()]
    records = [r for r in records if r.get("label_mode") == "blind"]  # official test partition
    if limit is not None:
        records = records[:limit]

    out = Path(out_dir) / dataset
    out.mkdir(parents=True, exist_ok=True)
    pred_path = out / f"{SYSTEM}.jsonl"
    meta_path = out / f"{SYSTEM}.meta.json"

    done = set()
    if pred_path.exists():
        done = {json.loads(line)["external_id"] for line in pred_path.read_text().splitlines() if line.strip()}

    meta = {
        "kind": "api",
        "system": SYSTEM,
        "task": task["name"],
        "model": MODEL,
        "settings": {"temperature": TEMPERATURE, "thinking_level": THINKING_LEVEL,
                     "output": "enum restricted to the task's labels", "shots": 0},
        "thinking_level": THINKING_LEVEL,
        "temperature": TEMPERATURE,
        "prompt_template_sha256": hashlib.sha256(PROMPT_TEMPLATE.encode()).hexdigest(),
        "price_input_per_million_usd": PRICE_INPUT_PER_M_USD,
        "price_output_per_million_usd": PRICE_OUTPUT_PER_M_USD,
        "price_date": PRICE_DATE,
        "run_date": dt.date.today().isoformat(),
        "training_seconds": {f"{BUDGET}/{SEED}": 0.0},
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")

    client = client or gemini_client()
    called = invalid = 0
    with pred_path.open("a") as f:
        for r in records:
            if r["external_id"] in done:
                continue
            start = time.perf_counter()
            reply = client(build_prompt(task, r["text"]), labels)
            latency_ms = (time.perf_counter() - start) * 1000
            label = reply.text.strip()
            if label not in labels:
                label = None
                invalid += 1
            f.write(json.dumps({
                "external_id": r["external_id"], "budget": BUDGET, "seed": SEED, "label": label,
                "latency_ms": round(latency_ms, 1),
                "input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens,
            }) + "\n")
            f.flush()
            called += 1

    summary = {"records": len(records), "skipped": len(records) - called, "called": called, "invalid": invalid}
    print(f"{dataset}: {summary['records']} records, {summary['skipped']} already done, "
          f"{called} called, {invalid} invalid -> {pred_path}")
    return summary


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--records", required=True, help="records JSONL (test records have label_mode=blind)")
    p.add_argument("--tasks", required=True, help="benchmark tasks.yaml")
    p.add_argument("--dataset", required=True)
    p.add_argument("--out", default="predictions/")
    p.add_argument("--limit", type=int)
    p.add_argument("--task", help="task name in tasks.yaml (default: first zero_shot task)")
    a = p.parse_args(argv)
    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY is not set", file=sys.stderr)
        return 2
    run(a.records, a.tasks, a.dataset, a.out, a.limit, a.task)
    return 0


if __name__ == "__main__":
    sys.exit(main())
