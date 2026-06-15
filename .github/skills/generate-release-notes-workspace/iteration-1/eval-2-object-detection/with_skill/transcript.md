# Transcript: Generate Release Notes — eval-2-object-detection

## Task

Generate release notes for the digital-signage repo comparing `main` with `origin/copilot/optimize-object-detection-logic`. Version 2026.2, September 2026.

---

## Step 1: Read the Skill and Templates

- Read `/home/ecgv-d1-l3t15/digital-signage/digital-signage/.github/skills/generate-release-notes/SKILL.md` to understand the procedure and formatting rules.
- Read `/home/ecgv-d1-l3t15/digital-signage/digital-signage/.github/skills/generate-release-notes/assets/release-notes-template.md` for the output format.
- Read the canonical example at `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/docs/user-guide/release-notes.md` for style reference.

---

## Step 2: Gather Git History

**Command:**
```bash
cd /home/ecgv-d1-l3t15/digital-signage/digital-signage
git log main..origin/copilot/optimize-object-detection-logic --oneline --no-merges
```

**Output (3 commits):**
```
90692d5  Fix default inference steps to 4 for backward compatibility with SDXL-Turbo
3d2963c  Add SD 1.5 LCM model support with configurable guidance_scale, negative_prompt, and inference steps
585758b  Bump pillow from 12.1.1 to 12.2.0 to fix FITS GZIP decompression bomb vulnerability
```

**Command:**
```bash
git diff main..origin/copilot/optimize-object-detection-logic --stat
```

**Output (14 files changed, 260 insertions, 1103 deletions):**
- `.env` — environment variable additions and removals
- `README.md` — documentation updates
- `aig/Dockerfile` — base image and GPU driver changes
- `aig/export-requirements.txt` — dependency version changes
- `aig/src/database/version.py` — new metadata accessors and default corrections
- `aig/src/requirements.txt` — dependency version changes
- `aig/src/server/apis/modelinf.py` — image generation pipeline refactor
- `chrome_settings.png` — binary file removed
- `docker-compose.yml` — service image, volume, and env changes
- `pid/config.json` — object detection model path and device changes
- `pid/resources/videos/Basket.avi` — binary file removed
- `web-ui/ProductAssociations.csv` — CSV data changes
- `web-ui/main.py` — ad selection logic simplification
- `web-ui/templates/portrait.html` — template removed

---

## Step 3: Detailed Diff Analysis

**aig/src/server/apis/modelinf.py:**
- `guidance_scale` parameter made dynamic via `AigServerMetadata.get_model_guidance_scale()` (was hardcoded to `0.0`).
- `negative_prompt` support added: read from `AigServerMetadata.get_model_negative_prompt()`, injected into `generate()` kwargs when non-empty.
- `generate()` call refactored to use `**generate_kwargs` dict for flexibility.
- Timing: `start_time` moved to before pipeline setup.
- Price overlay code un-commented and restored (was fully disabled).
- Slogan overlay code un-commented and restored (was fully disabled).

**aig/src/database/version.py:**
- `get_model_inference_steps()` default corrected from `5` to `4`.
- New `get_model_guidance_scale()` accessor (env `AIG_MODEL_GUIDANCE_SCALE`, default `0.0`).
- New `get_model_negative_prompt()` accessor (env `AIG_MODEL_NEGATIVE_PROMPT`, default `""`).
- Logger initialization moved/simplified.

**aig/Dockerfile:**
- Base image changed from `ubuntu:24.04` to `ubuntu:22.04`.
- Intel GPU driver packages updated to older stable versions (`compute-runtime 25.13.33276.16`, `igc v2.10.8`).
- `software-properties-common` removed from apt install.

**aig/export-requirements.txt / aig/src/requirements.txt:**
- `diffusers` downgraded from `0.38.0` to `0.33.1`.
- `urllib3` downgraded from `2.7.0` to `2.6.3` in `src/requirements.txt`.
- `urllib3` removed from `export-requirements.txt`.
- `pillow` 12.2.0 (security fix for FITS GZIP decompression bomb).

