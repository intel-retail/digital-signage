#!/usr/bin/env bash

# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DOWNLOAD_IMAGE="${MODEL_DOWNLOAD_IMAGE:-intel/model-download:latest@sha256:5d7607a8d8c184602eae5bfc5a9bd1783e204da65a6adee8e467677e7f668849}"
MODEL_DOWNLOAD_CONFIG="${MODEL_DOWNLOAD_CONFIG:-$REPO_ROOT/configs/model-download/startup-models.yaml}"
MODEL_DOWNLOAD_CONTAINER_NAME="${MODEL_DOWNLOAD_CONTAINER_NAME:-digital-signage-model-download}"
MODEL_DOWNLOAD_PLUGINS="${MODEL_DOWNLOAD_PLUGINS:-huggingface,openvino,ultralytics}"
MODEL_DOWNLOAD_TIMEOUT_SECONDS="${MODEL_DOWNLOAD_TIMEOUT_SECONDS:-7200}"
MODEL_DOWNLOAD_POLL_INTERVAL_SECONDS="${MODEL_DOWNLOAD_POLL_INTERVAL_SECONDS:-10}"
MODEL_DOWNLOAD_SERVICE_PORT=8000
EXPECTED_JOB_COUNT=3

HF_TOKEN_VALUE="${HUGGINGFACEHUB_API_TOKEN:-${HF_TOKEN:-}}"
MODEL_DOWNLOAD_PORT=""

cleanup() {
    if [[ -n "${MODEL_DOWNLOAD_CONTAINER_NAME}" ]]; then
        docker rm -f "${MODEL_DOWNLOAD_CONTAINER_NAME}" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

log() {
    echo "[model-download] $*"
}

require_path() {
    local path="$1"
    if [[ ! -e "$path" ]]; then
        echo "Required path not found: $path" >&2
        exit 1
    fi
}

link_directory() {
    local source_dir="$1"
    local target_dir="$2"
    local target_parent
    local target_name
    local relative_source

    require_path "$source_dir"
    target_parent="$(dirname "$target_dir")"
    target_name="$(basename "$target_dir")"
    mkdir -p "$target_parent"
    relative_source="$(python3 - <<'PY' "$source_dir" "$target_parent"
import os
import sys
print(os.path.relpath(sys.argv[1], sys.argv[2]))
PY
)"
    rm -rf "$target_dir"
    (
        cd "$target_parent"
        ln -sfn "$relative_source" "$target_name"
    )
}

mkdir -p \
    "$REPO_ROOT/configs/pid/models/object_detection/.model-download" \
    "$REPO_ROOT/aig/models/.model-download" \
    "$REPO_ROOT/aig/models/sdxl_turbo_ov"
require_path "$MODEL_DOWNLOAD_CONFIG"

log "Starting model-download microservice container"
DOCKER_ARGS=(
    docker run -d --rm
    --name "$MODEL_DOWNLOAD_CONTAINER_NAME"
    --publish "0:${MODEL_DOWNLOAD_SERVICE_PORT}"
    --env "STARTUP_MODELS_CONFIG=/opt/model-download/config/startup-models.yaml"
    --env "HF_HUB_ENABLE_HF_TRANSFER=1"
    --env "http_proxy=${http_proxy:-}"
    --env "https_proxy=${https_proxy:-}"
    --env "no_proxy=${no_proxy:-}"
    --env "HTTP_PROXY=${HTTP_PROXY:-${http_proxy:-}}"
    --env "HTTPS_PROXY=${HTTPS_PROXY:-${https_proxy:-}}"
    --env "NO_PROXY=${NO_PROXY:-${no_proxy:-}}"
    --volume "$REPO_ROOT:/opt/models"
    --volume "$MODEL_DOWNLOAD_CONFIG:/opt/model-download/config/startup-models.yaml:ro"
)

if [[ -n "$HF_TOKEN_VALUE" ]]; then
    DOCKER_ARGS+=(--env "HF_TOKEN=$HF_TOKEN_VALUE")
fi

DOCKER_ARGS+=(
    "$MODEL_DOWNLOAD_IMAGE"
    --plugins "$MODEL_DOWNLOAD_PLUGINS"
)

"${DOCKER_ARGS[@]}" >/dev/null

