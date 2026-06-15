# Transcript: Generating Release Notes for Version 2026.1 (WCL Integration)

## Steps Taken

### 1. Retrieved commit log between `main` and `origin/feature/wcl_integration`

Command:
```
git log main..origin/feature/wcl_integration --oneline
```

Result: 8 commits found, including:
- `78f5ae8` Feature/rebase (#27) — dependency bumps and review comments
- `c7512ab` Feature/rebase (#25) — dependency bumps
- `83e60f6` README.md: Updated Readme with optimized RTSP pipeline details (#24)
- `41251d8` Updated Readme and pipeline for bounding boxes (#22)
- `b8c9753` web-ui: Updated logic for ad generation to go round robin with price higher to lower (#21)
- `391cffe` signage: Added new inventory spreadsheet and fixed geti model path
- `b997941` signage: Added new inventory spreadsheet and fixed geti model path
- `f7472a7` WCL Integration & Testing (#16)

### 2. Retrieved full commit messages

Command:
```
git log main..origin/feature/wcl_integration --format="%H %s%n%b"
```

Key findings:
- WCL Integration (#16): Persistent HTTP session for AIG calls, skip ad generation when no new high-priced item, timing fix in AIG server, logging and config defaults.
- Round-robin ad selection (#21): label normalization, price-based prioritization, rotation, new product entries (grape, lime).
- Bounding box pipeline update (#22): gvawatermark display config added.
- RTSP pipeline docs update (#24).
- Dependency bumps (#25, #27): diffusers 0.33.1→0.38.0, urllib3 2.6.3→2.7.0.

### 3. Retrieved file-level diff statistics

Command:
```
git diff main...origin/feature/wcl_integration --stat
```

Result: 12 files changed, 444 insertions(+), 217 deletions(-)
Files changed: `.env`, `README.md`, `aig/Dockerfile`, `aig/export-requirements.txt`, `aig/src/database/version.py`, `aig/src/requirements.txt`, `aig/src/server/apis/modelinf.py`, `chrome_settings.png`, `docker-compose.yml`, `pid/config.json`, `web-ui/ProductAssociations.csv`, `web-ui/main.py`

### 4. Retrieved detailed diff for `web-ui/main.py`

Command:
```
git diff main...origin/feature/wcl_integration -- web-ui/main.py
```

Key changes:
- Added `normalize_product_key()` and `resolve_product_label()` for MQTT-to-CSV label matching.
- Added `product_association_lookup` dict populated at load time.
- Added `http_session = requests.Session()` to `Ad_Generator` for connection reuse.
- Added `last_selected_item`, `product_generation_count`, `last_association_index_by_label` state fields.
- Added early-exit (`continue`) when `find_product_for_ad_generation` returns `None`.
- Replaced `find_high_priced_item` with `get_product_max_price` to support round-robin rotation.

### 5. Retrieved detailed diff for `aig/src/server/apis/modelinf.py`

Command:
```
git diff main...origin/feature/wcl_integration -- aig/src/server/apis/modelinf.py
```

Key changes:
- Moved `start_time = time.time()` to after pipeline initialization so timing reflects actual image generation only.
- `end_time = time.time()` added after image generation.
- Price overlay code (draw_price_circle) commented out.

### 6. Retrieved diffs for `pid/config.json`, `aig/Dockerfile`, and `aig/src/requirements.txt`

Command:
```
git diff main...origin/feature/wcl_integration -- pid/config.json aig/Dockerfile aig/src/requirements.txt
```

Key changes:
- `aig/Dockerfile`: Base image from `ubuntu:22.04` → `ubuntu:24.04`; Intel Compute Runtime upgraded to `26.14.37833.4`; Intel Graphics Compiler upgraded to `v2.32.7`; added `software-properties-common`.
- `aig/src/requirements.txt`: `diffusers` 0.33.1→0.38.0, `urllib3` 2.6.3→2.7.0.
- `pid/config.json`: YOLO model path corrected; object detection device changed from `GPU` to `CPU`; GStreamer pipeline updated with `gvawatermark` display config.

### 7. Authored release notes

Synthesized all findings into structured Markdown release notes saved to:
`without_skill/outputs/release-notes-draft.md`
