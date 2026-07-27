---
name: digital-signage-dev
description: >
  Modify the code of the Context-Aware Cross-Selling Digital Signage application. Use this skill
  whenever the task changes Python under `aig/` or `web-ui/`, or the runtime configuration those
  services depend on: adding or changing a Flask-RESTX REST endpoint on the AIG or ASe API,
  touching image generation or the SDXL-Turbo model-loading path, editing ChromaDB storage or
  semantic search, changing the overlay drawing code (price, promo, logo, slogan, frame),
  altering how the web UI picks products or cross-sell variants, adjusting MQTT detection
  filtering, changing the ad polling contract, editing the GStreamer pipeline in
  `configs/pid/config.json`, or changing nginx routing. Also use it when the request is to
  understand how part of this codebase works before changing it — "where does the ad selection
  happen", "why is price ignored", "how do I add an endpoint" — and when preparing a commit or
  PR for this repository, which requires a signed-off conventional commit. Prefer this skill
  over reading the source cold; it maps the architecture, the established patterns, and the
  live-API validation loop this repo uses in place of unit tests.
---

# Digital Signage — Development

Change the code of the digital signage application, following the patterns already established
in it.

**Use `digital-signage-user` instead** when the goal is to run, configure, or debug a
deployment without changing code — model downloads, `.env`, `make up` failures, blank video, no
ads. Editing `.env` or `ProductAssociations.csv` is operations. Editing `config.json` or nginx
routing lands here, because those changes usually accompany a code change.

## Architecture at a glance

```
configs/pid/config.json          GStreamer pipeline: decode → gvadetect (YOLO11s) → appsink
        │
        ├── MQTT topic yolo_od_results ──→ web-ui/main.py
        │                                    MQTTSubscriber  filters by recency + confidence
        │                                    Ad_Generator    picks product, builds payload
        │                                         │
        │                                         ├─1─→ POST /ase/predef/query/ad   (predefined, 5s)
        │                                         └─2─→ POST /aig/minf/             (generate, 400s)
        │                                                        │
        │                                              aig/src/server/apis/
        │                                              ├── predefinedads.py → ase-chromadb
        │                                              └── modelinf.py      → SDXL-Turbo
        │
        └── WebRTC peer-id samplestream ──→ mediamtx ──→ nginx ──→ browser
```

The web UI always tries the predefined-ad lookup first and falls back to generation. Both paths
converge on the same overlay vocabulary (`price_details`, `promo_details`, `logo_details`,
`slogan_details`, `framed_details`), which is why a change to one overlay usually needs the
matching change in the other.

Eight containers, one published port: nginx on host `5000` (container 15443, HTTPS). Everything
else is internal to `app_network`.

## Where to work

Read the one reference that matches. They are sized so a single read answers the question.

| The task touches | Read |
|---|---|
| A REST endpoint, request/response schema, Swagger | `references/aig-service.md` |
| SDXL-Turbo loading, device selection, generation retries | `references/aig-service.md` |
| ChromaDB storage, semantic search, distance filtering | `references/aig-service.md` |
| Overlay drawing — price, promo, logo, slogan, frame | `references/aig-service.md` |
| Product selection, variant rotation, ad cadence | `references/web-ui-service.md` |
| MQTT detection filtering, label normalization | `references/web-ui-service.md` |
| The browser polling contract, templates, client ids | `references/web-ui-service.md` |
| GStreamer pipeline, detection model, MQTT/WebRTC payload | `references/pipeline-and-config.md` |
| nginx routes, TLS, upstreams, compose wiring | `references/pipeline-and-config.md` |
| Service boundaries, ports, volumes, startup order | `references/architecture.md` |

When a change spans services — most endpoint changes do, because the web UI is the only caller —
read `architecture.md` first to see the seam, then the two service references.

## Conventions

[AGENTS.md](../../../AGENTS.md) is the authority on repository conventions and is already in
context. Don't restate it; the points below are the ones it doesn't cover or that this codebase
gets wrong often enough to be worth naming.

