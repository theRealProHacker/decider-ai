#!/usr/bin/env bash
# T2.6 acceptance tests against a built image.
#   IMAGE=decider-ai:dev tests/container/test_first_start.sh
# Optional: SEED_HF_CACHE=<host HF hub dir holding models--convaiinnovations--laya-multilingual>
# skips the empty-volume download (first test) and seeds volumes from that cache instead.
set -uo pipefail

IMAGE=${IMAGE:-decider-ai:dev}
LIMITS=${DOCKER_LIMITS:---cpus 3 --memory 10g}   # resource limits for service containers
P=dtest$$                       # prefix for volumes and containers
REPO=convaiinnovations/laya-multilingual
REV=1720e3e3357cfe1e281542e223f8273b0890ca34
SHA=9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204
SNAP=/data/hf-cache/models--convaiinnovations--laya-multilingual/snapshots/$REV
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
SENTINEL="sentinel-$RANDOM-zebra-quartz"
fails=0

pass() { echo "PASS  $*"; }
fail() { echo "FAIL  $*"; fails=$((fails + 1)); }
check() { local msg=$1; shift; if "$@"; then pass "$msg"; else fail "$msg"; fi; }

cleanup() {
  docker rm -f $(docker ps -aq --filter "name=^$P") >/dev/null 2>&1
  (cd "$ROOT" && DECIDER_IMAGE=$IMAGE docker compose -p "$P" down -v >/dev/null 2>&1)
  docker volume rm $(docker volume ls -q --filter "name=^$P") >/dev/null 2>&1
}
trap cleanup EXIT

TASKS='tasks:
  - name: route
    question: Which team should handle this message?
    zero_shot: true
    max_input_tokens: 200
    labels:
      billing: Invoices, payments and refunds
      support: Technical problems with the product
'

in_vol() { docker run --rm -i -v "$1:/data" --entrypoint sh "$IMAGE" -c "$2"; }
new_vol() {  # new_vol NAME [seed]: fresh volume with tasks.yaml, optionally the checkpoint copied in
  docker volume create "$1" >/dev/null
  printf '%s' "$TASKS" | in_vol "$1" 'cat > /data/tasks.yaml'
  if [ "${2:-}" = seed ]; then
    docker run --rm -v "$SEED_VOL:/seed:ro" -v "$1:/data" --entrypoint sh "$IMAGE" -c 'cp -a /seed/hf-cache /data/'
  fi
}
wait_live() {  # wait_live CONTAINER SECONDS
  for _ in $(seq "$2"); do
    docker exec "$1" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/live')" \
      >/dev/null 2>&1 && return 0
    [ "$(docker inspect -f '{{.State.Running}}' "$1")" = true ] || return 1
    sleep 1
  done
  return 1
}
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
generated() { docker logs "$1" 2>&1 | grep -c 'Generated API key'; }

# --- 1. first start on an empty volume, key unset, published as documented -----------------
SEED_VOL=${P}seed
if [ -n "${SEED_HF_CACHE:-}" ]; then
  echo "(seeding from $SEED_HF_CACHE; empty-volume download not exercised)"
  new_vol "$SEED_VOL"
  docker run --rm -v "$SEED_HF_CACHE:/host:ro" -v "$SEED_VOL:/data" --entrypoint sh "$IMAGE" \
    -c 'mkdir -p /data/hf-cache && cp -rL /host/models--convaiinnovations--laya-multilingual /data/hf-cache/'
else
  new_vol "$SEED_VOL"
fi
docker run -d $LIMITS --name ${P}a -p 127.0.0.1:8080:8080 -v "$SEED_VOL:/data" "$IMAGE" >/dev/null
check "first start serves (download if empty)" wait_live ${P}a 900
check "generated key printed exactly once" [ "$(generated ${P}a)" = 1 ]
KEY=$(docker logs ${P}a 2>&1 | sed -n 's/.*Generated API key.*: //p' | tr -d '\r')
check "/data/api_key exists and holds the printed key" \
  [ "$(in_vol "$SEED_VOL" 'cat /data/api_key')" = "$KEY" ]
check "checkpoint at pinned revision, sha256 matches" \
  [ "$(in_vol "$SEED_VOL" "sha256sum $SNAP/model.safetensors | cut -d' ' -f1")" = "$SHA" ]
check "host loopback: /health/live -> 200" [ "$(code 127.0.0.1:8080/health/live)" = 200 ]
check "/health/ready with key -> 200" \
  [ "$(code -H "Authorization: Bearer $KEY" 127.0.0.1:8080/health/ready)" = 200 ]
check "/health/ready without key -> 401" [ "$(code 127.0.0.1:8080/health/ready)" = 401 ]

# No text in logs.
d=$(code -X POST -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d "{\"task\":\"route\",\"text\":\"$SENTINEL my invoice\"}" 127.0.0.1:8080/v1/decisions)
f=$(code -X POST -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d "{\"task\":\"route\",\"text\":\"$SENTINEL my invoice\",\"label\":\"billing\",\"external_id\":\"e1\"}" \
  127.0.0.1:8080/v1/feedback)
check "decision and feedback accepted ($d, $f)" [ "$d" = 200 ] && [ "$f" = 200 ]
check "events are logged (decide event present)" bash -c "docker logs ${P}a 2>&1 | grep -q 'decider:'"
check "sentinel text not in docker logs" bash -c "! docker logs ${P}a 2>&1 | grep -q '$SENTINEL'"
docker rm -f ${P}a >/dev/null

