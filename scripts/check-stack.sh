#!/usr/bin/env bash
#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Health check for the digital signage stack. Backs `make status` / `make check_stack`.
#
# Reports container state and restart counts, scans recent logs, and probes the AIG API and
# web UI so a live container that returns nothing is distinguishable from a dead one.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# The containers docker-compose.yml actually declares, in dependency order.
CONTAINERS=(
    mqtt-broker
    ase-chromadb
    mediamtx
    coturn
    dlstreamer-pipeline-server
    aig-server
    web-ui
    nginx_proxy
)

LOG_LINES=30
LOG_PATTERN='error|exception|traceback|fatal|refused|no such file'
# Noise that appears in healthy runs and would otherwise bury real failures.
LOG_IGNORE='GST_DEBUG|error_resilient|--error|errorlevel|0 errors'

RED=$'\033[1;31m'; GREEN=$'\033[1;32m'; YELLOW=$'\033[1;33m'; BLUE=$'\033[1;34m'; RESET=$'\033[0m'

FAILURES=0
WARNINGS=0

hdr()  { printf '\n%s== %s ==%s\n' "${BLUE}" "$*" "${RESET}"; }
ok()   { printf '  %sok%s    %s\n'   "${GREEN}"  "${RESET}" "$*"; }
bad()  { printf '  %sFAIL%s  %s\n'   "${RED}"    "${RESET}" "$*"; FAILURES=$((FAILURES+1)); }
warn() { printf '  %swarn%s  %s\n'   "${YELLOW}" "${RESET}" "$*"; WARNINGS=$((WARNINGS+1)); }

command -v docker >/dev/null 2>&1 || { echo "docker is not installed or not on PATH" >&2; exit 2; }

# A stack that was never started produces eight identical "not created" lines, which buries
# the one thing the user needs to know. Detect that case up front.
EXISTING=0
for name in "${CONTAINERS[@]}"; do
    docker inspect "${name}" >/dev/null 2>&1 && EXISTING=$((EXISTING+1))
done

if [[ "${EXISTING}" -eq 0 ]]; then
    printf '\n%sNone of the digital signage containers exist.%s\n' "${YELLOW}" "${RESET}"
    printf 'The stack has not been started. From %s:\n\n' "${REPO_ROOT}"
    printf '  1. make download_models\n'
    printf '  2. set MTX_WEBRTCICESERVERS2_0_USERNAME and _PASSWORD in .env\n'
    printf '  3. make build && make up\n\n'
    exit 1
fi

hdr "Containers"

RUNNING_COUNT=0
for name in "${CONTAINERS[@]}"; do
    # Query each container by exact name; missing ones produce empty output rather than an error.
    info="$(docker inspect --format '{{.State.Status}}|{{.State.Restarting}}|{{.RestartCount}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}-{{end}}' "${name}" 2>/dev/null)"

    if [[ -z "${info}" ]]; then
        bad "${name} — not created (is the stack up? run 'make up')"
        continue
    fi

    IFS='|' read -r status restarting restarts health <<<"${info}"
    detail="${status}"
    [[ "${health}" != "-" ]] && detail="${detail}, health=${health}"
    [[ "${restarts}" != "0" ]] && detail="${detail}, restarts=${restarts}"

    case "${status}" in
        running)
            RUNNING_COUNT=$((RUNNING_COUNT+1))
            if [[ "${restarting}" == "true" ]]; then
                bad "${name} — restart loop (${detail})"
            elif [[ "${restarts}" -gt 2 ]]; then
                warn "${name} — running but has restarted ${restarts} times"
            elif [[ "${health}" == "unhealthy" ]]; then
                bad "${name} — unhealthy"
            else
                ok "${name} (${detail})"
            fi
            ;;
        restarting) bad "${name} — restart loop (${detail})" ;;
        exited)     bad "${name} — exited (${detail}); see 'docker logs ${name}'" ;;
        *)          warn "${name} — ${detail}" ;;
    esac
done

if [[ "${RUNNING_COUNT}" -eq 0 ]]; then
    printf '\n%sNothing is running.%s Start the stack with:  cd %s && make up\n' \
        "${YELLOW}" "${RESET}" "${REPO_ROOT}"
    exit 1
fi

hdr "Recent log errors (last ${LOG_LINES} lines per container)"

FOUND_LOG_ERRORS=0
for name in "${CONTAINERS[@]}"; do
    docker inspect "${name}" >/dev/null 2>&1 || continue
    hits="$(docker logs --tail "${LOG_LINES}" "${name}" 2>&1 \
            | grep -Ei "${LOG_PATTERN}" \
            | grep -Eiv "${LOG_IGNORE}" \
            | head -5)"
    if [[ -n "${hits}" ]]; then
        FOUND_LOG_ERRORS=1
        printf '  %s%s%s\n' "${YELLOW}" "${name}" "${RESET}"
        sed 's/^/      /' <<<"${hits}"
    fi
done
[[ "${FOUND_LOG_ERRORS}" -eq 0 ]] && ok "no error patterns in recent logs"

hdr "Endpoints"

# Read the published UI port from compose rather than assuming 5000.
UI_PORT="$(docker port nginx_proxy 2>/dev/null | awk -F: '/->|15443/ {print $NF; exit}')"
UI_PORT="${UI_PORT:-5000}"
BASE="https://localhost:${UI_PORT}"

probe() {
    local label="$1" url="$2" expect="$3"
    local code
    code="$(curl -k -s -o /dev/null -w '%{http_code}' --max-time 10 "${url}" 2>/dev/null)"
    if [[ "${code}" == "000" ]]; then
        bad "${label} — no response from ${url}"
    elif [[ ",${expect}," == *",${code},"* ]]; then
        ok "${label} — HTTP ${code}"
    else
        warn "${label} — HTTP ${code} (expected ${expect}) at ${url}"
    fi
}

if command -v curl >/dev/null 2>&1; then
    probe "web UI          " "${BASE}/" "200"
    probe "AIG health      " "${BASE}/aig-api/aig/hstatus/1" "200"
    probe "Swagger UI      " "${BASE}/swaggerui/" "200,301,302"
    # 204 is a healthy answer here: it means this client already holds the current ad.
    probe "current ad      " "${BASE}/get_current_advertisement?width=1920&height=1080&client_id=check-stack" "200,204"
else
    warn "curl not installed — skipping endpoint probes"
fi

hdr "Summary"

if [[ "${FAILURES}" -eq 0 && "${WARNINGS}" -eq 0 ]]; then
    printf '  %sStack is healthy.%s Open %s in Chrome (accept the self-signed certificate).\n' \
        "${GREEN}" "${RESET}" "${BASE}"
    exit 0
fi

printf '  %d failure(s), %d warning(s)\n' "${FAILURES}" "${WARNINGS}"
printf '  Next steps: docker logs <container>, then see\n'
printf '  .github/skills/digital-signage-user/references/troubleshooting.md\n'
[[ "${FAILURES}" -gt 0 ]] && exit 1
exit 0
