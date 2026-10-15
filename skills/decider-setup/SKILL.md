---
name: decider-setup
description: Set up decider-ai (self-hosted text classifier container) from a spreadsheet or CSV of labelled messages - writes tasks.yaml, starts the container, measures the zero-shot model on the sheet, reports good and bad examples, and fine-tunes only when the user says so. Use when the user has an Excel/CSV file of texts with labels (categories, teams, queues) and wants decider-ai running on it, or asks to "set up decider", "classify these messages locally" or "train decider on this file".
---

# Set up decider-ai from a spreadsheet

Goal: the user hands over a sheet and ends with a running container, a measured zero-shot model and a clear yes/no question about fine-tuning. Do the work; ask only where this file says to ask.

Rules that never bend:
- Never activate a model without the user's yes in chat. decider-ai never retrains or activates on its own, and this skill must not either.
- Never print message text from the sheet beyond the handful of good/bad examples in the report.
- The container listens on `127.0.0.1` only.

Image: `ghcr.io/therealprohacker/decider-ai:v0.2.0` or newer (spreadsheet import arrived in v0.2.0) (use a local image instead if the user names one). Container name `decider-ai`, volume `decider-data`. If either already exists, ask before reusing or replacing it: it holds the user's data.

## 1. Read the sheet

Look at the header and a few rows (xlsx: `uvx --with openpyxl python -c ...` or any tool at hand; first sheet only). Find:
- the **text column** (the message) and the **label column** (the answer),
- an **ID column** if one exists (ticket number, message ID). Without one, the text is the ID.

If the choice is ambiguous, show the header and ask once. Count rows per label. Drop nothing yet.

Tell the user, in a few lines: rows, labels with counts, and anything that limits training:
- training needs at least 50 rows; a reliable verdict needs 150+ with about 10 per label,
- labels with fewer than 10 rows will hold back the verdict.

## 2. Write tasks.yaml

One task. Name it from the label column in lower snake case (e.g. `team`). Write a one-line question that a person would answer with the label. Labels are fixed once the container has started under this task name, so use exactly the label values from the sheet; quote `"yes"`, `"no"`, `"true"`, `"false"`, numbers.

Zero-shot needs `zero_shot: true` and a short description per label. Write each from the label name plus a look at its rows: what messages with this label are about, in the sheet's language, at most about 8 words. Example:

```yaml
tasks:
  - name: team
    question: Which team should handle this message?
    zero_shot: true
    labels:
      billing: Invoices, payments, refunds
      support: Something is broken or unclear
      sales: Buying, prices, upgrades
```

The question plus all descriptions must fit 256 tokens; roughly 10-18 labels fit with descriptions. With more labels, skip zero-shot (`zero_shot: false`, label names only), tell the user why, and go to step 6 after the import.

## 3. Start the container

```sh
docker volume create decider-data
docker run --rm -i -v decider-data:/data --entrypoint sh IMAGE -c 'cat > /data/tasks.yaml' < tasks.yaml
docker run -d --name decider-ai -p 127.0.0.1:8080:8080 -v decider-data:/data IMAGE
```

The first start downloads the base model (about 680 MB). Poll `docker logs decider-ai` until uvicorn is up, then read the API key from the `Generated API key` line (or `/data/api_key`). Keep it in a shell variable, never in a file in the user's project. Check `curl -H "Authorization: Bearer $KEY" 127.0.0.1:8080/health/ready`.

If the container exits naming the task, the 256-token budget was exceeded: shorten the descriptions, rewrite `/data/tasks.yaml` the same way, `docker start decider-ai`.

## 4. Measure zero-shot

Use `check.py` next to this file. It runs inside the container:

```sh
docker cp SHEET decider-ai:/tmp/sheet.EXT
docker exec -i decider-ai python - /tmp/sheet.EXT --task TASK --text-column TEXT --label-column LABEL < check.py
docker exec decider-ai rm /tmp/sheet.EXT
```

It samples up to 200 rows, skips rows whose label is not in the task, and prints accuracy, macro-F1, recall per label, the top confusions and five right and five wrong decisions.

## 5. Report and ask

Report briefly:
- accuracy and macro-F1 of the untrained model on N rows,
- which labels it gets right and which it confuses, in plain words,
- 2-3 good and 2-3 bad examples (short excerpts, the label, the model's answer).

If one label's description is clearly the cause of a confusion, you may improve the description once, restart and re-measure; say that you did.

Then ask: **fine-tune on the sheet?** Say what it costs: one training job of roughly an hour per 250 rows on a laptop CPU, about 8.5 GB RAM at peak, decisions keep being answered while it trains. Stop and wait for the answer.

## 6. Import and fine-tune (only after a yes)

```sh
curl -sS -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" \
  --data-binary @SHEET \
  "127.0.0.1:8080/v1/examples:batch?task=TASK&text_column=TEXT&label_column=LABEL&id_column=ID"
```

CSV: `Content-Type: text/csv` (UTF-8; `,` `;` or tab). Rows come in as `label_mode: blind`. Count the `outcomes`; report rejected rows grouped by `code` (e.g. `LABEL_NOT_IN_TASK`, `INPUT_TOO_LONG`) without echoing their text.

Then `POST /v1/retrain {"task": TASK}` and poll `GET /v1/jobs/{id}` every few minutes, reporting `epoch/epochs` when it changes. Training survives your session ending; tell the user how to check the job themselves.

## 7. Verdict and activation

When the job has `state: succeeded`, show `verdict` and `metrics`:
- `recommended` / `not_recommended`: compared with the active model on the frozen split (with its confidence interval).
- `unverified`: too few rows for a frozen split; the model is unmeasured.

Re-run step 4 only as a rough sanity check and say it overlaps the training data. Ask whether to activate; on yes, `POST /v1/tasks/TASK/models/VERSION/activate` and show any `warning`.

## 8. Hand over

End with: the URL, where the key is (`/data/api_key` in the volume), one `curl` example for `/v1/decisions`, how to send corrections (`POST /v1/feedback`), and that the volume is theirs to back up.
