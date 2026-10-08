"""Composition root: ``python -m decider`` starts the service on the ``/data`` volume (T2.6)."""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import sys
from pathlib import Path

import uvicorn
from huggingface_hub import snapshot_download

from decider import tasks
from decider.backend.fake import FakeBackend
from decider.core import Decider
from decider.http import create_app
from decider.runner import ThreadRunner

DATA = Path(os.environ.get("DECIDER_DATA", "/data"))
REPO = "convaiinnovations/laya-multilingual"
REVISION = "1720e3e3357cfe1e281542e223f8273b0890ca34"
SHA256 = "9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204"
FILES = ["rl_agent_config.json", "model.safetensors", "tokenizer/*", "encoder/*"]
PREDOWNLOAD = (
    f"hf download {REPO} --revision {REVISION} --cache-dir <volume>/hf-cache"
)


class StartupError(Exception):
    pass


def api_key() -> str:
    key = os.environ.get("DECIDER_API_KEY")
    if key:
        return key
    path = DATA / "api_key"
    if path.exists():
        return path.read_text().strip()
    key = secrets.token_urlsafe(32)
    path.write_text(key + "\n")
    path.chmod(0o600)
    print(f"Generated API key (shown once, stored in {path}): {key}", flush=True)
    return key


def ensure_checkpoint(cache_dir: Path) -> Path:
    snapshot = cache_dir / f"models--{REPO.replace('/', '--')}" / "snapshots" / REVISION
    weights = snapshot / "model.safetensors"
    if not weights.exists():
        print(f"Downloading base checkpoint {REPO}@{REVISION} into {cache_dir} ...", flush=True)
        try:
            snapshot_download(REPO, revision=REVISION, cache_dir=cache_dir, allow_patterns=FILES)
        except Exception as e:
            raise StartupError(
                f"base checkpoint {REPO} at revision {REVISION} is missing from {cache_dir} "
                f"and could not be downloaded ({type(e).__name__}). On a host without network, "
                f"pre-download it into the volume: {PREDOWNLOAD}"
            ) from e
    h = hashlib.sha256()
    with weights.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    if h.hexdigest() != SHA256:
        raise StartupError(
            f"checksum mismatch for {weights}: sha256 {h.hexdigest()}, expected {SHA256}. "
            f"Delete {cache_dir} and start again to re-download."
        )
    return snapshot


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        specs = tasks.load(os.environ.get("DECIDER_TASKS", DATA / "tasks.yaml"))
        key = api_key()
        ensure_checkpoint(DATA / "hf-cache")
        decider = Decider(
            specs,
            backend=FakeBackend(),  # T2.7 swaps in LayaBackend
            db_path=DATA / "decider.db",
            model_dir=DATA / "models",
            runner=ThreadRunner(),
        )
    except (tasks.ConfigError, StartupError) as e:
        print(f"decider-ai cannot start: {e}", file=sys.stderr, flush=True)
        sys.exit(1)
    app = create_app(decider, key)
    uvicorn.run(app, host="0.0.0.0", port=8080, workers=1, access_log=False)


if __name__ == "__main__":
    main()
