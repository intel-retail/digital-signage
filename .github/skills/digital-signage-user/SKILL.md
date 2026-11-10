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
  using the MCP agent tools or video ads, or calling the AIG/ASe REST API with curl. Also use it for vaguer operational phrasings like
  "it isn't working", "nothing shows up", "how do I start this", "which port do I open", or
  "why is my container unhealthy" when the repository is digital-signage. Prefer this skill over
  reading docs/user-guide/ file by file — it carries the deployment procedure, the full
  environment-variable reference, a symptom-driven troubleshooting matrix, and the `make` targets
  for model download and stack health. Works when installed outside the repo: it locates the
  checkout at runtime and follows the published user guide for system requirements and
  prerequisites.
compatibility: >
  Requires a local checkout of the digital-signage repository (its Makefile, .env, docker-compose.yml
  and scripts are read at runtime; the skill itself can be installed anywhere), web access to the
  published user guide (or the checkout's docs/user-guide copy), bash, git, make, curl, Docker Engine
  with Compose v2, and Python 3.
---

# Digital Signage — Deploy and Operate

Bring up, configure, and debug the digital signage stack. This is the operator's skill: it
assumes the goal is a working deployment, not a code change.

**Use `digital-signage-dev` instead** when the task edits Python under `aig/` or `web-ui/`,
adds or changes a REST endpoint, or needs a conforming commit. Editing `.env`, `config.json`,
or `ProductAssociations.csv` is operations and belongs here.

## Path resolution (the skill may be installed outside the repo)

This skill may live in the repo (`.github/skills/digital-signage-user/`) or be installed
standalone into an agent's skills directory (for example with `npx skills add`, which copies only
this skill folder). Paths therefore use three bases:

| Base | Paths | How to resolve |
|---|---|---|
| **Skill directory** (`<skill-dir>`, the folder containing this `SKILL.md`) | `references/…`, `evals/…` | Always bundled with the skill |
| **Repo root** (Step 0) | `Makefile`, `.env`, `docker-compose.yml`, `scripts/…`, `configs/…`, `aig/…`, `web-ui/…`, `docs/user-guide/…` | Read from the user's checkout at runtime; never expected inside `<skill-dir>` |
| **User guide** | Pages linked under "User guide" | Published at <https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-retail/digital-signage/index.html>; page `<page>.html` there is also in the checkout as `docs/user-guide/<page>.md` |

**Step 0 — locate the repo root.** It is the directory containing `Makefile`,
`docker-compose.yml`, `aig/` and `web-ui/`. Resolve it in this order: a path the user gave; cwd
or one of its parents; `git rev-parse --show-toplevel`. Do not derive it from `<skill-dir>`.
`cd` there before any `make` command — the Makefile reads `.env` from the current directory.
If no checkout exists, stop and offer the **Clone the Repository** commands from
[Get Started](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-retail/digital-signage/get-started.html) (`git clone https://github.com/intel-retail/digital-signage`).

## User guide (primary source for prerequisites and procedures)

The application's user guide is the authoritative procedure for system requirements and
prerequisites. Read the relevant page and follow it as written rather than composing your own
sequence. Read it by its published URL, so the skill works from a standalone install, a sparse
checkout, or an agent whose terminal runs on another host. Two exceptions:

- The published guide (`/dev/`) tracks the development branch. If the repo root is on a release
  tag or branch (`git describe --tags --exact-match`, `git branch --show-current`), read
  `docs/user-guide/<page>.md` from the checkout instead, because it matches the `Makefile` you
  are driving.
- If the published site is unreachable (offline host, proxy), read the checkout copy.

Name the source you used (URL or checkout path) in your report.

| Page | Use it for |
|---|---|
| [System requirements](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-retail/digital-signage/get-started/system-requirements.html) | Processor, RAM, storage, GPU, OS, Docker and browser requirements |
| [Get Started](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-retail/digital-signage/get-started.html) | Docker configuration (non-root, proxy, log rotation), clone, build, model download, `.env`, deploy, access, verify |
| [Build from source](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-retail/digital-signage/get-started/build-from-source.html) | `make build` |
| [Change inference device](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-retail/digital-signage/how-to-guides/change-inference-device.html), [Switch simulation video](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-retail/digital-signage/how-to-guides/switch-simulation-video.html), [Configure an RTSP camera](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-retail/digital-signage/how-to-guides/configure-rtsp-camera.html), [Configure predefined ads](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-retail/digital-signage/how-to-guides/configure-predefined-ads.html), [Use a Geti model](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-retail/digital-signage/how-to-guides/use-geti-model.html) | Post-deploy configuration |
| [Troubleshooting](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-retail/digital-signage/troubleshooting.html) | Known runtime issues |
| [API reference](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-retail/digital-signage/api-reference.html) | Documented REST endpoints (not all of them — see `references/api-usage.md`) |

