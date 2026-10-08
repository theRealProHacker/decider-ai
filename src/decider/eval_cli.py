"""decider-eval: the Phase 0 benchmark report (T1.5).

    decider-eval --data-dir data --datasets massive_de_scenario,clinc_domain \\
        --tasks-dir bench/tasks --predictions predictions \\
        --budgets 50,100,250 --seeds 0-4 --backend laya \\
        --machine "<specs>" --cpu-eur-per-hour 0.0256 --fx 0.86,2026-10-08 --out reports/<run-id>

Per dataset it reads ``<data-dir>/<dataset>/records.jsonl`` (test = ``label_mode: blind``),
``<data-dir>/<dataset>/subsets/<budget>-<seed>.json``, ``<tasks-dir>/<dataset>.yaml`` and every
``<predictions>/<dataset>/<system>.jsonl`` (+ ``<system>.meta.json``) as a named system. It runs
(c) ``finetune`` via ``Backend.train`` + ``predict`` per (budget, seed) and (d) ``zero_shot`` via
``Backend.predict`` on the base model, then writes ``report.json`` and ``report.md`` (rendered from
the JSON alone). Aggregate numbers only: no message text is written or printed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import random
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from statistics import fmean
from typing import Any, Sequence

from decider import evaluation, tasks
from decider.backend import BASE
from decider.core import Example

SCHEMA_VERSION = 1
FINETUNE = "finetune"  # (c)
ZERO_SHOT = "zero_shot"  # (d)
GATE_BUDGET = 250
ZERO_SHOT_RULE = ("tfidf_lr", 50)
AMORTISE_DECISIONS = 30_000
TOKEN_SENSITIVITY = 0.30

DATASET_INFO = {
    "massive_de_scenario": {
        "dataset": "MASSIVE 1.1, locale de-DE, scenario level",
        "authors": "FitzGerald et al., Amazon (2022); derived from SLURP",
        "licence": "CC BY 4.0",
        "link": "https://github.com/alexa/massive",
        "pin": "amazon-massive-dataset-1.1.tar.gz (alexa/massive @ f966f21846043aabef9b0f974fa7970027f43738)",
        "sha256": {
            "amazon-massive-dataset-1.1.tar.gz": "4cba5faa11c71437928e17cb1b9b3d8b8e727e7ea363a3a9a8045e19c0491577",
            "1.1/data/de-DE.jsonl": "5e09cc550b38d37faf002e0ff42103acd330906e23032689e8f071e1cf3ff621",
        },
    },
    "clinc_domain": {
        "dataset": "CLINC150 oos_plus, domain level + out_of_scope",
        "authors": "Larson et al., EMNLP 2019",
        "licence": "CC BY 3.0",
        "link": "https://github.com/clinc/oos-eval",
        "pin": "clinc/oos-eval @ 828f8093932c8fe6ca7936c3d2e52903b1c523de",
        "sha256": {
            "data_oos_plus.json": "bfcca9ae515623541dc1983c94c4ed7cae9d26b42ae47d74b972e51bb6f7a21f",
            "domains.json": "b947b579d3b8e74b06f93b01083d8efaff2888b43a3e362533bd88a6e1211b3a",
        },
    },
}


class EvalError(SystemExit):
    """A user-facing failure; the message names the file and what is missing."""


# --- statistics --------------------------------------------------------------


def _counts_f1(tp: Counter, fp: Counter, fn: Counter) -> float:
    labels = {k for c in (tp, fp, fn) for k, v in c.items() if v}
    if not labels:
        return 0.0
    return fmean(2 * tp[k] / (2 * tp[k] + fp[k] + fn[k]) if tp[k] else 0.0 for k in labels)


def weighted_macro_f1(gold: Sequence[str], pred: Sequence[str | None], w: Sequence[int]) -> float:
    """Macro-F1 with integer item weights (a bootstrap resample). ``None`` = invalid: wrong, no class."""
    tp: Counter = Counter()
    fp: Counter = Counter()
    fn: Counter = Counter()
    for wi, g, p in zip(w, gold, pred):
        if not wi:
            continue
        if g == p:
            tp[g] += wi
        else:
            fn[g] += wi
            if p is not None:
                fp[p] += wi
    return _counts_f1(tp, fp, fn)


def paired_bootstrap(
    gold: Sequence[str],
    a_by_seed: Sequence[Sequence[str | None]],
    b_by_seed: Sequence[Sequence[str | None]],
    groups: Sequence[Any],
    resamples: int = 2000,
    seed: int = 0,
) -> evaluation.Comparison:
    """``evaluation.compare`` (same resampling stream and percentiles) with seeds averaged on
    both sides, computed from per-resample weights so it runs on 5,000-item test sets."""
    n = len(gold)
    members: dict[Any, list[int]] = {}
    for i, g in enumerate(groups):
        members.setdefault(g, []).append(i)
    keys = list(members)

    def delta(w: Sequence[int]) -> float:
        fa = fmean(weighted_macro_f1(gold, a, w) for a in a_by_seed)
        return fa - fmean(weighted_macro_f1(gold, b, w) for b in b_by_seed)

    rng = random.Random(seed)
    deltas = []
    for _ in range(resamples):
        w = [0] * n
        for k, c in Counter(rng.choices(keys, k=len(keys))).items():
            for i in members[k]:
                w[i] += c
        deltas.append(delta(w))
    deltas.sort()
    lo = deltas[int(0.025 * (resamples - 1))]
    hi = deltas[int(round(0.975 * (resamples - 1)))]
    return evaluation.Comparison(delta=delta([1] * n), ci_low=lo, ci_high=hi, n=n)


def p95(values: Sequence[float]) -> float:
    s = sorted(values)
    return s[max(0, math.ceil(0.95 * len(s)) - 1)]


# --- loading -----------------------------------------------------------------


def _read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _key(s: str) -> tuple[int, int]:
    b, sd = s.replace("/", "-").rsplit("-", 1)
    return int(b), int(sd)


def load_external(path: Path, test_ids: list[str], labels: set[str], budgets, seeds) -> dict:
    """One external system from ``<name>.jsonl`` (+ optional ``<name>.meta.json``)."""
    meta_path = path.with_name(path.stem + ".meta.json")
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    preds: dict[tuple[int, int], dict[str, dict]] = {}
    for line in _read_jsonl(path):
        preds.setdefault((int(line["budget"]), int(line["seed"])), {})[line["external_id"]] = line
    zero_shot = set(preds) == {(0, 0)}
    wanted = [(0, 0)] if zero_shot else [(b, s) for b in budgets for s in seeds]
    for b, s in wanted:
        if (b, s) not in preds:
            raise EvalError(f"{path}: no predictions for budget {b} seed {s}")
        missing = sum(1 for i in test_ids if i not in preds[(b, s)])
        if missing:
            raise EvalError(f"{path}: {missing} test records missing for budget {b} seed {s}")
    train = meta.get("train_seconds") or meta.get("training_seconds") or {}
    out = {"kind": meta.get("kind", "local"), "zero_shot": zero_shot, "meta": meta,
           "labels": {}, "latency": {}, "tokens": {}, "train_seconds": {_key(k): v for k, v in train.items()}}
    for key in wanted:
        rows = [preds[key][i] for i in test_ids]
        out["labels"][key] = [r["label"] if r["label"] in labels else None for r in rows]
        out["latency"][key] = [float(r["latency_ms"]) for r in rows]
        out["tokens"][key] = [(r.get("input_tokens") or 0, r.get("output_tokens") or 0) for r in rows]
    return out


def make_backend(name: str):
    if name == "fake":
        from decider.backend.fake import FakeBackend

        return FakeBackend()
    if name == "laya":
        from decider.backend.laya import LayaBackend  # lazy: heavy, not needed for tests

        return LayaBackend()
    raise EvalError(f"unknown backend '{name}' (use fake or laya)")


def _is_too_long(e: Exception) -> bool:
    return type(e).__name__ == "InputTooLong"


def _predict_one(backend, model, task, text: str) -> tuple[str | None, float]:
    t0 = time.perf_counter()
    try:
        scores = backend.predict(model, task, [text])[0]
        label = max(scores, key=scores.get)
    except Exception as e:  # over-length input counts as invalid (wrong), never truncated
        if not _is_too_long(e):
            raise
        label = None
    return label, (time.perf_counter() - t0) * 1000


def run_backend(backend, task, train_by_id: dict, test: list[dict], subsets: dict, budgets, seeds, log) -> tuple[dict, dict]:
    """Returns the (c) fine-tune and (d) zero-shot systems."""
    texts = [r["text"] for r in test]
    ft = {"kind": "local", "zero_shot": False, "meta": {}, "labels": {}, "latency": {}, "tokens": {}, "train_seconds": {}}
    for b in budgets:
        for s in seeds:
            examples = [
                Example(task=task.name, text=r["text"], label=r["label"], external_id=r["external_id"],
                        group_id=r.get("group_id"), label_mode="assisted")
                for r in (train_by_id[i] for i in subsets[(b, s)])
            ]
            with tempfile.TemporaryDirectory(prefix="decider-eval-") as tmp:
                t0 = time.perf_counter()
                model = backend.train(BASE, task, examples, s, Path(tmp), lambda _p: None)
                ft["train_seconds"][(b, s)] = time.perf_counter() - t0
                out = [_predict_one(backend, model, task, t) for t in texts]
            ft["labels"][(b, s)] = [o[0] for o in out]
            ft["latency"][(b, s)] = [o[1] for o in out]
            log(f"  {FINETUNE} budget {b} seed {s}: trained in {ft['train_seconds'][(b, s)]:.1f}s, {len(texts)} predicted")
    zs = {"kind": "local", "zero_shot": True, "meta": {}, "labels": {}, "latency": {}, "tokens": {}, "train_seconds": {}}
    out = [_predict_one(backend, BASE, task, t) for t in texts]
    zs["labels"][(0, 0)] = [o[0] for o in out]
    zs["latency"][(0, 0)] = [o[1] for o in out]
    log(f"  {ZERO_SHOT}: {len(texts)} predicted")
    return ft, zs


# --- costs -------------------------------------------------------------------


def _api_price(meta: dict, currency: str, fx: tuple[float, str] | None) -> tuple[float, float, float]:
    """(input per M, output per M, conversion rate) in the report currency."""
    for k in meta:
        if k.startswith("price_input_per_million_"):
            cur = k.removeprefix("price_input_per_million_")
            rate = 1.0
            if cur.upper() != currency.upper():
                if fx is None:
                    raise EvalError(f"prices are in {cur.upper()}; pass --fx <rate,date> to convert to {currency}")
                rate = fx[0]
            return meta[k], meta[f"price_output_per_million_{cur}"], rate
    raise EvalError(f"api system meta has no price_input_per_million_<currency>: {sorted(meta)}")


def system_rows(sys_: dict, budgets, seeds, cpu_per_hour: float, currency: str, fx) -> list[dict]:
    rows = []
    for b in [0] if sys_["zero_shot"] else budgets:
        keys = [(0, 0)] if sys_["zero_shot"] else [(b, s) for s in seeds]
        lat = [x for k in keys for x in sys_["latency"][k]]
        row: dict[str, Any] = {"budget": b, "p95_latency_ms": round(p95(lat), 3)}
        if sys_["kind"] == "api":
            pin, pout, rate = _api_price(sys_["meta"], currency, fx)
            toks = [t for k in keys for t in sys_["tokens"][k]]
            per_1k = 1000 * rate * fmean(i * pin + o * pout for i, o in toks) / 1e6
            row.update(cost_per_1k=per_1k, cost_per_1k_low=per_1k * (1 - TOKEN_SENSITIVITY),
                       cost_per_1k_high=per_1k * (1 + TOKEN_SENSITIVITY),
                       mean_input_tokens=fmean(t[0] for t in toks), mean_output_tokens=fmean(t[1] for t in toks),
                       training_cpu_hours=0.0)
        else:
            train_s = [sys_["train_seconds"].get(k, 0.0) for k in keys] if not sys_["zero_shot"] else [0.0]
            train_h = fmean(train_s) / 3600
            infer_h_per_1k = fmean(lat) * 1000 / 3_600_000
            row.update(inference_cost_per_1k=infer_h_per_1k * cpu_per_hour,
                       retrain_cost_per_1k=train_h * cpu_per_hour * 1000 / AMORTISE_DECISIONS,
                       training_cpu_hours=train_h)
            row["cost_per_1k"] = row["inference_cost_per_1k"] + row["retrain_cost_per_1k"]
        rows.append(row)
    return rows


# --- one dataset -------------------------------------------------------------


def evaluate_dataset(name: str, args, backend, log) -> dict:
    ddir = args.data_dir / name
    records_path = ddir / "records.jsonl"
    if not records_path.exists():
        raise EvalError(f"{records_path}: not found")
    records = _read_jsonl(records_path)
    task = tasks.load(args.tasks_dir / f"{name}.yaml")[0]
    test = [r for r in records if r.get("label_mode") == "blind"]
    if not test:
        raise EvalError(f"{records_path}: no blind test records")
    train_by_id = {r["external_id"]: r for r in records if r.get("label_mode") != "blind"}
    test_ids = [r["external_id"] for r in test]
    gold = [r["label"] for r in test]
    groups = [r.get("group_id") or r["external_id"] for r in test]
    subsets = {}
    for b in args.budgets:
        for s in args.seeds:
            p = ddir / "subsets" / f"{b}-{s}.json"
            if not p.exists():
                raise EvalError(f"{p}: missing training subset for budget {b} seed {s}")
            subsets[(b, s)] = json.loads(p.read_text())

    log(f"{name}: {len(test)} test records, {len(task.labels)} labels")
    ft, zs = run_backend(backend, task, train_by_id, test, subsets, args.budgets, args.seeds, log)
    systems = {FINETUNE: ft, ZERO_SHOT: zs}
    pdir = args.predictions / name
    for path in sorted(pdir.glob("*.jsonl")) if pdir.is_dir() else []:
        if path.stem in systems:
            raise EvalError(f"{path}: system name '{path.stem}' is reserved")
        systems[path.stem] = load_external(path, test_ids, set(task.labels), args.budgets, args.seeds)
        log(f"  read system {path.stem}")

    ft_by_budget = {b: [ft["labels"][(b, s)] for s in args.seeds] for b in args.budgets}
    out_systems = []
    for sname, sys_ in systems.items():
        rows = system_rows(sys_, args.budgets, args.seeds, args.cpu_eur_per_hour, args.currency, args.fx)
        for row in rows:
            keys = [(0, 0)] if sys_["zero_shot"] else [(row["budget"], s) for s in args.seeds]
            by_seed = [weighted_macro_f1(gold, sys_["labels"][k], [1] * len(gold)) for k in keys]
            row["macro_f1"] = fmean(by_seed)
            row["macro_f1_by_seed"] = by_seed
            row["invalid"] = sum(1 for k in keys for x in sys_["labels"][k] if x is None)
        vs = []
        if sname != FINETUNE:
            for b in args.budgets:
                if not sys_["zero_shot"] and b not in {r["budget"] for r in rows}:
                    continue
                a = [sys_["labels"][(0, 0)]] if sys_["zero_shot"] else [sys_["labels"][(b, s)] for s in args.seeds]
                c = paired_bootstrap(gold, a, ft_by_budget[b], groups, args.resamples, seed=0)
                vs.append({"finetune_budget": b, "delta": c.delta, "ci_low": c.ci_low, "ci_high": c.ci_high, "n": c.n})
        entry = {"name": sname, "kind": sys_["kind"], "zero_shot": sys_["zero_shot"], "rows": rows,
                 "vs_finetune": vs}
        if sys_["kind"] == "api":
            m = sys_["meta"]
            entry["api"] = {k: m.get(k) for k in ("model", "settings", "price_date", "run_date", "prompt_template_sha256")}
            entry["api"]["prices"] = {k: v for k, v in m.items() if k.startswith("price_") and k != "price_date"}
        out_systems.append(entry)

    info = DATASET_INFO.get(name, {"dataset": name})
    return {
        "name": name,
        "task": task.name,
        "labels": len(task.labels),
        "n_test": len(test),
        "records_sha256": hashlib.sha256(records_path.read_bytes()).hexdigest(),
        "source": info,
        "systems": out_systems,
    }


# --- gate and zero-shot rule -------------------------------------------------


def _row(ds: dict, system: str, budget: int) -> dict | None:
    for s in ds["systems"]:
        if s["name"] == system:
            for r in s["rows"]:
                if r["budget"] == budget or s["zero_shot"]:
                    return r
    return None


def _vs(ds: dict, system: str, budget: int) -> dict | None:
    for s in ds["systems"]:
        if s["name"] == system:
            return next((v for v in s["vs_finetune"] if v["finetune_budget"] == budget), None)
    return None


def gate_section(datasets: list[dict], budgets) -> dict:
    out: dict[str, Any] = {"budget": GATE_BUDGET, "outcome": None, "reason": None, "per_dataset": []}
    if GATE_BUDGET not in budgets:
        out["reason"] = f"budget {GATE_BUDGET} not run"
        return out
    inputs = []
    for ds in datasets:
        api = sorted(s["name"] for s in ds["systems"] if s["kind"] == "api")
        if not api:
            out["reason"] = f"no API system for {ds['name']}"
            out["per_dataset"] = []
            return out
        llm = api[0]
        v, b, c = _vs(ds, llm, GATE_BUDGET), _row(ds, llm, GATE_BUDGET), _row(ds, FINETUNE, GATE_BUDGET)
        gi = evaluation.GateInput(
            dataset=ds["name"],
            f1=evaluation.Comparison(v["delta"], v["ci_low"], v["ci_high"], v["n"]),
            llm_cost_per_1k=b["cost_per_1k"], c_cost_per_1k=c["cost_per_1k"],
            llm_p95_ms=b["p95_latency_ms"], c_p95_ms=c["p95_latency_ms"],
        )
        inputs.append(gi)
        out["per_dataset"].append({
            "dataset": ds["name"], "llm_system": llm,
            "llm_cheaper": gi.llm_cost_per_1k < gi.c_cost_per_1k,
            "llm_faster": gi.llm_p95_ms < gi.c_p95_ms,
            "llm_better": gi.f1.ci_low > 0,
            "llm_wins": evaluation.llm_wins(gi),
        })
    out["outcome"] = type(evaluation.gate(inputs)).__name__
    return out


def zero_shot_rule(datasets: list[dict], budgets) -> dict:
    base, budget = ZERO_SHOT_RULE
    out: dict[str, Any] = {"baseline": base, "budget": budget, "outcome": None, "per_dataset": []}
    if budget not in budgets:
        return out
    for ds in datasets:
        b = _row(ds, base, budget)
        if b is None:
            out["per_dataset"] = []
            return out
        d = _row(ds, ZERO_SHOT, 0)["macro_f1"]
        out["per_dataset"].append({"dataset": ds["name"], "zero_shot_f1": d, "baseline_f1": b["macro_f1"],
                                   "passes": d >= b["macro_f1"]})
    out["outcome"] = all(x["passes"] for x in out["per_dataset"])
    return out


# --- report.md ---------------------------------------------------------------


def _f(x: float | None, nd: int = 3) -> str:
    return "n/a" if x is None else f"{x:.{nd}f}"


def _money(x: float, cur: str) -> str:
    return f"{x:.4f} {cur}"


def render_md(r: dict) -> str:
    """Render report.md from report.json alone (every number comes from ``r``)."""
    run, cur = r["run"], r["run"]["currency"]
    L = ["# decider-ai Phase 0 report", ""]
    L += [
        f"- Run date: {run['date']}",
        f"- Git SHA: {run['git_sha']}",
        f"- Machine: {run['machine']}",
        f"- Backend: {run['backend']['name']} (Laya revision {run['backend']['laya_revision'] or 'n/a'}, "
        f"SDK {run['backend']['sdk_version'] or 'n/a'})",
        f"- CPU price: {run['cpu_price_per_hour']} {cur}/h (retrieved {run['price_date']})",
        f"- FX: {'n/a' if run['fx'] is None else str(run['fx']['rate']) + ' (' + run['fx']['date'] + ')'}",
        f"- Budgets {', '.join(map(str, run['budgets']))}; seeds {', '.join(map(str, run['seeds']))}",
        f"- CIs: {run['ci']}",
        f"- Local cost: busy CPU-hours at the hourly rate plus one retrain amortised over "
        f"{run['amortise_decisions']:,} decisions",
        "",
    ]
    g = r["gate"]
    L += ["## Outcome", ""]
    if g["outcome"] is None:
        L.append(f"Gate at {g['budget']} labels: not applicable ({g['reason']}).")
    else:
        L.append(f"Gate at {g['budget']} labels: **{g['outcome']}**.")
    for ds in r["datasets"]:
        h = ds.get("headline")
        if h:
            L.append("")
            L.append(
                f"{ds['name']}: at {h['budget']} labels the fine-tune scores macro-F1 {_f(h['finetune_f1'])} "
                f"vs {h['llm_system']} {_f(h['llm_f1'])} (Δ {h['llm_system']} − fine-tune {h['delta']:+.3f}, "
                f"95% CI {h['ci_low']:+.3f} to {h['ci_high']:+.3f}), costs {_money(h['finetune_cost_per_1k'], cur)} "
                f"vs {_money(h['llm_cost_per_1k'], cur)} per 1,000 decisions, p95 {h['finetune_p95_ms']:.1f} ms "
                f"vs {h['llm_p95_ms']:.1f} ms."
            )
    zs = r["zero_shot_rule"]
    L.append("")
    if zs["outcome"] is None:
        L.append(f"Zero-shot rule ({ZERO_SHOT} ≥ {zs['baseline']} at {zs['budget']} on every dataset): not applicable.")
    else:
        L.append(f"Zero-shot rule ({ZERO_SHOT} ≥ {zs['baseline']} at {zs['budget']} on every dataset): "
                 f"**{'met' if zs['outcome'] else 'not met'}**"
                 + "".join(f"; {x['dataset']} {_f(x['zero_shot_f1'])} vs {_f(x['baseline_f1'])}" for x in zs["per_dataset"])
                 + ".")
    if g["per_dataset"]:
        L += ["", "| Dataset | LLM system | Cheaper | Faster p95 | Better F1 (CI > 0) | LLM wins |", "|---|---|---|---|---|---|"]
        yn = lambda b: "yes" if b else "no"  # noqa: E731
        for x in g["per_dataset"]:
            L.append(f"| {x['dataset']} | {x['llm_system']} | {yn(x['llm_cheaper'])} | {yn(x['llm_faster'])} | "
                     f"{yn(x['llm_better'])} | {yn(x['llm_wins'])} |")

    for ds in r["datasets"]:
        L += ["", f"## {ds['name']}", "",
              f"Test set n = {ds['n_test']} ({ds['labels']} labels). Records sha256 `{ds['records_sha256']}`.", "",
              "Macro-F1 with Δ vs the fine-tune at the same budget (zero-shot systems: vs the fine-tune at each "
              "budget); nominal 95% paired-bootstrap CI, unadjusted.", "",
              f"| System | Budget | Macro-F1 | Δ vs fine-tune | 95% CI | Invalid | p95 ms | Cost / 1,000 ({cur}) |",
              "|---|---|---|---|---|---|---|---|"]
        for s in ds["systems"]:
            for row in s["rows"]:
                vs = [v for v in s["vs_finetune"] if s["zero_shot"] or v["finetune_budget"] == row["budget"]]
                budget = "zero-shot" if s["zero_shot"] else str(row["budget"])
                if not vs:
                    L.append(f"| {s['name']} | {budget} | {_f(row['macro_f1'])} | — | — | {row['invalid']} | "
                             f"{row['p95_latency_ms']:.1f} | {row['cost_per_1k']:.4f} |")
                for v in vs:
                    b = f"{budget} (vs {v['finetune_budget']})" if s["zero_shot"] else budget
                    L.append(f"| {s['name']} | {b} | {_f(row['macro_f1'])} | {v['delta']:+.3f} | "
                             f"{v['ci_low']:+.3f} to {v['ci_high']:+.3f} | {row['invalid']} | "
                             f"{row['p95_latency_ms']:.1f} | {row['cost_per_1k']:.4f} |")
        curve = [s for s in ds["systems"] if s["name"] in (FINETUNE, ZERO_SHOT_RULE[0])]
        L += ["", "Learning curve (macro-F1, mean over seeds):", "",
              "| System | " + " | ".join(str(b) for b in r["run"]["budgets"]) + " |",
              "|---|" + "---|" * len(r["run"]["budgets"])]
        for s in curve:
            by = {row["budget"]: row["macro_f1"] for row in s["rows"]}
            L.append(f"| {s['name']} | " + " | ".join(_f(by.get(b)) for b in r["run"]["budgets"]) + " |")
        L += ["", f"Cost lines ({cur}):", ""]
        for s in ds["systems"]:
            for row in s["rows"]:
                at = "zero-shot" if s["zero_shot"] else f"budget {row['budget']}"
                if s["kind"] == "api":
                    L.append(f"- {s['name']} ({at}): {row['cost_per_1k']:.4f} per 1,000 at list price "
                             f"(±{int(TOKEN_SENSITIVITY * 100)}% tokens: {row['cost_per_1k_low']:.4f} to "
                             f"{row['cost_per_1k_high']:.4f}); mean tokens {row['mean_input_tokens']:.1f} in / "
                             f"{row['mean_output_tokens']:.1f} out")
                else:
                    L.append(f"- {s['name']} ({at}): inference {row['inference_cost_per_1k']:.6f} + retrain "
                             f"{row['retrain_cost_per_1k']:.6f} per 1,000; training CPU-hours "
                             f"{row['training_cpu_hours']:.6f}")
        for s in ds["systems"]:
            if "api" in s:
                a = s["api"]
                L.append(f"- {s['name']}: model {a['model']}, settings {json.dumps(a['settings'], sort_keys=True)}, "
                         f"prices {json.dumps(a['prices'], sort_keys=True)} (retrieved {a['price_date']})")

    L += ["", "## Datasets", ""]
    for ds in r["datasets"]:
        src = ds["source"]
        line = f"- {ds['name']}: {src.get('dataset')}"
        if "authors" in src:
            line += f"; {src['authors']}; licence {src['licence']}; {src['link']}; pin {src['pin']}"
            line += "; sha256 " + ", ".join(f"{k} `{v}`" for k, v in src["sha256"].items())
        L.append(line)
    return "\n".join(L) + "\n"


# --- CLI ---------------------------------------------------------------------


def _git_sha() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _backend_info(name: str, backend) -> dict:
    sdk = None
    if name == "laya":
        try:
            from importlib.metadata import version

            sdk = version("laya")
        except Exception:
            sdk = None
    return {"name": name, "laya_revision": getattr(backend, "revision", None), "sdk_version": sdk}


def _headline(ds: dict, gate: dict) -> dict | None:
    x = next((p for p in gate["per_dataset"] if p["dataset"] == ds["name"]), None)
    if x is None:
        return None
    b = gate["budget"]
    ft, llm, v = _row(ds, FINETUNE, b), _row(ds, x["llm_system"], b), _vs(ds, x["llm_system"], b)
    return {"budget": b, "llm_system": x["llm_system"], "finetune_f1": ft["macro_f1"], "llm_f1": llm["macro_f1"],
            "delta": v["delta"], "ci_low": v["ci_low"], "ci_high": v["ci_high"],
            "finetune_cost_per_1k": ft["cost_per_1k"], "llm_cost_per_1k": llm["cost_per_1k"],
            "finetune_p95_ms": ft["p95_latency_ms"], "llm_p95_ms": llm["p95_latency_ms"]}


def _seeds(s: str) -> list[int]:
    if "-" in s:
        a, b = s.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in s.split(",")]


def _fx(s: str) -> tuple[float, str]:
    rate, date = s.split(",")
    return float(rate), date


def parse_args(argv) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="decider-eval", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    p.add_argument("--datasets", required=True, help="comma list of dataset names under --data-dir")
    p.add_argument("--tasks-dir", type=Path, default=Path("bench/tasks"), help="holds <dataset>.yaml")
    p.add_argument("--predictions", type=Path, default=Path("predictions"))
    p.add_argument("--budgets", default="50,100,250")
    p.add_argument("--seeds", type=_seeds, default=_seeds("0-4"))
    p.add_argument("--backend", default="fake", choices=["fake", "laya"])
    p.add_argument("--machine", required=True, help="machine specs, stated in the report")
    p.add_argument("--cpu-eur-per-hour", "--price-per-hour", dest="cpu_eur_per_hour", type=float, default=0.0256)
    p.add_argument("--price-date", default="2026-10-08", help="retrieval date of the CPU price")
    p.add_argument("--currency", default="EUR")
    p.add_argument("--fx", type=_fx, default=None, help="rate,date: API price currency -> --currency")
    p.add_argument("--resamples", type=int, default=2000)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    a.budgets = [int(b) for b in a.budgets.split(",")]
    return a


def run(argv=None, backend=None, log=print) -> dict:
    args = parse_args(argv)
    backend = backend if backend is not None else make_backend(args.backend)
    datasets = [evaluate_dataset(n, args, backend, log) for n in args.datasets.split(",")]
    gate = gate_section(datasets, args.budgets)
    for ds in datasets:
        ds["headline"] = _headline(ds, gate)
    report = {
        "schema_version": SCHEMA_VERSION,
        "run": {
            "date": dt.date.today().isoformat(),
            "git_sha": _git_sha(),
            "machine": args.machine,
            "backend": _backend_info(args.backend, backend),
            "cpu_price_per_hour": args.cpu_eur_per_hour,
            "price_date": args.price_date,
            "currency": args.currency,
            "fx": None if args.fx is None else {"rate": args.fx[0], "date": args.fx[1]},
            "budgets": args.budgets,
            "seeds": args.seeds,
            "resamples": args.resamples,
            "amortise_decisions": AMORTISE_DECISIONS,
            "ci": f"nominal 95% paired bootstrap ({args.resamples} resamples, seeds averaged inside each "
                  "resample), unadjusted; one look per dataset",
        },
        "datasets": datasets,
        "gate": gate,
        "zero_shot_rule": zero_shot_rule(datasets, args.budgets),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (args.out / "report.md").write_text(render_md(report), encoding="utf-8")
    log(f"gate: {gate['outcome'] or 'not applicable'}; zero-shot rule: {report['zero_shot_rule']['outcome']}")
    log(f"wrote {args.out / 'report.json'} and {args.out / 'report.md'}")
    return report


def main(argv=None) -> None:
    try:
        run(sys.argv[1:] if argv is None else argv)
    except EvalError as e:
        print(f"decider-eval: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
