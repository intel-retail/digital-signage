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

copy_directory() {
    local source_dir="$1"
    local target_dir="$2"
    local target_parent

    require_path "$source_dir"
    target_parent="$(dirname "$target_dir")"
    mkdir -p "$target_parent"
    rm -rf "$target_dir"
    cp -a "$source_dir" "$target_dir"
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
MODEL_DOWNLOAD_PORT_KEY="${MODEL_DOWNLOAD_SERVICE_PORT}/tcp"
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
    --volume "$REPO_ROOT/configs/pid/models/object_detection:/opt/models/pid/object_detection"
    --volume "$REPO_ROOT/aig/models:/opt/models/aig/models"
    --volume "$MODEL_DOWNLOAD_CONFIG:/opt/model-download/config/startup-models.yaml:ro"
)

if [[ -n "$HF_TOKEN_VALUE" ]]; then
    DOCKER_ARGS+=(--env "HF_TOKEN=$HF_TOKEN_VALUE" --env "HUGGINGFACEHUB_API_TOKEN=$HF_TOKEN_VALUE")
fi

DOCKER_ARGS+=(
    "$MODEL_DOWNLOAD_IMAGE"
    --plugins "$MODEL_DOWNLOAD_PLUGINS"
)

"${DOCKER_ARGS[@]}" >/dev/null

port_deadline=$((SECONDS + 30))
while true; do
    MODEL_DOWNLOAD_PORT="$(docker inspect --format='{{with index .NetworkSettings.Ports "'"$MODEL_DOWNLOAD_PORT_KEY"'"}}{{(index . 0).HostPort}}{{end}}' "$MODEL_DOWNLOAD_CONTAINER_NAME" 2>/dev/null || true)"
    if [[ -n "$MODEL_DOWNLOAD_PORT" ]]; then
        break
    fi
    if (( SECONDS >= port_deadline )); then
        echo "Failed to determine model-download microservice port" >&2
        docker logs "$MODEL_DOWNLOAD_CONTAINER_NAME" >&2 || true
        exit 1
    fi
    sleep 1
done

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
job_creation_deadline=$((SECONDS + 30))
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

    job_summary="$(
python3 - "$jobs_json" 2>/dev/null <<'PY' || true
import json
import sys

payload = json.loads(sys.argv[1])
jobs = payload.get("jobs", [])
statuses = [job.get("status", "unknown") for job in jobs]
failed = [job for job in jobs if job.get("status") in {"failed", "canceled"}]
completed = sum(status == "completed" for status in statuses)
all_done = bool(jobs) and completed == len(jobs)
print(len(jobs))
print(1 if all_done else 0)
print(json.dumps(failed))
print(", ".join(statuses))
PY
)"
    if [[ -z "$job_summary" ]]; then
        if (( SECONDS >= poll_deadline )); then
            echo "Timed out while waiting for valid startup job status responses" >&2
            docker logs "$MODEL_DOWNLOAD_CONTAINER_NAME" >&2 || true
            exit 1
        fi
        sleep "$MODEL_DOWNLOAD_POLL_INTERVAL_SECONDS"
        continue
    fi
    mapfile -t job_summary_lines <<<"$job_summary"
    job_count="${job_summary_lines[0]:-0}"
    all_done="${job_summary_lines[1]:-0}"
    failed_jobs="${job_summary_lines[2]:-[]}"
    job_statuses="${job_summary_lines[3]:-}"

    if [[ "$job_count" == "0" ]]; then
        if (( SECONDS >= job_creation_deadline )); then
            echo "No startup model jobs were created from $MODEL_DOWNLOAD_CONFIG" >&2
            docker logs "$MODEL_DOWNLOAD_CONTAINER_NAME" >&2 || true
            exit 1
        fi
        sleep "$MODEL_DOWNLOAD_POLL_INTERVAL_SECONDS"
        continue
    fi
    if [[ "$failed_jobs" != "[]" ]]; then
        echo "Model download job failed" >&2
        python3 -m json.tool <<<"$failed_jobs" >&2 || true
        docker logs "$MODEL_DOWNLOAD_CONTAINER_NAME" >&2 || true
        exit 1
    fi

    if [[ "$all_done" == "1" ]]; then
        break
    fi

    if (( SECONDS >= poll_deadline )); then
        echo "Timed out while waiting for startup jobs to finish" >&2
        python3 -m json.tool <<<"$jobs_json" >&2 || true
        docker logs "$MODEL_DOWNLOAD_CONTAINER_NAME" >&2 || true
        exit 1
    fi

    log "Current job summary: ${job_count} job(s): ${job_statuses}"
    sleep "$MODEL_DOWNLOAD_POLL_INTERVAL_SECONDS"
done

log "Normalizing model paths for Digital Signage"
pid_source_dir="$REPO_ROOT/configs/pid/models/object_detection/.model-download/yolo11s/ultralytics/public/yolo11s"
minilm_source_dir="$REPO_ROOT/aig/models/.model-download/all-MiniLM-L12-v2/huggingface/sentence-transformers_all-MiniLM-L12-v2"
sdxl_candidates=(
    "$REPO_ROOT/aig/models/.model-download/sdxl_turbo_ov/openvino_models/CPU/int8/stabilityai/sdxl-turbo"
    "$REPO_ROOT/aig/models/.model-download/sdxl_turbo_ov/openvino_models/cpu/int8/stabilityai/sdxl-turbo"
)
sdxl_matches=()
for candidate in "${sdxl_candidates[@]}"; do
    if [[ -d "$candidate" ]]; then
        sdxl_matches+=("$candidate")
    fi
done

if [[ ! -d "$pid_source_dir" ]]; then
    echo "Expected YOLO11s output was not found at $pid_source_dir" >&2
    exit 1
fi
if (( ${#sdxl_matches[@]} != 1 )); then
    echo "Expected exactly one SDXL-Turbo output directory under $REPO_ROOT/aig/models/.model-download/sdxl_turbo_ov/openvino_models but found ${#sdxl_matches[@]}" >&2
    exit 1
fi
sdxl_source_dir="${sdxl_matches[0]}"
if [[ ! -d "$minilm_source_dir" ]]; then
    echo "Expected MiniLM output was not found at $minilm_source_dir" >&2
    exit 1
fi

copy_directory \
    "$pid_source_dir" \
    "$REPO_ROOT/configs/pid/models/object_detection/yolo11s"
link_directory \
    "$sdxl_source_dir" \
    "$REPO_ROOT/aig/models/sdxl_turbo_ov/int8"
link_directory \
    "$minilm_source_dir" \
    "$REPO_ROOT/aig/models/all-MiniLM-L12-v2"

log "Models are ready for make up"