The skill's `references/` carry what the guide does not (full variable reference, symptom matrix,
undocumented endpoints). If the guide and the live `Makefile` disagree, follow the `Makefile` and
mention the discrepancy in your report.

## What the stack is

A video source feeds DL Streamer, which runs YOLO11s object detection and publishes labels to
MQTT. The web UI turns a detected product into an ad — first trying a semantic lookup against
predefined ads in Qdrant, falling back to generating one with SDXL-Turbo — and the browser
polls for it while watching the video over WebRTC. An MCP server inside the web UI container
(reached at `/mcp` through nginx) lets an agent trigger or clear ads, including optional
LTX-Video video ads.

```
video/RTSP → dlstreamer-pipeline-server ─┬─ MQTT topic yolo_od_results ─→ web-ui ─→ aig-server
                                          │                                   ↑         ↓
                                          └─ WebRTC peer-id samplestream      │    ase-qdrant  
                                                     ↓                        │
                                      mediamtx + coturn ──→ nginx (host :5000) ──→ browser
```

Only **two host ports are published: 5000** (nginx, HTTPS, self-signed certificate; also serves
`/mcp`) and **`COTURN_UDP_PORT` (3478)** for WebRTC TURN relay. Both bind to `HOST_IP`
(default `127.0.0.1`, loopback-only). Everything else is internal to the `app_network` bridge.
A `model-download` service exists behind the `model-download` compose profile and only runs
during `make download_models`.

## Fast path

Jump straight to the row that matches. Read only that reference section — the references are
sized so one read answers one question.

| The user says | Go to |
|---|---|
| "how do I get this running", fresh clone, new machine | Path resolution (Step 0) above, then the deployment procedure below, all five steps |
| "make up fails", "models not found", "username unassigned" | `references/troubleshooting.md` § Bring-up failures |
| black / frozen video panel, WebRTC won't connect | `references/troubleshooting.md` § Video panel |
| no ads, ads never change, same ad repeats | `references/troubleshooting.md` § Ads |
| generation takes forever, high memory | `references/troubleshooting.md` § Performance |
| "what does VARIABLE do", "what should I set X to" | `references/env-reference.md` |
| swap video, RTSP camera, CPU/GPU/NPU, Geti model, add ads | `references/customize.md` |
| curl the API, "what endpoints exist", Swagger | `references/api-usage.md` |
| MCP agent tools, `trigger_ad` / `trigger_video_ad`, video ads | `references/customize.md`, `docs/user-guide/how-to-guides/use-mcp-agent-tools.md` |
| model download fails or hangs | `references/troubleshooting.md` § Model download |

## The Makefile is the interface

`Makefile` at the repo root drives everything — prefer a `make` target over
reconstructing the underlying commands, and quote the target to the user rather than a raw
script path. `make help` lists them all.

| Target | Does |
|---|---|
| `make download_models` | Downloads and prepares YOLO11s, SDXL-Turbo, MiniLM (and LTX-Video unless skipped) through the model-download microservice container (`scripts/download_models.sh`) |
| `make build` | Builds all images |
| `make up` | `check_models` → `check_env_variables` → `validate_host_ip` → `down` → `compose up -d` |
| `make status` (alias `make check_stack`) | Stack health: containers, restart counts, recent log errors, endpoint probes (`scripts/check-stack.sh`) |
| `make down` | Stops containers and removes volumes |
| `make build_copyleft_sources` | Builds images including copyleft-licensed sources |
| `make update-submodules`, `make benchmark-*` | Fetch `performance-tools` and run benchmarks — see `docs/user-guide/how-to-guides/benchmarking.md`; not part of deployment |
| `make check_models` / `check_env_variables` / `validate_host_ip` | The individual `make up` preconditions, runnable alone to isolate a failure |

## Deployment procedure

### Step 1 — Prerequisites

Compare the host against [System requirements](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-retail/digital-signage/get-started/system-requirements.html) before
building: Ubuntu 24.04 LTS (26.04 also validated), Docker Engine 24.x or higher with Compose v2, an Intel Core Ultra
(Series 2) or above with at least 16 cores, 16 GB RAM (32 GB recommended), 500 GB free storage,
an Intel iGPU (plus about 8 GB of extra GPU/shared memory, so 32 GB RAM, if video ads are used), Chrome, and internet access for model downloads and image pulls. Check with
`docker --version`, `docker compose version`, `free -g`, `df -h .` and `nproc`, and report any
shortfall as a warning — the stack may still run on lesser hardware, but say so. Also confirm
`curl` and Python 3 are installed (the model download script needs both).

Then follow **Configure Docker** in [Get Started](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-retail/digital-signage/get-started.html): run Docker as non-root,
configure the Docker proxy if the host needs one, and enable log rotation. Verify with
`docker info >/dev/null 2>&1`. If it fails, **stop**, report the host blocker, and point the
user to that section rather than retrying.

