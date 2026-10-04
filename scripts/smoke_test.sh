#!/usr/bin/env bash
# Builds the app image and drives it the way the Supervisor would: options in
# /data/options.json, storage under /share. Needs podman or docker, and network
# access for the base image and a ~1 MB test model.
set -euo pipefail

cd "$(dirname "$0")/.."

ENGINE="${ENGINE:-$(command -v podman || command -v docker)}"
IMAGE="llama-cpp-app:smoke"
NAME="llama-cpp-app-smoke"
PORT="${PORT:-18080}"
MODEL_URL="https://huggingface.co/ggml-org/models/resolve/main/tinyllamas/stories260K.gguf"

work="$(mktemp -d)"
cleanup() {
    "$ENGINE" rm -f "$NAME" >/dev/null 2>&1 || true
    rm -rf "$work"
}
trap cleanup EXIT

fail() {
    echo "FAIL: $*" >&2
    "$ENGINE" logs "$NAME" 2>&1 | tail -30 >&2 || true
    exit 1
}

start() {
    "$ENGINE" rm -f "$NAME" >/dev/null 2>&1 || true
    printf '%s' "$1" > "$work/data/options.json"
    "$ENGINE" run -d --name "$NAME" -p "127.0.0.1:${PORT}:8080" \
        -v "$work/data:/data:z" -v "$work/share:/share:z" "$IMAGE" >/dev/null
}

wait_healthy() {
    for _ in $(seq 1 60); do
        if curl -fs "http://127.0.0.1:${PORT}/health" >/dev/null; then return 0; fi
        sleep 1
    done
    fail "server did not become healthy"
}

# Runs the image's own health check, the way the container engine would.
healthcheck() {
    "$ENGINE" exec "$NAME" /usr/bin/python3 /usr/lib/llama-app/healthcheck.py
}

chat() {
    curl -fsS "http://127.0.0.1:${PORT}/v1/chat/completions" "${@:2}" \
        -H 'Content-Type: application/json' \
        -d "{\"model\":\"$1\",\"max_tokens\":8,\"messages\":[{\"role\":\"user\",\"content\":\"Once upon a time\"}]}"
}

# podman drops HEALTHCHECK instructions unless it writes the docker format.
BUILDAH_FORMAT=docker "$ENGINE" build -q -t "$IMAGE" llama_cpp >/dev/null

"$ENGINE" image inspect "$IMAGE" | grep -q 'healthcheck.py' \
    || fail "image has no health check configured"

mkdir -p "$work/data" "$work/share/llama_cpp/models"
curl -fsSL -o "$work/share/llama_cpp/models/stories260K.gguf" "$MODEL_URL"

echo "== single model, API key required"
start '{"model":"stories260K.gguf","context_size":512,"gpu_layers":"0","api_key":"smoke-key"}'
wait_healthy
code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/v1/models")"
[ "$code" = 401 ] || fail "request without the key returned $code, expected 401"
chat stories260K -H 'Authorization: Bearer smoke-key' | grep -q '"content"' \
    || fail "no completion in single-model mode"
"$ENGINE" logs "$NAME" 2>&1 | grep -q 'smoke-key' && fail "API key leaked into the log"
# /health is exempt from the key, or the check would fail on every keyed install.
[ "$(healthcheck)" = "HTTP 200" ] || fail "health check failed with an API key set"

echo "== router mode, model picked per request"
start '{"model":""}'
wait_healthy
curl -fsS "http://127.0.0.1:${PORT}/v1/models" | grep -q 'stories260K' \
    || fail "router does not list the model in the models directory"
chat stories260K | grep -q '"content"' || fail "no completion in router mode"
[ "$(healthcheck)" = "HTTP 200" ] || fail "health check failed in router mode"

echo "== web UI is served"
curl -fsS --compressed -H 'Accept-Encoding: gzip' "http://127.0.0.1:${PORT}/" | grep -q '<html' \
    || fail "web UI not served"

echo "== a bad option stops the container with a clear message"
start '{"model":"not-a-model"}'
for _ in $(seq 1 20); do
    [ "$("$ENGINE" inspect -f '{{.State.Running}}' "$NAME")" = false ] && break
    sleep 0.5
done
[ "$("$ENGINE" inspect -f '{{.State.ExitCode}}' "$NAME")" = 1 ] || fail "bad model did not exit 1"
"$ENGINE" logs "$NAME" 2>&1 | grep -q 'neither a .gguf file' || fail "bad model not explained"

echo "PASS"
