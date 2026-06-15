# Transcript: Generate Release Notes — WCL Integration (eval-1-wcl-comparison)

## Inputs

- Base branch: `main` (resolved as `origin/main`)
- Release branch: `origin/feature/wcl_integration`
- Version: `2026.1`
- Month/Year: `June 2026`
- Repository: `/home/ecgv-d1-l3t15/digital-signage/digital-signage`

---

## Step 1: Loaded skill and format references

Read the skill file at:
  `.github/skills/generate-release-notes/SKILL.md`

Read the format template at:
  `.github/skills/generate-release-notes/assets/release-notes-template.md`

Read the canonical format example at:
  `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/docs/user-guide/release-notes.md`

Key format rules confirmed:
- Version heading: `## Version <X.Y>`
- Date line immediately below (bold, own line): `**<Month Year>**`
- One-sentence intro naming 2–4 highlights in bold, ending with closing clause
- Category headings: `**New**`, `**Improved**`, `**Fixed**`
- Bullets: `- **Feature Name**: lowercase description ending with period`

---

## Step 2: Git log — commits unique to the feature branch

Command run:
```
git --no-pager log origin/main..origin/feature/wcl_integration --oneline --no-merges
```

Output (7 commits, oldest to newest):
1. `f7472a7` — WCL Integration & Testing (#16)
2. `b997941` — signage: Added new inventory spreadsheet and fixed geti model path
3. `b8c9753` — web-ui: Updated logic for ad generation to go round robin with price higher to lower (#21)
4. `41251d8` — Updated Readme and pipeline for bounding boxes (#22)
5. `83e60f6` — README.md: Updated Readme with optimized RTSP pipeline details (#24)
6. `c7512ab` — Feature/rebase (#25)  [dep bumps: diffusers 0.33.1→0.38.0, urllib3 2.6.3→2.7.0]
7. `78f5ae8` — Feature/rebase (#27)  [ProductAssociations.csv minor fix]

---

## Step 3: Per-commit analysis

### f7472a7 — WCL Integration & Testing (#16)
Files changed: `.env`, `README.md`, `aig/Dockerfile`, `aig/src/database/version.py`,
  `aig/src/server/apis/modelinf.py`, `docker-compose.yml`, `pid/config.json`, `web-ui/main.py`

Key changes identified:
- `aig/Dockerfile`: Base image upgraded `ubuntu:22.04` → `ubuntu:24.04`; Intel GPU compute
  runtime updated from 25.13.x to 26.14.37833.4; Intel Graphics Compiler updated from v2.10.8
  to v2.32.7
- `web-ui/main.py`: Added persistent HTTP session reuse for AIG calls; skip ad generation
  when no new high-priced item detected
- `aig/src/server/apis/modelinf.py`: Image-generation timing adjustments, logging config changes
- `pid/config.json`: YOLO model path changed from `yolo_models/` to `object_detection/`;
  device changed from GPU to CPU
- `README.md`: Added Web UI local setup tips

Decision: Core **New** items (WCL integration), **Improved** (AIG base image upgrade),
**Fixed** (model path).

### b997941 — Added new inventory spreadsheet and fixed geti model path
Files changed: `README.md`, `docker-compose.yml`, `pid/config.json`, `web-ui/ProductAssociations.csv`

Key changes:
- `ProductAssociations.csv`: Comprehensive revamp of product-to-ad associations and prompts
- `README.md` + `pid/config.json`: Fixed Geti model deployment path

Decision: **Improved** (product associations), **Fixed** (Geti model path).

### b8c9753 — Round-robin ad selection
Files changed: `README.md`, `docker-compose.yml`, `web-ui/ProductAssociations.csv`, `web-ui/main.py`

Key changes:
- `web-ui/main.py`: New label normalization, price-ordered first-time selection, selection-count
  tracking, ad variant rotation — all new logic
- `ProductAssociations.csv`: Added grape and lime entries
- `README.md`: Expanded guidance; updated DL Streamer image tag

Decision: **New** (round-robin ad selection algorithm), **Improved** (product associations
extended, documentation).

### 41251d8 — Bounding boxes
Files changed: `README.md`, `chrome_settings.png` (new), `pid/config.json`

Key changes:
- `pid/config.json`: Added `gvawatermark` display config (`font-scale=1.5,thickness=3,color-idx=2`)
- `README.md`: Bounding box setup instructions
- `chrome_settings.png`: New screenshot

Decision: **Improved** (bounding box visualization).

### 83e60f6 — RTSP pipeline docs
Files changed: `README.md`

Decision: **Improved** (documentation).

### c7512ab + 78f5ae8 — Rebase / dependency bumps
Files changed: `aig/export-requirements.txt`, `aig/src/requirements.txt`, `web-ui/ProductAssociations.csv`

Key changes:
- `diffusers` 0.33.1 → 0.38.0
- `urllib3` 2.6.3 → 2.7.0

Decision: **Improved** (security/dependency upgrades).

---

## Step 4: Categorization summary

| Category | Item |
|----------|------|
| New | WCL Integration (persistent session + smart skip) |
| New | Round-Robin Ad Selection (price-ordered, variant rotation) |
| Improved | AIG Container Base Image (Ubuntu 22.04 → 24.04, GPU runtime/compiler upgrades) |
| Improved | Product Associations (revamped CSV + grape/lime added) |
| Improved | Bounding Box Display (gvawatermark config) |
| Improved | Security (diffusers 0.38.0, urllib3 2.7.0) |
| Improved | Documentation (RTSP pipeline, Web UI local setup, bounding boxes, image tags) |
| Fixed | Object Detection Model Path (yolo_models/ → object_detection/) |
| Fixed | Geti Model Path (deployment config fix) |

---

## Step 5: Introductory sentence selection

Chose pattern: names 2–4 most significant highlights in bold.

Selected highlights: WCL integration, round-robin ad selection, AIG container base image upgrade.

---

## Step 6: Output written

Release notes saved to:
  `.github/skills/generate-release-notes-workspace/iteration-1/eval-1-wcl-comparison/with_skill/outputs/release-notes-draft.md`
