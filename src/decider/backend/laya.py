"""The real ``Backend``: the Apache-2.0 ``laya`` SDK on CPU.

A task is one Laya ``choice`` question: the task's question as instructions and its
labels (with their one-line descriptions) as options. Training is ``laya.train.finetune``
(fp32, gradient checkpointing, the SDK's default learning rates and its built-in 10%
calibration holdout); each trained version is one checkpoint in the SDK's layout.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Sequence

import torch
from huggingface_hub import snapshot_download
from laya import Agent
from laya import train as laya_train
from laya.common import build_head, encode_text, render_options, state_room

from decider.backend import BASE, ModelRef
from decider.tasks import ConfigError, TaskSpec

REPO = "convaiinnovations/laya-multilingual"
REVISION = "1720e3e3357cfe1e281542e223f8273b0890ca34"  # Apache-2.0 (model card)
_FILES = ["rl_agent_config.json", "model.safetensors", "tokenizer/*", "encoder/*"]


class LayaBackend:
    def __init__(
        self,
        cache_dir: str | Path | None = None,
        threads: int | None = None,
        revision: str = REVISION,
        epochs: int | None = None,  # None: 12 below 300 examples, else 4
    ) -> None:
        self.cache_dir = cache_dir
        self.revision = revision
        self.threads = threads or max(1, (os.cpu_count() or 2) // 2)
        self.epochs = epochs
        torch.set_num_threads(self.threads)  # process-wide
        self._base_dir: Path | None = None
        self._agents: dict[Path, Agent] = {}
        self._checked: set[tuple] = set()

    # -- loading ---------------------------------------------------------------------

    def base_dir(self) -> Path:
        if self._base_dir is None:
            self._base_dir = Path(
                snapshot_download(
                    REPO, revision=self.revision, cache_dir=self.cache_dir, allow_patterns=_FILES
                )
            )
        return self._base_dir

    def _dir(self, model: ModelRef) -> Path:
        return self.base_dir() if model.path is None else Path(model.path)

    def _agent(self, model: ModelRef) -> Agent:
        path = self._dir(model)
        if path not in self._agents:
            self._agents[path] = Agent(str(path), device="cpu")
        return self._agents[path]

    # -- encoding --------------------------------------------------------------------

    @staticmethod
    def _question(task: TaskSpec) -> dict[str, Any]:
        return {"type": "choice", "instructions": task.question, "criteria": dict(task.labels)}

    def count_tokens(self, text: str) -> int:
        """Tokens of ``text`` as the SDK encodes a state (mask token replaced)."""
        tok = self._agent(BASE).tok
        return len(encode_text(tok, text.replace(tok.mask_token, " "), add_special_tokens=False)["input_ids"])

    def head_tokens(self, task: TaskSpec) -> int:
        """Tokens of question + options before any SDK cut (the SDK's head budget counts these)."""
        tok = self._agent(BASE).tok
        q = laya_train.to_internal(task.name, self._question(task))

        def n(text: str) -> int:
            return len(encode_text(tok, text.replace(tok.mask_token, " "), add_special_tokens=False)["input_ids"])

        return n("%s question: %s" % (q["t"], q["ins"])) + sum(1 + n(" " + o) for o in render_options(q))

    def check_task(self, task: TaskSpec) -> None:
        """Raise ``ConfigError`` if the SDK would cut the task's question or options."""
        key = (task.name, task.question, tuple(task.labels.items()))
        if key in self._checked:
            return
        agent = self._agent(BASE)
        budget = agent.cfg["head_max_len"]
        q = laya_train.to_internal(task.name, self._question(task))
        built = len(build_head(agent.tok, q, budget)[0]) - 3  # minus [CLS] and two [SEP]
        need = self.head_tokens(task)
        if built != need:
            raise ConfigError(
                f"task '{task.name}': question and label descriptions need {need} tokens, "
                f"the model allows {budget} (each description at most 48); shorten or drop the label descriptions (fine-tuned tasks work with label names only)"
            )
        self._checked.add(key)

    def max_input(self, task: TaskSpec) -> int:
        """Exact state room the SDK leaves for a text after the task's question and options."""
        self.check_task(task)
        agent = self._agent(BASE)
        q = laya_train.to_internal(task.name, self._question(task))
        return state_room(agent.tok, q, agent.cfg["max_len"], agent.cfg["head_max_len"])

    # -- Backend ---------------------------------------------------------------------

    def predict(self, model: ModelRef, task: TaskSpec, texts: list[str]) -> list[dict[str, float]]:
        self.check_task(task)
        # Callers (decider.core) reject over-long texts first via count_tokens/max_input;
        # anything longer that reaches here would be cut silently by the SDK.
        results = self._agent(model).predict_batch(
            texts, {task.name: self._question(task)}, batch_size=16
        )
        return [
            {label: float(r["answers"][task.name]["probabilities"][label]) for label in task.labels}
            for r in results
        ]

    def train(
        self,
        base: ModelRef,
        task: TaskSpec,
        examples: Sequence[Any],
        seed: int,
        out_dir: Path,
        progress: Callable[[float], None],
    ) -> ModelRef:
        self.check_task(task)
        epochs = self.epochs or (12 if len(examples) < 300 else 4)
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        question = {task.name: self._question(task)}
        config = laya_train.TrainConfig(
            epochs=epochs, seed=seed, amp=False, gradient_checkpointing=True
        )

        # Report progress per epoch; dropping the SDK's own epoch hook also skips its
        # per-epoch `checkpoint_latest` copy, so out_dir holds exactly one checkpoint.
        original = laya_train.train_model

        def train_model(*args: Any, **kwargs: Any) -> Any:
            kwargs["on_epoch_end"] = lambda epoch, _loss: progress((epoch + 1) / (epochs + 1))
            return original(*args, **kwargs)

        progress(0.0)
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "train.jsonl"
            with data.open("w", encoding="utf-8") as f:
                for ex in examples:
                    row = {"state": ex.text, "questions": question, "expected": {task.name: ex.label}}
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            laya_train.train_model = train_model
            try:
                laya_train.finetune(str(data), str(self._dir(base)), str(out_dir), config, device="cpu")
            finally:
                laya_train.train_model = original
        progress(1.0)
        return ModelRef(out_dir.name, out_dir)
