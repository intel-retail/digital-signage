#!/usr/bin/env bash
#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Download and prepare every model the digital signage stack needs:
#
#   configs/pid/models/object_detection/yolo11s/   YOLO11s, quantized to INT8 (detection)
#   aig/models/sdxl_turbo_ov/int8/                 SDXL-Turbo, OpenVINO INT8 (ad generation)
#   aig/models/all-MiniLM-L12-v2/                  Sentence embeddings (semantic ad search)
#
# `make up` refuses to start unless configs/pid/models and aig/models are both non-empty.
#
# Idempotent: an already-populated target is skipped unless --force is given.
#
# Normally invoked through the Makefile: `make download_models`, `make download_models_pid`,
# `make download_models_aig`, optionally with FORCE=1.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PID_MODEL_DIR="${REPO_ROOT}/configs/pid/models/object_detection/yolo11s"
SDXL_DIR="${REPO_ROOT}/aig/models/sdxl_turbo_ov/int8"
MINILM_DIR="${REPO_ROOT}/aig/models/all-MiniLM-L12-v2"

# Pinned so a moving upstream default cannot silently change what gets downloaded.
ASC_REF="v3.6.3"
ASC_SCRIPT_URL="https://raw.githubusercontent.com/intel-retail/automated-self-checkout/${ASC_REF}/download_models/downloadAndQuantizeModel.sh"
YOLO_MODEL_NAME="yolo11s"
SDXL_MODEL_ID="stabilityai/sdxl-turbo"
MINILM_MODEL_ID="sentence-transformers/all-MiniLM-L12-v2"

DO_PID=1
DO_AIG=1
FORCE=0

usage() {
    cat <<'EOF'
Download the digital signage models.

Usage: scripts/download-models.sh [OPTIONS]
   or: make download_models [FORCE=1]

Options:
  --pid-only    Only the YOLO11s detection model (configs/pid/models/)   [make download_models_pid]
  --aig-only    Only the SDXL-Turbo and MiniLM models (aig/models/)      [make download_models_aig]
  --force       Re-download even if the target directory already has content  [FORCE=1]
  -h, --help    Show this help

Targets:
  configs/pid/models/object_detection/yolo11s/   YOLO11s INT8, object detection
  aig/models/sdxl_turbo_ov/int8/                 SDXL-Turbo INT8, ad image generation
  aig/models/all-MiniLM-L12-v2/                  MiniLM embeddings, semantic ad search

Notes:
  Expect tens of minutes on a first run; the SDXL-Turbo export dominates.
  Requires python3 with venv, git, wget and roughly 30 GB of free disk.
  Behind a proxy, export http_proxy / https_proxy / no_proxy before running.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --pid-only) DO_AIG=0; shift ;;
        --aig-only) DO_PID=0; shift ;;
        --force)    FORCE=1;  shift ;;
        -h|--help)  usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

log()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m warning: %s\033[0m\n' "$*" >&2; }
die()  { printf '\033[1;31m error: %s\033[0m\n' "$*" >&2; exit 1; }

# A directory counts as "already downloaded" only if it exists and holds something.
# This mirrors what `make check_models` tests, so a pass here means `make up` will pass too.
has_content() {
    [[ -d "$1" ]] && [[ -n "$(ls -A "$1" 2>/dev/null)" ]]
}

should_skip() {
    local dir="$1" label="$2"
    if [[ "${FORCE}" -eq 0 ]] && has_content "${dir}"; then
        log "${label}: already present at ${dir#"${REPO_ROOT}/"} — skipping (use --force to redo)"
        return 0
    fi
    return 1
}

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "'$1' is required but not installed."
}

