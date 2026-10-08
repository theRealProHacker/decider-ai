"""Pure statistics shared by Decider and decider-eval: split, compare, recommend, gate.

No I/O, stdlib only. Every random choice takes a ``seed`` so results are reproducible.
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import fmean
from typing import Any, Sequence

# --- split -------------------------------------------------------------------


@dataclass(frozen=True)
class Split:
    test: tuple[Any, ...]  # the held-out examples (exactly `size`)
    rest: tuple[Any, ...]  # everything else, usable for training


@dataclass(frozen=True)
class NotEnough:
    blocking_labels: list[str]


def _group_of(ex: Any) -> Any:
    group = getattr(ex, "group_id", None)
    return group if group is not None else getattr(ex, "external_id", id(ex))


def _is_blind(ex: Any) -> bool:
    return getattr(ex, "label_mode", "blind") == "blind"


def split(
    examples: Sequence[Any],
    size: int,
    min_per_label: int,
    prefer_blind: bool = True,
    seed: int = 0,
) -> Split | NotEnough:
    """Pick a group-aware held-out set of exactly ``size`` examples.

    Examples are any objects with ``label`` and optionally ``group_id``,
    ``external_id`` and ``label_mode`` ("blind" / "assisted"). A group is never
    split across test and rest. Every label ends up with >= ``min_per_label``.
    """
    counts = Counter(ex.label for ex in examples)
    short = sorted(label for label, n in counts.items() if n < min_per_label)
    if short:
        return NotEnough(blocking_labels=short)

    groups: dict[Any, list[Any]] = defaultdict(list)
    for ex in examples:
        groups[_group_of(ex)].append(ex)
    order = list(groups)
    random.Random(seed).shuffle(order)
    if prefer_blind:  # stable sort keeps the shuffle within each class
        order.sort(key=lambda g: not all(_is_blind(ex) for ex in groups[g]))

    chosen: list[Any] = []
    have: Counter[str] = Counter()
    total = 0

    def take(g: Any) -> None:
        nonlocal total
        chosen.append(g)
        have.update(ex.label for ex in groups[g])
        total += len(groups[g])

    # Pass 1: meet min_per_label for every label.
    for label in sorted(counts):
        for g in order:
            if have[label] >= min_per_label:
                break
            if g in chosen or total + len(groups[g]) > size:
                continue
            if any(ex.label == label for ex in groups[g]):
                take(g)
    # Pass 2: fill up to exactly `size`.
    for g in order:
        if total == size:
            break
        if g not in chosen and total + len(groups[g]) <= size:
            take(g)

    blocking = sorted(label for label in counts if have[label] < min_per_label)
    if blocking or total != size:
        return NotEnough(blocking_labels=blocking)
    picked = set(chosen)
    test = tuple(ex for g in chosen for ex in groups[g])
    rest = tuple(ex for ex in examples if _group_of(ex) not in picked)
    return Split(test=test, rest=rest)


# --- compare -----------------------------------------------------------------


@dataclass(frozen=True)
class Comparison:
    delta: float  # metric(a) - mean over seeds of metric(b)
    ci_low: float  # 95% paired-bootstrap interval of delta
    ci_high: float
    n: int  # number of items


def macro_f1(gold: Sequence[str], pred: Sequence[str]) -> float:
    """Unweighted mean F1 over every label seen in gold or predictions."""
    labels = set(gold) | set(pred)
    if not labels:
        return 0.0
    scores = []
    for label in labels:
        tp = sum(1 for g, p in zip(gold, pred) if g == label and p == label)
        fp = sum(1 for g, p in zip(gold, pred) if g != label and p == label)
        fn = sum(1 for g, p in zip(gold, pred) if g == label and p != label)
        scores.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return fmean(scores)


def accuracy(gold: Sequence[str], pred: Sequence[str]) -> float:
    return fmean(g == p for g, p in zip(gold, pred)) if gold else 0.0


METRICS = {"macro_f1": macro_f1, "accuracy": accuracy}


def compare(
    gold: Sequence[str],
    a: Sequence[str],
    b_by_seed: Sequence[Sequence[str]],
    groups: Sequence[Any],
    metric: str = "macro_f1",
    resamples: int = 2000,
    seed: int = 0,
) -> Comparison:
    """Paired bootstrap of metric(a) - mean_seeds(metric(b)), resampling whole groups."""
    m = METRICS[metric]
    n = len(gold)
    if not (len(a) == len(groups) == n and all(len(b) == n for b in b_by_seed) and b_by_seed):
        raise ValueError("gold, a, every b and groups must have the same non-zero length")

    def delta(idx: Sequence[int]) -> float:
        g = [gold[i] for i in idx]
        score_a = m(g, [a[i] for i in idx])
        return score_a - fmean(m(g, [b[i] for i in idx]) for b in b_by_seed)

    members: dict[Any, list[int]] = defaultdict(list)
    for i, grp in enumerate(groups):
        members[grp].append(i)
    keys = list(members)
    rng = random.Random(seed)
    deltas = sorted(
        delta([i for k in rng.choices(keys, k=len(keys)) for i in members[k]])
        for _ in range(resamples)
    )
    lo = deltas[int(0.025 * (resamples - 1))]
    hi = deltas[int(round(0.975 * (resamples - 1)))]
    return Comparison(delta=delta(range(n)), ci_low=lo, ci_high=hi, n=n)


# --- recommend ---------------------------------------------------------------


@dataclass(frozen=True)
class Recommended:
    comparison: Comparison


@dataclass(frozen=True)
class NotRecommended:
    comparison: Comparison


@dataclass(frozen=True)
class Unverified:
    pass


def recommend(cmp: Comparison | None, split_frozen: bool) -> Recommended | NotRecommended | Unverified:
    """Advisory verdict on a candidate vs the active model."""
    if not split_frozen or cmp is None:
        return Unverified()
    return Recommended(cmp) if cmp.ci_low > 0 else NotRecommended(cmp)


# --- Phase 0 gate ------------------------------------------------------------


@dataclass(frozen=True)
class GateInput:
    """One dataset: LLM baseline (b) vs the fine-tune (c) at 250 labels."""

    dataset: str
    f1: Comparison  # macro-F1 of b - c
    llm_cost_per_1k: float
    c_cost_per_1k: float
    llm_p95_ms: float
    c_p95_ms: float


@dataclass(frozen=True)
class ReScope:
    pass


@dataclass(frozen=True)
class Launch:
    pass


def llm_wins(x: GateInput) -> bool:
    return x.llm_cost_per_1k < x.c_cost_per_1k and x.llm_p95_ms < x.c_p95_ms and x.f1.ci_low > 0


def gate(per_dataset: Sequence[GateInput]) -> ReScope | Launch:
    """ReScope only if the LLM is cheaper, faster and better on every dataset."""
    if per_dataset and all(llm_wins(x) for x in per_dataset):
        return ReScope()
    return Launch()
