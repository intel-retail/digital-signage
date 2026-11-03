# AGENTS.md

Guidelines for AI coding agents working in this repository.

## Project Overview

Context-Aware, Cross-Selling Digital Signage — a containerized edge AI solution using Intel hardware for real-time product detection (YOLO11) and dynamic ad generation (SDXL-Turbo images, optional LTX-Video video ads), with an MCP server for agent-driven ad triggering. Deployed via Docker Compose.

## Repository Structure

```
aig/            # Advertise Image Generator — Flask/Flask-RESTX Python service
  src/
    server/     # REST API endpoints (Flask-RESTX)
    database/   # Qdrant-backed semantic search (ASE)
    imgproc/    # Image processing utilities
web-ui/         # Flask web UI — video stream + ad display; mcp_server.py exposes MCP tools (nginx /mcp)
configs/        # Runtime configs: DLStreamer pipeline, MQTT, nginx
docs/           # User-facing documentation (Markdown)
scripts/        # Helper scripts, invoked through the Makefile (model download, stack health)
performance-tools/  # Git submodule for benchmarking (`make update-submodules`); absent until initialised
Makefile        # Primary build/run interface
docker-compose.yml
.env            # Local environment config (never commit secrets)
```

## Build & Run

The Makefile is the interface for everything — prefer a target over running the underlying commands by hand. `make help` lists them all.

```bash
make download_models   # Download/prepare YOLO11s, SDXL-Turbo, MiniLM (+ LTX-Video) via the model-download microservice
make build             # Build all Docker images
make up                # Validate env + models, start all containers
make down              # Stop and remove containers + volumes
make status            # Stack health: containers, log errors, endpoint probes (alias: check_stack)
make update-submodules # Fetch performance-tools; needed before any `make benchmark-*` target
```

`make download_models` needs Docker and the `MODEL_DOWNLOAD_IMAGE` pull; it skips work when the artifacts already exist. `make status` exits non-zero on failure, so it works as a gate in a script or CI step.

Before `make up`, ensure:
- `HOST_IP` is set in `.env` to an IPv4 address — default `127.0.0.1` (loopback-only); `localhost` is rejected. Published ports bind to it, so use the host's reachable IPv4 for remote access
- `MTX_WEBRTCICESERVERS2_0_USERNAME` (≥5 alpha chars) and `MTX_WEBRTCICESERVERS2_0_PASSWORD` (≥8 alphanumeric, at least one digit) are set
- Models exist in `configs/pid/models/` and `aig/models/` (`make download_models`; `make check_models` verifies them)

## Code Conventions

**Languages:** Python 3 (`aig/`, `web-ui/`). No JavaScript/TypeScript.

**License header** — every new source file must include:
```python
#
# Apache v2 license
# Copyright (C) <year> Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
```

**Python style:** Follow existing patterns — Flask-RESTX for REST APIs, `logging` module (not `print`), type hints where already used.

**No hardcoded secrets or credentials** — use environment variables via `os.getenv()`.

## Agent Skills

Skills live in `.github/skills/` (`digital-signage-user` to deploy/operate, `digital-signage-dev` to change code). They may be installed outside this repo (for example `npx skills add`), so:

- Keep `references/…` paths relative to the skill folder and everything else relative to the repo root; do not link to repo files with `../../../`.
- Skills locate the checkout at runtime (user-given path, cwd, then `git rev-parse --show-toplevel`) and treat the published user guide (`docs/user-guide/`) as the primary source for system requirements and prerequisites instead of duplicating them.
- Update the skills when the Makefile targets, `.env` rules, or user-guide procedures they describe change.

## Commit Format

```
<type>(<scope>): <subject>        ← max 72 chars
<blank line>
<body>                            ← imperative present tense
<blank line>
Signed-off-by: Name <email>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `revert`  
Scopes: `app`, `eval`, `deps`, `all` (or omit)

`Signed-off-by` is **required** (DCO). Use `git commit -s` to add automatically.

## Testing

No automated unit test suite. Integration tests are live API calls against the running stack (see `aig/src/database/testASE.py` and `testqdrant.py` for examples). Validate changes by running `make up` and checking `make status`.

CI runs `make build` + `make up` on every PR. Security scans use Bandit (Python) and Trivy (containers/filesystem) — avoid flagged patterns (`# nosec` only with justification).

## What Not to Touch

- `aig/models/` and `configs/pid/models/` — AI model files, never commit
- `.env` — local config, in `.gitignore`, never commit secrets
- `aig/npu_cache/` — compiled NPU blobs, git-ignored
- Pinned dependency versions in `aig/src/requirements.txt` and `web-ui/requirements.txt` — update deliberately with justification (Dependabot manages routine bumps)