# --- 2. second start: no key printed, same key, nothing downloaded ---------------------------
MT1=$(in_vol "$SEED_VOL" "stat -L -c %Y $SNAP/model.safetensors")
docker run -d $LIMITS --name ${P}b -p 127.0.0.1:8080:8080 -v "$SEED_VOL:/data" "$IMAGE" >/dev/null
check "second start serves" wait_live ${P}b 120
check "second start prints no key" [ "$(generated ${P}b)" = 0 ]
check "second start accepts the same key" \
  [ "$(code -H "Authorization: Bearer $KEY" 127.0.0.1:8080/health/ready)" = 200 ]
check "second start downloads nothing" bash -c "! docker logs ${P}b 2>&1 | grep -q Downloading"
check "checkpoint file untouched" [ "$(in_vol "$SEED_VOL" "stat -L -c %Y $SNAP/model.safetensors")" = "$MT1" ]
docker rm -f ${P}b >/dev/null

# --- 3. DECIDER_API_KEY set ------------------------------------------------------------------
new_vol ${P}k seed
docker run -d $LIMITS --name ${P}k -p 127.0.0.1:8080:8080 -e DECIDER_API_KEY=my-own-key -v ${P}k:/data "$IMAGE" >/dev/null
check "env key: serves" wait_live ${P}k 120
check "env key: works" [ "$(code -H 'Authorization: Bearer my-own-key' 127.0.0.1:8080/health/ready)" = 200 ]
check "env key: no key generated" [ "$(generated ${P}k)" = 0 ]
check "env key: no /data/api_key" bash -c "! docker run --rm -v ${P}k:/data --entrypoint test $IMAGE -e /data/api_key"
docker rm -f ${P}k >/dev/null

# --- 4. corrupted checkpoint -----------------------------------------------------------------
new_vol ${P}c seed
in_vol ${P}c "printf garbage | dd of=\$(readlink -f $SNAP/model.safetensors) bs=1 seek=1000 conv=notrunc 2>/dev/null"
out=$(docker run --rm $LIMITS -v ${P}c:/data "$IMAGE" 2>&1); rc=$?
check "corrupt checkpoint: exits non-zero ($rc)" [ $rc -ne 0 ]
check "corrupt checkpoint: names checksum mismatch" grep -q "checksum mismatch" <<<"$out"

# --- 5. offline -------------------------------------------------------------------------------
new_vol ${P}o
out=$(docker run --rm $LIMITS --network none -v ${P}o:/data "$IMAGE" 2>&1); rc=$?
check "offline empty: exits non-zero ($rc)" [ $rc -ne 0 ]
check "offline empty: names checkpoint and pre-download command" \
  bash -c "grep -q '$REPO' <<<\"\$0\" && grep -q 'hf download $REPO --revision $REV' <<<\"\$0\"" "$out"

# Pre-populate with the README command (seeded first so it only verifies, not re-downloads).
new_vol ${P}p seed
docker run --rm -v ${P}p:/data --entrypoint hf "$IMAGE" \
  download $REPO --revision $REV --cache-dir /data/hf-cache >/dev/null 2>&1
check "README pre-download command succeeds" [ $? -eq 0 ]
docker run -d $LIMITS --name ${P}p --network none -v ${P}p:/data "$IMAGE" >/dev/null
check "offline with pre-populated volume: serves" wait_live ${P}p 120
docker rm -f ${P}p >/dev/null

# --- 6. tasks.yaml error ---------------------------------------------------------------------
docker volume create ${P}t >/dev/null
printf 'tasks:\n  - name: x\n    labels: {a: A, b: B}\n    max_input_tokens: 10\n' | in_vol ${P}t 'cat > /data/tasks.yaml'
out=$(docker run --rm $LIMITS -v ${P}t:/data "$IMAGE" 2>&1); rc=$?
check "bad tasks.yaml: exits non-zero ($rc)" [ $rc -ne 0 ]
check "bad tasks.yaml: shows the ConfigError" grep -q "/data/tasks.yaml: task 'x': missing 'question'" <<<"$out"

# --- 7. docker compose sample: curl reaches decider-ai over the shared network ----------------
LOG=$(mktemp)
docker volume create ${P}_decider-data >/dev/null
docker run --rm -v "$SEED_VOL:/seed:ro" -v ${P}_decider-data:/data --entrypoint sh "$IMAGE" \
  -c 'cp -a /seed/tasks.yaml /seed/hf-cache /data/'
(cd "$ROOT" && DECIDER_IMAGE=$IMAGE docker compose -p "$P" up --abort-on-container-exit --exit-code-from curl \
  >"$LOG" 2>&1); rc=$?
check "compose: curl -> http://decider-ai:8080/health/live 200 (rc $rc)" [ $rc -eq 0 ]
(cd "$ROOT" && DECIDER_IMAGE=$IMAGE docker compose -p "$P" down -v >/dev/null 2>&1)
[ $rc -eq 0 ] || cat "$LOG"; rm -f "$LOG"

# --- 8. docs name pinned tags only -----------------------------------------------------------
check "README and compose sample never use :latest" \
  bash -c "! grep -nE ':latest|ghcr.io/[^ ]*decider-ai([^:]|\$)' '$ROOT/README.md' '$ROOT/docker-compose.yml'"

echo
[ $fails -eq 0 ] && echo "ALL PASSED" || echo "$fails FAILED"
exit $fails
