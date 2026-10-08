from dataclasses import dataclass, replace

import pytest

from decider.evaluation import (
    Comparison,
    GateInput,
    Launch,
    NotEnough,
    NotRecommended,
    Recommended,
    ReScope,
    Split,
    Unverified,
    compare,
    gate,
    recommend,
    split,
)


@dataclass(frozen=True)
class Ex:
    external_id: str
    label: str
    group_id: str
    label_mode: str = "blind"


def make(labels_counts, mode="blind", group_size=1, prefix=""):
    out = []
    for label, count in labels_counts.items():
        for i in range(count):
            out.append(Ex(f"{prefix}{label}{i}", label, f"{prefix}{label}-g{i // group_size}", mode))
    return out


# --- split -------------------------------------------------------------------


def test_split_exact_size_and_min_per_label():
    examples = make({"a": 60, "b": 50, "c": 50})
    s = split(examples, size=100, min_per_label=10)
    assert isinstance(s, Split)
    assert len(s.test) == 100
    assert len(s.test) + len(s.rest) == len(examples)
    for label in "abc":
        assert sum(ex.label == label for ex in s.test) >= 10


def test_split_keeps_groups_together():
    examples = make({"a": 60, "b": 60, "c": 60}, group_size=4)
    s = split(examples, size=100, min_per_label=10)
    assert isinstance(s, Split)
    assert len(s.test) == 100
    test_groups = {ex.group_id for ex in s.test}
    rest_groups = {ex.group_id for ex in s.rest}
    assert not test_groups & rest_groups


def test_split_prefers_blind():
    examples = make({"a": 40, "b": 40, "c": 40}, mode="blind", prefix="x") + make(
        {"a": 40, "b": 30, "c": 30}, mode="assisted", prefix="y"
    )
    s = split(examples, size=100, min_per_label=10)
    assert isinstance(s, Split)
    assert all(ex.label_mode == "blind" for ex in s.test)


def test_split_one_label_short():
    examples = make({"a": 60, "b": 60, "c": 9})
    assert split(examples, size=100, min_per_label=10) == NotEnough(blocking_labels=["c"])


def test_split_deterministic_for_seed():
    examples = make({"a": 60, "b": 60, "c": 60}, group_size=3)
    assert split(examples, 100, 10, seed=7) == split(examples, 100, 10, seed=7)


# --- compare -----------------------------------------------------------------

GOLD = ["x", "y", "z", "x", "y", "z", "x", "x", "y", "z"]


def test_compare_equal_systems():
    c = compare(GOLD, GOLD, [GOLD], groups=list(range(10)), resamples=500)
    assert c.delta == 0
    assert c.ci_low <= 0 <= c.ci_high


def test_compare_perfect_vs_chance():
    gold = ["a", "b", "c", "d"] * 50
    # b is right only on every 4th item: chance level for 4 labels
    chance = [g if i % 4 == 0 else {"a": "b", "b": "c", "c": "d", "d": "a"}[g] for i, g in enumerate(gold)]
    c = compare(gold, gold, [chance], groups=list(range(200)), resamples=500)
    assert c.n == 200
    assert c.ci_low > 0


def test_compare_identical_seeds_equal_one_seed():
    b = ["x", "x", "z", "x", "z", "z", "y", "x", "y", "y"]
    one = compare(GOLD, GOLD, [b], groups=list(range(10)), resamples=300, seed=3)
    five = compare(GOLD, GOLD, [b] * 5, groups=list(range(10)), resamples=300, seed=3)
    assert five.delta == pytest.approx(one.delta, abs=1e-12)
    assert five.ci_low == pytest.approx(one.ci_low, abs=1e-12)
    assert five.ci_high == pytest.approx(one.ci_high, abs=1e-12)


def test_compare_resamples_by_group():
    # Group A: gold x, a right, b wrong. Group B: gold y, a wrong, b right.
    gold = ["x"] * 10 + ["y"] * 10
    a = ["x"] * 20
    b = ["y"] * 20
    groups = ["A"] * 10 + ["B"] * 10
    c = compare(gold, a, [b], groups, resamples=2000)
    # Whole groups move together, so the extremes are "A twice" (+1) and "B twice" (-1),
    # each drawn with probability 1/4; item-level resampling would almost never hit them.
    assert c.ci_low == -1.0
    assert c.ci_high == 1.0
    assert c.n == 20


def test_compare_deterministic_for_seed():
    b = ["x", "x", "z", "x", "z", "z", "y", "x", "y", "y"]
    args = (GOLD, GOLD, [b, GOLD], list(range(10)))
    assert compare(*args, resamples=200, seed=1) == compare(*args, resamples=200, seed=1)


# --- recommend ---------------------------------------------------------------


def test_recommend():
    up = Comparison(delta=0.1, ci_low=0.02, ci_high=0.2, n=100)
    flat = Comparison(delta=0.01, ci_low=0.0, ci_high=0.05, n=100)
    assert recommend(up, split_frozen=True) == Recommended(up)
    assert recommend(flat, split_frozen=True) == NotRecommended(flat)
    assert recommend(up, split_frozen=False) == Unverified()


# --- gate --------------------------------------------------------------------

LLM_WINS = GateInput(
    dataset="massive",
    f1=Comparison(delta=0.1, ci_low=0.05, ci_high=0.15, n=2974),
    llm_cost_per_1k=0.05,
    c_cost_per_1k=0.10,
    llm_p95_ms=200.0,
    c_p95_ms=400.0,
)
LOSING_AXES = {
    "cost": {"llm_cost_per_1k": 0.20},
    "latency": {"llm_p95_ms": 500.0},
    "f1": {"f1": Comparison(delta=0.05, ci_low=-0.01, ci_high=0.1, n=2974)},
}


def test_gate_rescope_when_llm_wins_everywhere():
    both = [LLM_WINS, replace(LLM_WINS, dataset="clinc")]
    assert gate(both) == ReScope()


@pytest.mark.parametrize("axis", LOSING_AXES)
@pytest.mark.parametrize("which", [0, 1])
def test_gate_flip_one_axis_on_one_dataset_launches(axis, which):
    both = [LLM_WINS, replace(LLM_WINS, dataset="clinc")]
    both[which] = replace(both[which], **LOSING_AXES[axis])
    assert gate(both) == Launch()


def test_gate_ties_launch():
    tie = replace(LLM_WINS, llm_cost_per_1k=0.10)
    assert gate([tie]) == Launch()