**License headers.** AGENTS.md requires the Apache-2.0 header on every new source file. Most
existing files under `aig/src/` don't have it. Follow AGENTS.md for new files rather than
copying the neighbors, but don't bulk-add headers to untouched files as a side effect.

**Environment defaults must match `.env`.** Every `os.getenv('X', default)` should use the same
value `.env` ships. Several currently don't — `AIG_KEEP_MODEL_IN_MEMORY` defaults to `'false'`
in code but `true` in `.env`, `ASE_DISTANCE_MAX_THRESHOLD` to `1.5` versus `0.2`. These diverge
silently and produce behavior nobody can reproduce. When you add a variable, add it to `.env`
with a comment, wire it through `docker-compose.yml`, and use the identical default in code.
All three, or it won't reach the container.

**Logging, not printing.** `logging` with a module-level `logger`. The existing code logs
generously around selection and generation decisions, which is the only way to debug the ad
pipeline — keep that up in new code paths.

**Bandit.** CI runs Bandit over `aig/src/` and `web-ui/`. A `# nosec` needs a written
justification, as in the existing `# nosec B104` on the `0.0.0.0` binds.

**Pinned dependencies.** `aig/src/requirements.txt` and `aig/export-requirements.txt` are
exactly pinned. Changing a pin is a deliberate act needing justification in the commit body.

## Validating a change

There is no unit test suite. Verification is a live API call against a running stack — plan for
that from the start, because it makes the edit-test loop slow and favors getting the change
right by reading over iterating.

```bash
make build && make up                                  # ~minutes; recreates everything
make status                                            # containers, logs and endpoint probes
curl -k https://localhost:5000/aig-api/aig/hstatus/1   # then exercise your change
```

[Makefile](../../../Makefile) at the repo root is the interface for all of this — `make help`
lists every target. `make status` (alias `check_stack`) runs
[scripts/check-stack.sh](../../../scripts/check-stack.sh) and exits non-zero on failure, so it
works as a gate in a script. If the stack has never been brought up on this machine, models
come from `make download_models` (see the `digital-signage-user` skill).

`aig/src/database/testASE.py` is the existing example of live-call testing — follow its shape
for a new endpoint rather than introducing a test framework, unless adding one is the point of
the task.

Two shortcuts worth knowing:

- `aig/src` is bind-mounted into the container at `/home/aigserver/src`, and the AIG server runs
  Flask with `debug=True`, so **Python edits under `aig/src/` reload without a rebuild** — a
  `docker restart aig-server` is usually enough. `web-ui` has no such mount and needs a rebuild.
- `.env` and `config.json` are read at container start, so those changes need `make up`
  (which downs first), never `docker restart`.

Before declaring done, check the change against the other consumer. An endpoint schema change
that the web UI doesn't send, or an overlay field the API stops reading, produces no error at
all — just an ad that quietly looks wrong.

## Committing

```
<type>(<scope>): <subject>        ≤72 chars

<body, imperative present tense>

Signed-off-by: Name <email>
```

Types `feat|fix|docs|style|refactor|perf|test|build|ci|revert`; scopes `app|eval|deps|all` or
omitted. `Signed-off-by` is mandatory (DCO) — use `git commit -s`. The PR template in
`.github/PULL_REQUEST_TEMPLATE.md` carries an ISDM compliance checklist; fill it rather than
deleting it.

Never commit `aig/models/`, `configs/pid/models/`, `.env`, or `aig/.modelenv/`.

## Working style

Read before writing. This codebase has real asymmetries — the price and slogan overlays are
commented out in `modelinf.py` but live in `predefinedads.py`; `framed_details` has two schema
definitions sharing one name and the handler reads only one of them; the web UI hardcodes
`"device": "GPU"` regardless of `AIG_MODEL_DEVICE`. A change that assumes symmetry where none
exists will look correct and behave wrong. The references call these out; check the relevant one
before assuming the two paths match.

When you find one of these inconsistencies while doing something else, mention it rather than
silently fixing it — an unrelated fix bundled into a change makes the PR harder to review, and
some of them are deliberate.
