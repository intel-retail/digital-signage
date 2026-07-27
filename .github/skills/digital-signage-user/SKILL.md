---
name: digital-signage-user
description: >
  Deploy, configure, verify and troubleshoot the Context-Aware Cross-Selling Digital Signage
  stack. Use this skill whenever the user is trying to *run* the demo rather than change its
  code: first-time bring-up on a new machine, downloading or converting the YOLO11s / SDXL-Turbo /
  MiniLM models, filling in `.env`, a failing `make up` or `make build`, containers restarting or
  exiting, a black or frozen video panel in the browser, ads that never appear or never change,
  slow image generation, switching inference between CPU/GPU/NPU, swapping the simulation video,
  pointing the pipeline at an RTSP camera, adding predefined ads, deploying a custom Geti model,
  or calling the AIG/ASe REST API with curl. Also use it for vaguer operational phrasings like
  "it isn't working", "nothing shows up", "how do I start this", "which port do I open", or
  "why is my container unhealthy" when the repository is digital-signage. Prefer this skill over
  reading docs/user-guide/ file by file — it carries the deployment procedure, the full
  environment-variable reference, a symptom-driven troubleshooting matrix, and the `make` targets
  for model download and stack health.
---

# Digital Signage — Deploy and Operate

Bring up, configure, and debug the digital signage stack. This is the operator's skill: it
assumes the goal is a working deployment, not a code change.

**Use `digital-signage-dev` instead** when the task edits Python under `aig/` or `web-ui/`,
adds or changes a REST endpoint, or needs a conforming commit. Editing `.env`, `config.json`,
or `ProductAssociations.csv` is operations and belongs here.

## What the stack is

A video source feeds DL Streamer, which runs YOLO11s object detection and publishes labels to
MQTT. The web UI turns a detected product into an ad — first trying a semantic lookup against
predefined ads in ChromaDB, falling back to generating one with SDXL-Turbo — and the browser
polls for it while watching the video over WebRTC.

```
video/RTSP → dlstreamer-pipeline-server ─┬─ MQTT topic yolo_od_results ─→ web-ui ─→ aig-server
                                          │                                   ↑         ↓
                                          └─ WebRTC peer-id samplestream      │    ase-chromadb
                                                     ↓                        │
                                      mediamtx + coturn ──→ nginx (host :5000) ──→ browser
```

Only **one host port is exposed: 5000**, served by nginx over HTTPS with a self-signed
certificate. Everything else is internal to the `app_network` bridge. `COTURN_UDP_PORT` (3478)
is also published for WebRTC TURN relay.

## Fast path

Jump straight to the row that matches. Read only that reference section — the references are
sized so one read answers one question.

| The user says | Go to |
|---|---|
| "how do I get this running", fresh clone, new machine | Deployment procedure below, all five steps |
| "make up fails", "models not found", "username unassigned" | `references/troubleshooting.md` § Bring-up failures |
| black / frozen video panel, WebRTC won't connect | `references/troubleshooting.md` § Video panel |
| no ads, ads never change, same ad repeats | `references/troubleshooting.md` § Ads |
| generation takes forever, high memory | `references/troubleshooting.md` § Performance |
| "what does VARIABLE do", "what should I set X to" | `references/env-reference.md` |
| swap video, RTSP camera, CPU/GPU/NPU, Geti model, add ads | `references/customize.md` |
| curl the API, "what endpoints exist", Swagger | `references/api-usage.md` |

## The Makefile is the interface

[Makefile](../../../Makefile) at the repo root drives everything — prefer a `make` target over
reconstructing the underlying commands, and quote the target to the user rather than a raw
script path. `make help` lists them all.

| Target | Does |
|---|---|
| `make download_models` | Downloads and prepares YOLO11s, SDXL-Turbo and MiniLM (`scripts/download-models.sh`) |
| `make download_models_pid` / `make download_models_aig` | Just the detection half / just the AIG half |
| `make ... FORCE=1` | Re-download even when the target directory is already populated |
| `make build` | Builds all images |
| `make up` | `check_models` → `check_env_variables` → `validate_host_ip` → `down` → `compose up -d` |
| `make status` (alias `make check_stack`) | Stack health: containers, restart counts, recent log errors, endpoint probes (`scripts/check-stack.sh`) |
| `make down` | Stops containers and removes volumes |
| `make check_models` / `check_env_variables` / `validate_host_ip` | The individual `make up` preconditions, runnable alone to isolate a failure |

## Deployment procedure

### Step 1 — Prerequisites

Docker Engine with the Compose plugin, Python 3, and roughly 40 GB free disk (the SDXL-Turbo
export is large and the build pulls a DL Streamer image). For GPU or NPU inference the host
needs `/dev/dri` or `/dev/accel` populated — the Makefile probes for these at parse time and
silently substitutes `/dev/null` when absent, so a missing device shows up later as an
OpenVINO device error rather than a mount failure.

