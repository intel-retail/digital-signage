# AGENTS.md

Guidelines for AI coding agents working in this repository.

## Project Overview

Context-Aware, Cross-Selling Digital Signage — a containerized edge AI solution using Intel hardware for real-time product detection (YOLO11) and dynamic ad generation (SDXL-Turbo). Deployed via Docker Compose.

## Repository Structure

```
aig/            # Advertise Image Generator — Flask/Flask-RESTX Python service
  src/
    server/     # REST API endpoints (Flask-RESTX)
    database/   # ChromaDB + semantic search (ASE)
    imgproc/    # Image processing utilities
web-ui/         # Flask web UI — video stream + ad display
configs/        # Runtime configs: DLStreamer pipeline, MQTT, nginx
docs/           # User-facing documentation (Markdown)
scripts/        # Helper scripts, invoked through the Makefile (model download, stack health)
Makefile        # Primary build/run interface
docker-compose.yml
.env            # Local environment config (never commit secrets)
```

## Build & Run

The Makefile is the interface for everything — prefer a target over running the underlying commands by hand. `make help` lists them all.

```bash
make download_models   # Download/prepare YOLO11s, SDXL-Turbo, MiniLM (add FORCE=1 to redo)
make build             # Build all Docker images
make up                # Validate env + models, start all containers
make down              # Stop and remove containers + volumes
make status            # Stack health: containers, log errors, endpoint probes (alias: check_stack)
```

`make download_models_pid` and `make download_models_aig` do one half only. `make status` exits non-zero on failure, so it works as a gate in a script or CI step.

Before `make up`, ensure:
- `HOST_IP` is set in `.env` (IP or `localhost`)
- `MTX_WEBRTCICESERVERS2_0_USERNAME` (≥5 alpha chars) and `MTX_WEBRTCICESERVERS2_0_PASSWORD` (≥8 alphanumeric, at least one digit) are set
- Models exist in `configs/pid/models/` and `aig/models/` (`make download_models`)

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

No automated unit test suite. Integration tests are live API calls against the running stack (see `aig/src/database/testASE.py` for examples). Validate changes by running `make up` and checking `make status`.

CI runs `make build` + `make up` on every PR. Security scans use Bandit (Python) and Trivy (containers/filesystem) — avoid flagged patterns (`# nosec` only with justification).

## What Not to Touch

- `aig/models/` and `configs/pid/models/` — AI model files, never commit
- `.env` — local config, in `.gitignore`, never commit secrets
- `aig/.modelenv/` — Python venv, in `.gitignore`
- Pinned dependency versions in `aig/src/requirements.txt` and `aig/export-requirements.txt` — update deliberately with justification