MODEL_DOWNLOAD_PORT="$(docker port "$MODEL_DOWNLOAD_CONTAINER_NAME" "${MODEL_DOWNLOAD_SERVICE_PORT}/tcp" | head -1 | cut -d: -f2)"
if [[ -z "$MODEL_DOWNLOAD_PORT" ]]; then
    echo "Failed to determine model-download microservice port" >&2
    docker logs "$MODEL_DOWNLOAD_CONTAINER_NAME" >&2 || true
    exit 1
fi

MODEL_DOWNLOAD_URL="http://localhost:${MODEL_DOWNLOAD_PORT}"
log "Waiting for service health at ${MODEL_DOWNLOAD_URL}/health"

health_deadline=$((SECONDS + 180))
until curl -fsS "${MODEL_DOWNLOAD_URL}/health" >/dev/null 2>&1; do
    if (( SECONDS >= health_deadline )); then
        echo "Timed out waiting for model-download microservice health check" >&2
        docker logs "$MODEL_DOWNLOAD_CONTAINER_NAME" >&2 || true
        exit 1
    fi
    sleep 3
done

log "Polling startup model jobs"
poll_deadline=$((SECONDS + MODEL_DOWNLOAD_TIMEOUT_SECONDS))
while true; do
    jobs_json="$(curl -fsS "${MODEL_DOWNLOAD_URL}/jobs" || true)"
    if [[ -z "$jobs_json" ]]; then
        if (( SECONDS >= poll_deadline )); then
            echo "Timed out while waiting for startup jobs" >&2
            docker logs "$MODEL_DOWNLOAD_CONTAINER_NAME" >&2 || true
            exit 1
        fi
        sleep "$MODEL_DOWNLOAD_POLL_INTERVAL_SECONDS"
        continue
    fi

    job_summary="$(python3 - <<'PY' "$jobs_json" "$EXPECTED_JOB_COUNT"
import json
import sys

payload = json.loads(sys.argv[1])
expected = int(sys.argv[2])
jobs = payload.get("jobs", [])
statuses = [job.get("status", "unknown") for job in jobs]
failed = [job for job in jobs if job.get("status") in {"failed", "canceled"}]
completed = sum(status == "completed" for status in statuses)
all_done = len(jobs) >= expected and statuses and completed == len(jobs)
print(json.dumps({
    "count": len(jobs),
    "statuses": statuses,
    "completed": completed,
    "all_done": all_done,
    "failed": failed,
}, sort_keys=True))
PY
)"

    failed_jobs="$(python3 - <<'PY' "$job_summary"
import json
import sys
print(json.dumps(json.loads(sys.argv[1]).get("failed", [])))
PY
)"
    if [[ "$failed_jobs" != "[]" ]]; then
        echo "Model download job failed" >&2
        python3 -m json.tool <<<"$failed_jobs" >&2 || true
        docker logs "$MODEL_DOWNLOAD_CONTAINER_NAME" >&2 || true
        exit 1
    fi

    if python3 - <<'PY' "$job_summary"
import json
import sys
sys.exit(0 if json.loads(sys.argv[1]).get("all_done") else 1)
PY
    then
        break
    fi

    if (( SECONDS >= poll_deadline )); then
        echo "Timed out while waiting for startup jobs to finish" >&2
        python3 -m json.tool <<<"$job_summary" >&2 || true
        docker logs "$MODEL_DOWNLOAD_CONTAINER_NAME" >&2 || true
        exit 1
    fi

    log "Current job summary: $(python3 - <<'PY' "$job_summary"
import json
import sys
summary = json.loads(sys.argv[1])
print(f'{summary["count"]} job(s): {", ".join(summary["statuses"])}')
PY
)"
    sleep "$MODEL_DOWNLOAD_POLL_INTERVAL_SECONDS"
done

log "Normalizing model paths for Digital Signage"
link_directory \
    "$REPO_ROOT/configs/pid/models/object_detection/.model-download/yolo11s/ultralytics/public/yolo11s" \
    "$REPO_ROOT/configs/pid/models/object_detection/yolo11s"
link_directory \
    "$REPO_ROOT/aig/models/.model-download/sdxl_turbo_ov/openvino_models/cpu/int8/stabilityai/sdxl-turbo" \
    "$REPO_ROOT/aig/models/sdxl_turbo_ov/int8"
link_directory \
    "$REPO_ROOT/aig/models/.model-download/all-MiniLM-L12-v2/huggingface/sentence-transformers_all-MiniLM-L12-v2" \
    "$REPO_ROOT/aig/models/all-MiniLM-L12-v2"

log "Models are ready for make up"