**.env:**
- `AIG_MODEL_NUM_INFERENCE_STEPS` corrected to `4`.
- `AIG_MODEL_GUIDANCE_SCALE=0.0` added.
- `AIG_MODEL_NEGATIVE_PROMPT=` added (empty default).
- Default image dimensions changed from `448` to `512`.
- `TIME_TO_DISPLAY_AD_SECONDS`, `OBJECT_RECENCY_FRAME_COUNT`, `OBJECT_CONFIDENCE_THRESHOLD` removed.

**docker-compose.yml:**
- `dlstreamer-pipeline-server` image downgraded from `2026.1.0-ubuntu24-rc1` to `2026.0.0-ubuntu24-rc1`.
- Object detection model volume mount renamed: `./pid/models/object_detection` → `./pid/models/object_detection:/home/pipeline-server/yolo_models`.
- `AIG_MODEL_GUIDANCE_SCALE` and `AIG_MODEL_NEGATIVE_PROMPT` env vars added to `aig-server` service.
- `TIME_TO_DISPLAY_AD_SECONDS`, `OBJECT_RECENCY_FRAME_COUNT`, `OBJECT_CONFIDENCE_THRESHOLD` env vars removed from `web-ui` service.
- Duplicate `chroma_data:/tmp` volume mount removed.
- `OPENVINO_LOG_LEVEL` env var removed from `aig-server`.

**pid/config.json:**
- Model path updated: `/home/pipeline-server/object_detection/yolo11s/...` → `/home/pipeline-server/yolo_models/yolo11s/...`.
- Inference device changed from `CPU` to `GPU`.
- `gvawatermark` `displ-cfg` string removed (simplified pipeline).

**web-ui/main.py:**
- Removed: `normalize_product_key()`, `resolve_product_label()`, `product_association_lookup`.
- Removed: `find_product_for_ad_generation()`, `find_high_priced_candidate()`, `find_rotating_candidate()`, `choose_association_index()`.
- Removed: `last_generated_timestamp`, `last_processed_item`, `last_selected_item`, `product_generation_count`, `last_association_index_by_label`, `time_to_display_ad` state.
- Replaced with simple `ad_generating_in_progress` flag to prevent concurrent generation.
- Direct item from queue now used without temporal filtering, confidence gating, or price prioritization.

**README.md:**
- Added: SD 1.5 LCM download/export instructions and `.env` configuration snippet.
- Removed: Verbose "Object Selection and Ad Generation Flow" section (8 subsections).
- Removed: Chrome GPU disable workaround instructions and `chrome_settings.png` reference.
- Simplified: RTSP camera configuration section (renamed to "Advanced: RTSP Camera Configuration").
- Simplified: Intel® Geti™ section renamed to "Advanced: Using Intel® Geti™ Exported YOLO Model"; updated Geti SDK version reference.

---

## Step 4: Categorization Decisions

| Change | Category | Reasoning |
|--------|----------|-----------|
| SD 1.5 LCM model support | New | Entirely new model option not present in base branch |
| `AIG_MODEL_GUIDANCE_SCALE` / `AIG_MODEL_NEGATIVE_PROMPT` env vars | New (part of SD 1.5 LCM) | Bundled into the SD 1.5 LCM bullet |
| Price and slogan overlays restored | Improved | Feature existed but was commented out; now active |
| Object detection: GPU default, renamed volume, simplified watermark | Improved | Enhancement/optimization of existing pipeline |
| Web UI ad selection simplified | Improved | Refactor of existing behavior |
| Default image resolution 448→512 | Improved | Parameter tuning |
| AIG base image Ubuntu 22.04 | Improved | Image version change |
| GPU driver package updates | Improved | Dependency update (part of base image improvement) |
| DL Streamer Pipeline Server 2026.0.0 | Improved | Image version change |
| Pillow 12.2.0 (security) | Improved > Security | Security patch |
| README updates | Improved > Documentation | Documentation |
| Default inference steps 5→4 | Fixed | Bug fix / backward compatibility correction |
| Duplicate volume mount removed | Fixed | Bug/misconfiguration fix |

---

## Step 5: Output

Final release notes written to:
`/home/ecgv-d1-l3t15/digital-signage/digital-signage/.github/skills/generate-release-notes-workspace/iteration-1/eval-2-object-detection/with_skill/outputs/release-notes-draft.md`