For GPU or NPU inference the host needs `/dev/dri` or `/dev/accel` populated — the Makefile
probes for these at parse time and silently substitutes `/dev/null` when absent, so a missing
device shows up later as an OpenVINO device error rather than a mount failure.

Behind a corporate proxy, configure Docker's daemon proxy *and* export `http_proxy`,
`https_proxy`, `no_proxy` before building — compose forwards them as build args.

### Step 2 — Download the models

`make up` refuses to start unless `make check_models` finds the YOLO11s, SDXL-Turbo and MiniLM
artifacts. Use the make target rather than reconstructing the commands, and have the user
review the YOLO11s and SDXL-Turbo licenses linked in Get Started first (downloading is not
license acceptance):

```bash
make download_models
```

It pulls the pinned `intel/model-download` image (`MODEL_DOWNLOAD_IMAGE`), starts it on
`MODEL_DOWNLOAD_PORT` (8000), and submits jobs that quantize YOLO11s into
`configs/pid/models/object_detection/yolo11s/`, export SDXL-Turbo to OpenVINO INT8 in
`aig/models/sdxl_turbo_ov/int8/`, and fetch MiniLM into `aig/models/all-MiniLM-L12-v2/`. It
skips everything when all artifacts already exist, so re-running is cheap; to redo a model,
delete its directory first. Expect tens of minutes on a first run, mostly the SDXL export.

The optional LTX-Video model (`aig/models/ltx_video_ov/int8`, only for `trigger_video_ad`) is
exported too unless `SKIP_LTX_VIDEO_EXPORT` is set (it defaults to on under `CI`); it is long
and large, so ask before including it. `make check_models` does not require it.

Failures are almost always network, proxy or disk: the script prints the model-download
container logs on error. See `references/troubleshooting.md` § Model download.

### Step 3 — Configure `.env`

Three variables gate `make up`. The repo ships the two WebRTC credentials **empty**, so a
fresh clone always fails here first — set them before anything else:

| Variable | Rule enforced by `make check_env_variables` |
|---|---|
| `MTX_WEBRTCICESERVERS2_0_USERNAME` | letters only, at least 5 (`^[A-Za-z]{5,}$`) |
| `MTX_WEBRTCICESERVERS2_0_PASSWORD` | alphanumeric, at least 8, with at least one digit **and** one letter |
| `HOST_IP` | a dotted-quad IPv4 with every octet 0–255; default `127.0.0.1`. **`localhost` is rejected** |

`HOST_IP=127.0.0.1` only works when the browser runs on the same machine, because the published
ports bind to that address. To reach the UI from another device, set the host's real IPv4 and
recreate the containers with `make up` — it also sets the TURN server URL the browser uses, so
a loopback value is the usual cause of "UI unreachable" or remote WebRTC failure.

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
`scripts/check-stack.sh`: it checks the eight long-running containers this
compose file declares (not the on-demand `model-download` one), reports restart counts, scans recent logs, and probes the web
UI, AIG health, Swagger and current-ad endpoints at the address nginx is bound to. It exits non-zero on failure, so it is also usable as a gate in a
script or CI step.

Then open **`https://localhost:5000`** in Chrome (or `https://<HOST_IP>:5000` remotely, with `HOST_IP` set to that address). The
self-signed certificate produces a browser warning; proceed past it. `/portrait` serves the
portrait-orientation layout.

A healthy first view shows the detection video within a few seconds and the first ad within
roughly `TIME_TO_DISPLAY_AD_SECONDS` after a product is detected. The very first dynamic ad is
slower than steady state because the model compiles on first use (about 3 minutes on the NPU, which
is experimental and image-ads only).

Stop with `make down`, which also removes volumes — including the Qdrant volumes, so
predefined ads are re-created from `ProductAssociations.csv` / the sample data on the next start.

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
`docs/user-guide/api-reference.md` documents only a subset of the REST endpoints
(`references/api-usage.md` has the full list), and the MCP tools are documented separately in
`docs/user-guide/how-to-guides/use-mcp-agent-tools.md`. If a user hits one of these, tell them it
is a repo gap, not their mistake.

## Answer contract when blocked

A failing prerequisite that the user guide documents how to fix (for example `make up` refusing
to start because the models are missing, or the WebRTC credentials being empty) is **not** a
blocker: apply the documented procedure, then continue.

Real blockers are conditions you cannot or must not fix yourself: no repo checkout, Docker
unreachable, unsupported hardware, a model download or image build that fails (network, proxy,
disk), or `.env` credentials the user has not chosen. In those cases **do not stall**: state the
blocker plainly, cite the user-guide section that covers it, show the exact command sequence the
user would run once unblocked, and stop. Never invent "it worked" output.