download_pid_model() {
    should_skip "${PID_MODEL_DIR}" "YOLO11s" && return 0

    log "Downloading and quantizing ${YOLO_MODEL_NAME} (detection)"
    require_cmd wget
    require_cmd python3

    local workdir="${REPO_ROOT}/configs/pid"
    local script="${workdir}/downloadAndQuantizeModel.sh"
    local venv="${workdir}/.modelenv"

    # The upstream script defaults to /workspace/models and yolo11n; retarget both.
    wget -q -O "${script}" "${ASC_SCRIPT_URL}" \
        || die "Could not fetch ${ASC_SCRIPT_URL} (proxy configured?)"
    sed -i 's|MODELS_PATH="${MODELS_DIR:-/workspace/models}"|MODELS_PATH="${MODELS_DIR:-$PWD/models}"|g' "${script}"
    sed -i "s/MODEL_NAME=\"yolo11n\"/MODEL_NAME=\"${YOLO_MODEL_NAME}\"/g" "${script}"
    chmod +x "${script}"

    rm -rf "${venv}"
    python3 -m venv "${venv}"
    # shellcheck disable=SC1091
    source "${venv}/bin/activate"
    pip3 install --quiet --upgrade pip
    pip3 install --quiet -r "${workdir}/model_download_requirements.txt"

    # Only wipe the old models once we are committed to producing new ones.
    rm -rf "${workdir}/models"
    ( cd "${workdir}" && ./downloadAndQuantizeModel.sh )

    deactivate
    rm -f "${script}"
    rm -rf "${venv}"

    has_content "${PID_MODEL_DIR}" \
        || die "Detection model missing after download; expected ${PID_MODEL_DIR}"
    log "Detection model ready: ${PID_MODEL_DIR#"${REPO_ROOT}/"}"
}

download_aig_models() {
    local need_sdxl=1 need_minilm=1
    should_skip "${SDXL_DIR}"   "SDXL-Turbo" && need_sdxl=0
    should_skip "${MINILM_DIR}" "MiniLM"     && need_minilm=0
    [[ "${need_sdxl}" -eq 0 && "${need_minilm}" -eq 0 ]] && return 0

    log "Preparing AIG models (this is the slow part)"
    require_cmd python3

    local workdir="${REPO_ROOT}/aig"
    local venv="${workdir}/.modelenv"

    rm -rf "${venv}"
    python3 -m venv "${venv}"
    # shellcheck disable=SC1091
    source "${venv}/bin/activate"
    pip3 install --quiet --upgrade pip
    pip3 install --quiet -r "${workdir}/export-requirements.txt"

    export HF_HUB_ENABLE_HF_TRANSFER=1

    if [[ "${need_sdxl}" -eq 1 ]]; then
        log "Exporting ${SDXL_MODEL_ID} to OpenVINO INT8"
        rm -rf "${SDXL_DIR}"
        ( cd "${workdir}" && optimum-cli export openvino \
            --model "${SDXL_MODEL_ID}" \
            --task stable-diffusion-xl \
            --weight-format int8 \
            ./models/sdxl_turbo_ov/int8 )
    fi

    if [[ "${need_minilm}" -eq 1 ]]; then
        log "Downloading ${MINILM_MODEL_ID}"
        rm -rf "${MINILM_DIR}"
        ( cd "${workdir}" && huggingface-cli download "${MINILM_MODEL_ID}" \
            --local-dir ./models/all-MiniLM-L12-v2 )
    fi

    deactivate
    rm -rf "${venv}"

    has_content "${SDXL_DIR}"   || die "SDXL-Turbo missing after export; expected ${SDXL_DIR}"
    has_content "${MINILM_DIR}" || die "MiniLM missing after download; expected ${MINILM_DIR}"
    log "AIG models ready under aig/models/"
}

# `make check_models` only tests that these two directories are non-empty, which a partial
# download also satisfies. Verify the specific artifacts so a half-finished run fails here
# rather than as an opaque OpenVINO error at inference time.
verify() {
    log "Verifying"
    local ok=1

    if [[ "${DO_PID}" -eq 1 ]]; then
        if has_content "${PID_MODEL_DIR}"; then
            echo "  ok    detection  ${PID_MODEL_DIR#"${REPO_ROOT}/"}"
            find "${PID_MODEL_DIR}" -name '*.xml' -print -quit | grep -q . \
                || warn "no .xml found under ${PID_MODEL_DIR} — the IR may be incomplete"
        else
            echo "  FAIL  detection  ${PID_MODEL_DIR#"${REPO_ROOT}/"} is missing or empty"; ok=0
        fi
    fi

    if [[ "${DO_AIG}" -eq 1 ]]; then
        for d in "${SDXL_DIR}" "${MINILM_DIR}"; do
            if has_content "${d}"; then
                echo "  ok    aig        ${d#"${REPO_ROOT}/"}"
            else
                echo "  FAIL  aig        ${d#"${REPO_ROOT}/"} is missing or empty"; ok=0
            fi
        done
    fi

    [[ "${ok}" -eq 1 ]] || die "Verification failed. Re-run with 'make download_models FORCE=1'."
    log "All requested models are in place. Next: set the .env credentials, then 'make build && make up'."
}

[[ "${DO_PID}" -eq 1 ]] && download_pid_model
[[ "${DO_AIG}" -eq 1 ]] && download_aig_models
verify
