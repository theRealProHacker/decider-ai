from pathlib import Path

from decider.tasks import load

ROOT = Path(__file__).resolve().parents[2]


def test_benchmark_tasks_load():
    massive = load(ROOT / "bench/tasks/massive_de_scenario.yaml")
    clinc = load(ROOT / "bench/tasks/clinc_domain.yaml")
    assert [len(t.labels) for t in massive] == [18]
    assert [len(t.labels) for t in clinc] == [11]
