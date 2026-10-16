# decider-ai setup guide (for an AI agent)

You are setting up decider-ai for the user: a local service that routes short texts (tickets, mails, messages) to one of a fixed set of labels, learned from a spreadsheet of past examples. Follow these steps in order. Every command below works as written; replace only FILE with the path of the user's file.

Rules:
- Never activate a trained model without the user's yes in chat.
- Do not print message text from the user's file beyond the few examples the commands show.
- The service listens on 127.0.0.1 only. The API key stays in the Docker volume; you never need it.

## 1. The file

Use the spreadsheet the user gave you (xlsx or CSV, first row = column names). If they gave none, ask for it and stop. If a container `decider-ai` or a volume `decider-data` already exists, ask before touching it: it holds the user's data.

## 2. Create the task from the file

```sh
docker volume create decider-data
docker run --rm -i -v decider-data:/data {image} init < FILE
```

It picks the text, label and ID columns, writes `tasks.yaml` into the volume and prints it plus the label counts. If it picked the wrong columns, rerun with `--text-column NAME --label-column NAME` (and `--id-column NAME`), adding `--force`.

A specific question and label descriptions make the untrained model better. Save the printed YAML as `tasks.yaml`, replace the generic question with one a person would answer with the label (e.g. "Which team should handle this ticket?"), and replace each description (now just the label name) with a short phrase of at most 8 words about what messages with that label are about, then load it:

```sh
docker run --rm -i -v decider-data:/data {image} config < tasks.yaml
```

## 3. Start the service

```sh
docker run -d --name decider-ai --restart unless-stopped -p 127.0.0.1:8080:8080 -v decider-data:/data {image}
docker exec decider-ai decider-ai ready
```

The first start downloads the base model (about 680 MB). `ready` waits up to 100 seconds; if it says not up yet, run it again. If the container stops, `docker logs decider-ai` says why. If it names the task's token budget, shorten the descriptions, load them with `config` and `docker start decider-ai`.

## 4. Test the untrained model

```sh
docker exec -i decider-ai decider-ai check < FILE
```

It takes about a minute and prints how often the untrained model is right on up to 100 rows, per label, the most common mix-ups and a few right and wrong examples.

## 5. Report and ask

Tell the user in a few lines: how often it is right, which labels work and which get mixed up, two right and two wrong examples. Then ask whether to train on their file. Training takes roughly an hour per 250 rows on a laptop CPU and needs about 8.5 GB of RAM; the service keeps answering meanwhile. Stop and wait for the answer.

If they say no, go to step 8: the untrained model is already serving.

## 6. Train (only after a yes)

```sh
docker exec -i decider-ai decider-ai import < FILE
docker exec decider-ai decider-ai train
docker exec decider-ai decider-ai wait
```

`import` needs at least 50 rows for training. `wait` follows the job for up to 100 seconds and prints progress and the time left; while it says "Still training", run it again (between runs, tell the user the progress; there is no need to wait in between). Training keeps running if you stop waiting; `docker exec decider-ai decider-ai status` shows it.

## 7. Activate (only after a yes)

`wait` ends with the trained model's result. Tell the user and ask whether to serve it. On yes:

```sh
docker exec decider-ai decider-ai activate
```

If your permission system blocks this command, do not work around it: give the user the command to run themselves.

## 8. Hand over

Add this line to the user's shell profile (`~/.bashrc` or `~/.zshrc`, whichever their shell uses) and tell them you did:

```sh
alias decider-ai='docker exec -i decider-ai decider-ai'
```

Then they can type `decider-ai "Do you have a free trial?"` and get the label back. Show them one example with a made-up message, and mention:
- `decider-ai --scores "..."` shows every label's score (a ranking, not a probability).
- `decider-ai status` shows what is serving.
- Programs call `POST http://127.0.0.1:8080/v1/decisions` with `Authorization: Bearer <key>`; the key is in the volume: `docker exec decider-ai cat /data/api_key`.
- The volume `decider-data` holds everything; backing it up is theirs.
