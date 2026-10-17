# decider-ai

decider-ai is a self-hosted container that classifies short texts into the labels you define, starts from a zero-shot model, and learns from the decisions you confirm. Licensed under Apache-2.0.

## Results

Fine-tuned on 250 labels, decider-ai costs about €0.003–0.004 per 1,000 decisions on a CPU and answers faster than Gemini 3.5 Flash-Lite (p95 345–626 ms vs 695–805 ms). It is less accurate: zero-shot Gemini scores 10–15 macro-F1 points higher.

| Dataset | decider-ai, 250 labels | Gemini 3.5 Flash-Lite, zero-shot | TF-IDF + LR, 250 labels |
|---|---|---|---|
| MASSIVE 1.1 de-DE, 18 scenarios | F1 0.717 · €0.0043 / 1,000 · p95 626 ms | F1 0.864 · €0.0808 / 1,000 · p95 805 ms | F1 0.619 |
| CLINC150, 10 domains + out-of-scope | F1 0.734 · €0.0027 / 1,000 · p95 345 ms | F1 0.836 · €0.0766 / 1,000 · p95 695 ms | F1 0.588 |

Measured on one laptop CPU (Intel Core Ultra 7 258V), priced at a Hetzner CX43's €0.0256 per hour of busy time, mean of 5 seeds, on a seeded 1,000-record sample of each official test set. Full report, method and confidence intervals: [reports/gate-20261008-0543/report.md](reports/gate-20261008-0543/report.md).

## Host

- x86-64 with AVX2, 4 or more vCPUs, 16 GB RAM. Training peaks at about 8.5 GB of memory.
- Disk: about 678 MB for the base checkpoint plus about 678 MB per kept model version.
- Only one retrain job runs at a time. Decisions are still answered while it trains.

Things to know:

- The `predictions` scores are not calibrated probabilities. Use them to rank labels, not as confidence.
- Deleting an example removes it from the data, but a trained model keeps what it learned from it until you retrain and activate the new version.

## Run

Images are published to GHCR under pinned version tags. Always use a version tag such as `v0.3.1`; never `latest`. Replace `OWNER` below with the GitHub owner of this repository.

1. Put a `tasks.yaml` (see below) into a volume:

   ```sh
   docker volume create decider-data
   docker run --rm -i -v decider-data:/data --entrypoint sh ghcr.io/OWNER/decider-ai:v0.3.1 \
     -c 'cat > /data/tasks.yaml' < tasks.yaml
   ```

2. Start the container, published to host loopback only:

   ```sh
   docker run -d --name decider-ai -p 127.0.0.1:8080:8080 -v decider-data:/data \
     ghcr.io/OWNER/decider-ai:v0.3.1
   docker logs decider-ai   # the generated API key is printed once, on first start
   ```

   Set `-e DECIDER_API_KEY=...` to choose the key yourself. Otherwise one is generated on first start, printed once and stored in `/data/api_key`. Every route except `GET /health/live` needs `Authorization: Bearer <key>`.

3. Check it: `curl 127.0.0.1:8080/health/live`, then `curl -H "Authorization: Bearer <key>" 127.0.0.1:8080/health/ready`.

The volume holds everything: `tasks.yaml`, `api_key`, `decider.db`, `models/` and `hf-cache/`. Backing it up is your responsibility.

### Set it up with an AI agent

Give Claude Code (or any agent that can run Docker) your spreadsheet and this line:

```
Set up decider-ai with my data: run `docker run --rm ghcr.io/therealprohacker/decider-ai:v0.3.1 guide` and follow it.
```

It creates the task from your columns, starts the container, tests the untrained model on your rows, shows what it gets right and wrong, and trains and activates only when you say so. At the end you can type:

```sh
decider-ai "Do you have a free trial?"
```

### The `decider-ai` command

The image's entrypoint is a small command. With no arguments it starts the service; inside a running container it talks to that service with the key from the volume:

| Command | Does |
|---|---|
| `docker run --rm IMAGE guide` | Setup steps for an agent |
| `docker run --rm -i -v decider-data:/data IMAGE init < FILE` | Write `tasks.yaml` from a sheet |
| `docker exec -i decider-ai decider-ai check < FILE` | Score the serving model on a labelled sheet |
| `docker exec -i decider-ai decider-ai import < FILE` | Add a sheet as training examples |
| `docker exec decider-ai decider-ai train`, then `wait` | Train and follow the job |
| `docker exec decider-ai decider-ai activate` | Serve the newest trained model |
| `docker exec decider-ai decider-ai "text"` | The label for a text (`--scores` for all) |

With `alias decider-ai='docker exec -i decider-ai decider-ai'` these become `decider-ai check < FILE`, `decider-ai "text"` and so on.

### Import a spreadsheet

`POST /v1/examples:batch` also takes a CSV (UTF-8, `,` `;` or tab) or an xlsx file (first sheet). The first row holds the column names:

```sh
curl -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" \
  --data-binary @tickets.xlsx \
  "127.0.0.1:8080/v1/examples:batch?task=route&text_column=Message&label_column=Team&id_column=Ticket"
```

Without an ID column, the text is the ID, so importing the same sheet again updates rows instead of adding them. Use `Content-Type: text/csv` for CSV.

### Base checkpoint and offline hosts

The image does not contain the model. On first start it downloads `convaiinnovations/laya-multilingual` at revision `1720e3e3357cfe1e281542e223f8273b0890ca34` (about 680 MB, Apache-2.0) into `/data/hf-cache` and checks its sha256. Later starts download nothing. If the file is corrupted, the container stops with a checksum mismatch; delete `/data/hf-cache` and start again.

For a host without internet access, fill the volume on a machine that has it, then move the volume over:

```sh
docker run --rm -v decider-data:/data --entrypoint hf ghcr.io/OWNER/decider-ai:v0.3.1 \
  download convaiinnovations/laya-multilingual \
  --revision 1720e3e3357cfe1e281542e223f8273b0890ca34 --cache-dir /data/hf-cache
```

Without Docker, the same with the Hugging Face CLI: `hf download convaiinnovations/laya-multilingual --revision 1720e3e3357cfe1e281542e223f8273b0890ca34 --cache-dir <volume>/hf-cache`.

### Using it from n8n

Do not publish the port to your network. Put n8n and decider-ai on one Docker network and call `http://decider-ai:8080`. [`docker-compose.yml`](docker-compose.yml) shows the wiring, with a `curl` service standing in for n8n; attach your n8n service to the `decider` network the same way.

## tasks.yaml

```yaml
tasks:
  - name: route
    question: Which team should handle this message?
    max_input_tokens: 200        # optional; lowers the input limit
    labels:                      # label names only: fine for tasks you train
      billing:
      support:
      sales:
      other:
  - name: urgent
    question: Does this message need a reply today?
    zero_shot: true              # serve the base model before any training
    labels:                      # zero_shot needs a one-line description per label
      "yes": The sender is blocked or a deadline is today
      "no": Everything else
```

- Label descriptions are optional. They are required only with `zero_shot: true`.
- The question plus all label options must fit the model's 256-token budget, or the container refuses to start and names the task. With label names only, roughly 30–60 labels fit; with descriptions, roughly 10–18.
- A task's labels are fixed for its name. Changing them makes the container refuse to start; use a new task name instead.
- Quote labels such as `"yes"`, `"no"`, `"true"` and `"false"`, or YAML reads them as booleans.
