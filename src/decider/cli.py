"""``decider-ai``: the container's entrypoint and the command an operator (or an AI agent) types.

`serve` (the image's default) starts the service. Everything else talks to that service on localhost with the key
from the volume, so nobody handles the key or curl:

    docker run --rm IMAGE guide                         # setup instructions for an AI agent
    docker run --rm -i -v decider-data:/data IMAGE init < tickets.xlsx
    docker exec decider-ai decider-ai "Do you have a free trial?"
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections import Counter
from importlib import resources
from pathlib import Path

import yaml

from decider import sheets, tasks

DATA = Path(os.environ.get("DECIDER_DATA", "/data"))
URL = os.environ.get("DECIDER_URL", "http://127.0.0.1:8080")
JOB = DATA / "cli-job.json"
COMMANDS = ("serve", "guide", "init", "config", "ready", "status", "check", "import", "train",
            "wait", "activate", "ask")


class Fail(Exception):
    pass


# --- talking to the service -------------------------------------------------------------------


def key() -> str:
    k = os.environ.get("DECIDER_API_KEY")
    if k:
        return k
    try:
        return (DATA / "api_key").read_text().strip()
    except OSError:
        raise Fail("no API key yet: start the service first (see `decider-ai guide`)") from None


def call(method: str, path: str, body=None, ctype: str = "application/json"):
    data = body if isinstance(body, bytes) or body is None else json.dumps(body).encode()
    req = urllib.request.Request(f"{URL}{path}", data, method=method, headers={
        "Authorization": f"Bearer {key()}", "Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            err = json.load(e)["error"]
        except Exception:
            raise Fail(f"HTTP {e.code}") from None
        raise Fail(err["message"]) from None
    except urllib.error.URLError:
        raise Fail("the service is not answering yet; run `decider-ai ready`") from None


def live() -> bool:
    try:
        with urllib.request.urlopen(f"{URL}/health/live", timeout=5):
            return True
    except Exception:
        return False


def task_names() -> dict[str, dict]:
    return call("GET", "/health/ready")["tasks"]


def pick_task(name: str | None) -> str:
    names = list(task_names())
    if name:
        if name not in names:
            raise Fail(f"no task '{name}'; tasks: {', '.join(names)}")
        return name
    if len(names) > 1:
        raise Fail(f"several tasks, name one with --task: {', '.join(names)}")
    return names[0]


def stdin_sheet(args) -> tuple[list[dict[str, str]], dict[str, str | None]]:
    if sys.stdin.isatty():
        raise Fail("pipe the spreadsheet in: ... < file.xlsx (with docker exec -i / docker run -i)")
    try:
        rows = sheets.read(sys.stdin.buffer.read())
        guess = sheets.guess_columns(rows)
    except sheets.SheetError as e:
        raise Fail(str(e)) from None
    cols = {"text": args.text_column or guess["text"], "label": args.label_column or guess["label"],
            "id": args.id_column or guess["id"]}
    missing = [c for c in (cols["text"], cols["label"], cols["id"]) if c and c not in rows[0]]
    if missing:
        raise Fail(f"no column {missing[0]!r}; columns: {list(rows[0])}")
    return rows, cols


def columns_line(cols) -> str:
    return (f"text column {cols['text']!r}, label column {cols['label']!r}, "
            + (f"ID column {cols['id']!r}" if cols["id"] else "no ID column (the text is the ID)"))


# --- commands ---------------------------------------------------------------------------------


def cmd_guide(args):
    guide = resources.files("decider").joinpath("guide.md").read_text()
    print(guide.replace("{image}", os.environ.get("DECIDER_IMAGE", "decider-ai:dev")))


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") or "route"


def cmd_init(args):
    rows, cols = stdin_sheet(args)
    counts = Counter(r[cols["label"]] for r in rows if r.get(cols["label"]) and r.get(cols["text"]))
    name = args.task or slug(cols["label"])
    spec = {"tasks": [{
        "name": name,
        "question": "Which category fits this message best?",
        "zero_shot": True,
        "labels": {label: label for label in sorted(counts)},
    }]}
    text = yaml.safe_dump(spec, allow_unicode=True, sort_keys=False)
    write_config(text, args.force)
    print(text, end="")
    print(f"\n{sum(counts.values())} rows; {columns_line(cols)}; labels: "
          + ", ".join(f"{k} {v}" for k, v in counts.most_common()), file=sys.stderr)
    print("Wrote /data/tasks.yaml. The question is generic and the label descriptions are the "
          "label names; better ones help zero-shot: edit and load with `config`.", file=sys.stderr)


def write_config(text: str, force: bool):
    target = DATA / "tasks.yaml"
    if target.exists() and not force and target.read_text() != text:
        raise Fail("/data/tasks.yaml exists; pass --force to replace it (a task's labels are "
                   "fixed once the service has started with it)")
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(text)
    try:
        tasks.load(f.name)
    except tasks.ConfigError as e:
        raise Fail(str(e)) from None
    finally:
        os.unlink(f.name)
    target.write_text(text)


def cmd_config(args):
    write_config(sys.stdin.read(), force=True)
    print("Wrote /data/tasks.yaml. Restart the service to load it: docker restart decider-ai")


def cmd_ready(args):
    deadline = time.monotonic() + args.timeout
    while not live():
        if time.monotonic() > deadline:
            raise Fail("not up yet (the first start downloads ~680 MB); run `decider-ai ready` again")
        time.sleep(3)
    cmd_status(args)


def cmd_status(args):
    for name, t in task_names().items():
        serving = {"base": "the untrained base model (zero-shot)", "trained": f"model {t['active_version']}",
                   "not_trained": "nothing yet (train and activate a model)"}[t["serving"]]
        print(f"{name}: serving {serving}; {t['confirmed']} examples")
    job = last_job()
    if job and job["state"] in ("queued", "running"):
        print(job_line(job))


def last_job() -> dict | None:
    try:
        saved = json.loads(JOB.read_text())
    except (OSError, ValueError):
        return None
    job = call("GET", f"/v1/jobs/{saved['id']}")
    job["started"] = saved["started"]
    return job


def job_line(job) -> str:
    epoch = f"epoch {job['epoch'] or 0}/{job['epochs']}" if job.get("epochs") else "starting"
    p, elapsed = job["progress"], time.time() - job["started"]
    left = f", about {max(1, round(elapsed * (1 - p) / p / 60))} min left" if p > 0.02 else ""
    return f"training {job['task']}: {epoch}{left}"


def cmd_check(args):
    rows, cols = stdin_sheet(args)
    task = pick_task(args.task)
    data = list({r[cols["text"]]: r[cols["label"]] for r in rows
                 if r.get(cols["text"]) and r.get(cols["label"])}.items())  # each text once
    random.Random(0).shuffle(data)
    right, wrong, model, skipped = [], [], None, Counter()
    for text, gold in data[:args.sample]:
        d = call("POST", "/v1/decisions", {"task": task, "text": text})
        model, p = d["model_version"], d["predictions"]
        if gold not in p:
            skipped[gold] += 1
            continue
        (right if max(p, key=p.get) == gold else wrong).append((text, gold, max(p, key=p.get)))
    n = len(right) + len(wrong)
    if not n:
        raise Fail("no row has a label of the task")
    hits, total = Counter(g for _, g, _ in right), Counter(g for _, g, _ in right + wrong)
    print(f"Model {model} on {n} rows: {len(right) / n:.0%} right.")
    print("Per label: " + ", ".join(f"{k} {hits[k]}/{v}" for k, v in total.most_common()))
    confusions = Counter((g, m) for _, g, m in wrong).most_common(3)
    if confusions:
        print("Most confused: " + "; ".join(f"{g} taken for {m} ({c}x)" for (g, m), c in confusions))
    if skipped:
        print("Skipped, label not in the task: " + ", ".join(f"{k} ({v})" for k, v in skipped.items()))
    for title, items in (("Right", right), ("Wrong", wrong)):
        if items:
            print(f"\n{title}:")
            for text, gold, m in items[:args.show]:
                print(f"- [{gold}{'' if gold == m else ' -> ' + m}] {text[:140]}")


def cmd_import(args):
    rows, cols = stdin_sheet(args)
    task = pick_task(args.task)
    lines = [json.dumps({"task": task, "text": r.get(cols["text"]) or None,
                         "label": r.get(cols["label"], ""),
                         "external_id": sheets.external_id(r, cols["id"], r.get(cols["text"], "")),
                         "label_mode": "blind"}) for r in rows]
    out = call("POST", "/v1/examples:batch", "\n".join(lines).encode(), "application/x-ndjson")
    kinds = Counter(o["outcome"] if o["outcome"] != "rejected" else f"rejected ({o['code']})"
                    for o in out["outcomes"])
    print(f"{columns_line(cols)}\n" + ", ".join(f"{v} {k}" for k, v in kinds.most_common()))
    print(f"{task} now has {task_names()[task]['confirmed']} examples.")


def cmd_train(args):
    task = pick_task(args.task)
    job = call("POST", "/v1/retrain", {"task": task})["job_id"]
    JOB.write_text(json.dumps({"id": job, "started": time.time()}))
    print(f"Training {task} started. It takes roughly an hour per 250 examples on a laptop CPU; "
          f"answers keep being served meanwhile. Run `decider-ai wait` to follow it.")


def cmd_wait(args):
    if not last_job():
        raise Fail("no training started from here; run `decider-ai train`")
    deadline, shown = time.monotonic() + args.timeout, None
    while True:
        job = last_job()
        if job["state"] == "succeeded":
            m = job["metrics"]
            score = f", {m['macro_f1']:.0%} macro-F1 on {m['split_size']} held-out rows" if "macro_f1" in m else ""
            print(f"Trained {job['version']}: verdict {job['verdict']}{score}.")
            print(VERDICTS[job["verdict"]])
            print(f"Not serving yet. To serve it: decider-ai activate {job['version']}")
            return
        if job["state"] == "failed":
            raise Fail(f"training failed: {job['error']}")
        line = job_line(job)
        if line != shown:
            print(line, flush=True)
            shown = line
        if time.monotonic() > deadline:
            print("Still training; run `decider-ai wait` again.")
            return
        time.sleep(10)


VERDICTS = {
    "recommended": "It beats the model serving now on the held-out rows.",
    "not_recommended": "It does not beat the model serving now on the held-out rows.",
    "unverified": "No reliable comparison yet (no model to compare with, or too few examples per label).",
}


def cmd_activate(args):
    task = pick_task(args.task)
    version = args.version
    if not version:  # "the newest" is only the one just trained once training has finished
        job = last_job()
        if job and job["task"] == task and job["state"] in ("queued", "running"):
            raise Fail("training is still running; run `decider-ai wait` until it prints the result")
        models = call("GET", f"/v1/tasks/{task}/models")["models"]
        if not models:
            raise Fail(f"no trained model for {task} yet; run `decider-ai train`")
        version = models[-1]["version"]
    out = call("POST", f"/v1/tasks/{task}/models/{version}/activate")
    print(f"{task} now serves {version}." + (f" Note: {out['warning']}" if out.get("warning") else ""))


def cmd_ask(args):
    task = pick_task(args.task)
    text = " ".join(args.text) if args.text else sys.stdin.read()
    p = call("POST", "/v1/decisions", {"task": task, "text": text.strip()})["predictions"]
    if args.scores:
        for label, s in sorted(p.items(), key=lambda x: -x[1]):
            print(f"{label}\t{s:.3f}")
    else:
        print(max(p, key=p.get))


# --- entry ------------------------------------------------------------------------------------


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="decider-ai", description="decider-ai: route messages to labels. "
                                "`decider-ai \"some text\"` answers with a label.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve", help="start the service (the image's default)")
    sub.add_parser("guide", help="setup instructions for an AI agent")
    for name, help_ in (("init", "write tasks.yaml from a spreadsheet on stdin"),
                        ("check", "score the serving model on a labelled sheet on stdin"),
                        ("import", "add a labelled sheet on stdin as training examples")):
        s = sub.add_parser(name, help=help_)
        s.add_argument("--text-column")
        s.add_argument("--label-column")
        s.add_argument("--id-column")
        s.add_argument("--task")
        if name == "init":
            s.add_argument("--force", action="store_true")
        if name == "check":
            s.add_argument("--sample", type=int, default=100)
            s.add_argument("--show", type=int, default=4)
    sub.add_parser("config", help="load a tasks.yaml from stdin")
    for name in ("ready", "wait"):
        s = sub.add_parser(name, help={"ready": "wait until the service answers",
                                       "wait": "follow the training job"}[name])
        s.add_argument("--timeout", type=int, default=100, help="seconds (default 100)")
    sub.add_parser("status", help="what each task serves")
    s = sub.add_parser("train", help="start training on the imported examples")
    s.add_argument("--task")
    s = sub.add_parser("activate", help="serve a trained model (default: the newest)")
    s.add_argument("version", nargs="?")
    s.add_argument("--task")
    s = sub.add_parser("ask", help="the label for a text (also: decider-ai \"text\")")
    s.add_argument("text", nargs="*")
    s.add_argument("--task")
    s.add_argument("--scores", action="store_true")
    return p


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["serve"]:  # the image's CMD; a bare `decider-ai` shows help instead
        from decider.__main__ import main as serve
        return serve()
    if not argv:
        argv = ["--help"]
    if argv[0] not in COMMANDS and not argv[0].startswith("-"):
        argv = ["ask", *argv]
    elif argv[0] in ("--task", "--scores"):
        argv = ["ask", *argv]
    args = parser().parse_args(argv)
    try:
        globals()[f"cmd_{args.cmd}"](args)
    except Fail as e:
        print(f"decider-ai: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