Behind a corporate proxy, configure Docker's daemon proxy *and* export `http_proxy`,
`https_proxy`, `no_proxy` before building — compose forwards them as build args.

### Step 2 — Download the models

`make up` refuses to start unless both `configs/pid/models/` and `aig/models/` exist and are
non-empty. Use the make target rather than reconstructing the commands:

```bash
make download_models
```

It downloads and quantizes YOLO11s into `configs/pid/models/object_detection/yolo11s/`, exports
SDXL-Turbo to OpenVINO INT8 in `aig/models/sdxl_turbo_ov/int8/`, and fetches the MiniLM
embedding model into `aig/models/all-MiniLM-L12-v2/`. It is idempotent — an already-populated
target is skipped unless you add `FORCE=1` — and `make download_models_pid` /
`make download_models_aig` redo just one half. Expect tens of minutes on a first run, mostly
the SDXL export.

The target runs [scripts/download-models.sh](../../../scripts/download-models.sh), which
replaces a long copy-paste block still duplicated in `docs/user-guide/get-started.md` and the
CI workflow. If the target fails, that block is the fallback, but prefer fixing the script.

### Step 3 — Configure `.env`

Three variables gate `make up`. The repo ships the two WebRTC credentials **empty**, so a
fresh clone always fails here first — set them before anything else:

| Variable | Rule enforced by `make check_env_variables` |
|---|---|
| `MTX_WEBRTCICESERVERS2_0_USERNAME` | letters only, at least 5 (`^[A-Za-z]{5,}$`) |
| `MTX_WEBRTCICESERVERS2_0_PASSWORD` | alphanumeric, at least 8, with at least one digit **and** one letter |
| `HOST_IP` | `localhost`, or a dotted-quad IPv4 with every octet 0–255 |

`HOST_IP=localhost` only works when the browser runs on the same machine. To reach the UI from
another device, set the host's real IP — it is baked into the TURN server URL that the browser
uses, so leaving it as `localhost` is the usual cause of remote WebRTC failure.

Everything else has a working default. `references/env-reference.md` covers all of them,
including several where the code's `os.getenv` fallback disagrees with the shipped `.env` value.

### Step 4 — Build and start

```bash
make build
make up
```

`make up` runs `check_models`, `check_env_variables`, `validate_host_ip`, then `down`, then
`docker compose up -d`. Because it always tears down first, `make up` is also the way to
restart after a config change — `.env` and `config.json` are read at container start, so
edits need a full `make up`, not a `docker restart`.

### Step 5 — Verify

```bash
make status
```

`status` (alias `check_stack`) runs
[scripts/check-stack.sh](../../../scripts/check-stack.sh): it checks the eight containers this
compose file actually declares, reports restart counts, scans recent logs, and probes the web
UI and AIG health endpoints. It exits non-zero on failure, so it is also usable as a gate in a
script or CI step.

Then open **`https://localhost:5000`** in Chrome (or `https://<HOST_IP>:5000` remotely). The
self-signed certificate produces a browser warning; proceed past it. `/portrait` serves the
portrait-orientation layout.

A healthy first view shows the detection video within a few seconds and the first ad within
roughly `TIME_TO_DISPLAY_AD_SECONDS` after a product is detected. The very first dynamic ad is
slower than steady state because the model compiles on first use.

Stop with `make down`, which also removes volumes — including the ChromaDB volume, so
predefined ads are re-seeded from `ProductAssociations.csv` on the next start.

## Reference lookup

Each reference answers one class of question. Read one, not all.

| Reference | Read it for |
|---|---|
| `references/env-reference.md` | Any question about a variable's meaning, default, validation, or which service consumes it |
| `references/troubleshooting.md` | Any symptom — build, startup, video, ads, performance |
| `references/customize.md` | Changing input source, inference device, models, or ad content |
| `references/api-usage.md` | Calling AIG/ASe endpoints directly, or when a UI symptom needs to be isolated to the API |

## Working style

Diagnose before prescribing. Most reported symptoms have several plausible causes and the
stack makes them cheap to distinguish: `make status` separates "container is dead" from
"container is fine but returning nothing", and a direct `curl` against the AIG API
(`references/api-usage.md`) separates "generation is broken" from "the browser isn't getting
it". Ask for the output of one of those before guessing.

When the fix is an `.env` or `config.json` edit, say explicitly that it needs `make up` to take
effect — operators lose a lot of time editing a file and reloading the browser.

Be honest about the known rough edges rather than working around them silently:
`docs/user-guide/get-started.md` still spells out the model download by hand instead of using
`make download_models`, and `docs/user-guide/api-reference.md` documents four of the nine REST
endpoints. If a user hits one of these, tell them it is a repo gap, not their mistake.
