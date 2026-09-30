#!/usr/bin/env bash

# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DOWNLOAD_PLUGINS="${MODEL_DOWNLOAD_PLUGINS:-huggingface,openvino,ultralytics}"
MODEL_DOWNLOAD_TIMEOUT_SECONDS="${MODEL_DOWNLOAD_TIMEOUT_SECONDS:-7200}"
MODEL_DOWNLOAD_POLL_INTERVAL_SECONDS="${MODEL_DOWNLOAD_POLL_INTERVAL_SECONDS:-10}"
MODEL_DOWNLOAD_PORT="${MODEL_DOWNLOAD_PORT:-8000}"
MODEL_DOWNLOAD_COMPOSE_FILE="$REPO_ROOT/docker-compose.yml"
MODEL_DOWNLOAD_URL="http://127.0.0.1:${MODEL_DOWNLOAD_PORT}/api/v1"

HF_TOKEN_VALUE="${HUGGINGFACEHUB_API_TOKEN:-${HF_TOKEN:-}}"

log() {
    echo "[model-download] $*"
}

models_ready() {
    [[ -s "$REPO_ROOT/configs/pid/models/object_detection/yolo11s/INT8/yolo11s.xml" && \
       -s "$REPO_ROOT/configs/pid/models/object_detection/yolo11s/INT8/yolo11s.bin" && \
       -s "$REPO_ROOT/aig/models/sdxl_turbo_ov/int8/graph.pbtxt" && \
       -s "$REPO_ROOT/aig/models/all-MiniLM-L12-v2/config.json" ]]
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
require_path "$MODEL_DOWNLOAD_COMPOSE_FILE"

if models_ready; then
    log "All required model artifacts already exist; skipping downloads"
    exit 0
fi
# New model directories must inherit the host group for non-root container writes.
MODEL_DOWNLOAD_HOST_GID="$(id -g)"
export MODEL_DOWNLOAD_HOST_GID
chmod g+rwx,g+s \
    "$REPO_ROOT/configs/pid/models/object_detection" \
    "$REPO_ROOT/configs/pid/models/object_detection/.model-download" \
    "$REPO_ROOT/aig/models" \
    "$REPO_ROOT/aig/models/.model-download"

log "Starting model-download microservice container"
if [[ -z "${MODEL_DOWNLOAD_CA_BUNDLE+x}" ]]; then
    for ca_bundle in /etc/ssl/certs/ca-certificates.crt /etc/pki/tls/certs/ca-bundle.crt; do
        if [[ -f "$ca_bundle" ]]; then
            export MODEL_DOWNLOAD_CA_BUNDLE="$ca_bundle"
            break
        fi
    done
fi
if [[ -n "${HF_TOKEN_VALUE}" ]]; then
    export HUGGINGFACEHUB_API_TOKEN="${HUGGINGFACEHUB_API_TOKEN:-$HF_TOKEN_VALUE}"
fi

export MODEL_DOWNLOAD_PORT
compose=(docker compose --project-directory "$REPO_ROOT" --profile model-download -f "$MODEL_DOWNLOAD_COMPOSE_FILE")
log "Pulling model-download image"
if ! "${compose[@]}" pull model-download; then
    echo "Failed to pull model-download image" >&2
    exit 1
fi
if ! "${compose[@]}" up -d model-download; then
    "${compose[@]}" logs --no-color model-download >&2 || true
    exit 1
fi

log "Waiting for service health at ${MODEL_DOWNLOAD_URL}/health"

health_deadline=$((SECONDS + 180))
until curl -fsS "${MODEL_DOWNLOAD_URL}/health" >/dev/null 2>&1; do
    if [[ -z "$("${compose[@]}" ps --status running --quiet model-download)" ]]; then
        echo "model-download service exited before becoming healthy" >&2
        "${compose[@]}" logs --no-color model-download >&2 || true
        exit 1
    fi
    if (( SECONDS >= health_deadline )); then
        echo "Timed out waiting for model-download microservice health check" >&2
        "${compose[@]}" logs --no-color model-download >&2 || true
        exit 1
    fi
    sleep 3
done

log "Submitting model download jobs"
poll_deadline=$((SECONDS + MODEL_DOWNLOAD_TIMEOUT_SECONDS))
download_paths=(
    "pid/object_detection/.model-download/yolo11s"
    "aig/models/.model-download/sdxl_turbo_ov"
    "aig/models/.model-download/all-MiniLM-L12-v2"
)
request_bodies=(
    '{"models":[{"name":"yolo11s","hub":"ultralytics","type":"vision","config":{"quantize":"coco128"}}]}'
    '{"models":[{"name":"stabilityai/sdxl-turbo","hub":"openvino","type":"image_generation","is_ovms":true,"config":{"precision":"int8","device":"CPU"}}]}'
    '{"models":[{"name":"sentence-transformers/all-MiniLM-L12-v2","hub":"huggingface","type":"embeddings"}]}'
)
job_ids=()
for index in "${!download_paths[@]}"; do
    download_path="${download_paths[$index]}"
    request_body="${request_bodies[$index]}"
    if ! response="$(curl --connect-timeout 5 --max-time 30 -fsS -X POST \
        -H "Content-Type: application/json" \
        -d "$request_body" "${MODEL_DOWNLOAD_URL}/models/download?download_path=${download_path}")"; then
        echo "Failed to submit model download for $download_path" >&2
        "${compose[@]}" logs --no-color model-download >&2 || true
        exit 1
    fi
    job_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["job_ids"][0])' <<<"$response")"
    job_ids+=("$job_id")
    log "Submitted $download_path (job $job_id)"
done

while (( ${#job_ids[@]} > 0 )); do
    remaining=()
    statuses=()
    for job_id in "${job_ids[@]}"; do
        if ! job="$(curl --connect-timeout 5 --max-time 15 -fsS "${MODEL_DOWNLOAD_URL}/jobs/${job_id}" 2>/dev/null)"; then
            if [[ -z "$("${compose[@]}" ps --status running --quiet model-download)" ]]; then
                echo "model-download service exited while jobs were running" >&2
                "${compose[@]}" logs --no-color model-download >&2 || true
                exit 1
            fi
            remaining+=("$job_id")
            statuses+=("unavailable")
            continue
        fi
        status="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("status", "unknown"))' <<<"$job")"
        case "$status" in
            completed) ;;
            failed|canceled)
                echo "Model download job $job_id ended with status: $status" >&2
                python3 -m json.tool <<<"$job" >&2 || true
                "${compose[@]}" logs --no-color model-download >&2 || true
                exit 1
                ;;
            *)
                remaining+=("$job_id")
                statuses+=("$status")
                ;;
        esac
    done
    job_ids=("${remaining[@]}")
    if (( ${#job_ids[@]} > 0 )); then
        if (( SECONDS >= poll_deadline )); then
            echo "Timed out waiting for model download jobs" >&2
            "${compose[@]}" logs --no-color model-download >&2 || true
            exit 1
        fi
        log "Jobs still running: ${statuses[*]}"
        sleep "$MODEL_DOWNLOAD_POLL_INTERVAL_SECONDS"
    fi
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

"${compose[@]}" rm --stop --force model-download >/dev/null

log "Models are ready for make up"
