# Transcript: Release Notes Generation for digital-signage v2026.2

## Goal

Generate release notes for the digital-signage repository comparing `main` with `origin/copilot/optimize-object-detection-logic`, version 2026.2, September 2026.

---

## Step 1: List commits in the feature branch

Command:
```
git log --oneline main..origin/copilot/optimize-object-detection-logic
```

Result — 3 commits found:
- `90692d5` Fix default inference steps to 4 for backward compatibility with SDXL-Turbo
- `3d2963c` Add SD 1.5 LCM model support with configurable guidance_scale, negative_prompt, and inference steps
- `585758b` Bump pillow from 12.1.1 to 12.2.0 to fix FITS GZIP decompression bomb vulnerability

---

## Step 2: Get file-level diff statistics

Command:
```
git diff main..origin/copilot/optimize-object-detection-logic --stat
```

Result — 14 files changed, 260 insertions, 1103 deletions:
- `.env`
- `README.md`
- `aig/Dockerfile`
- `aig/export-requirements.txt`
- `aig/src/database/version.py`
- `aig/src/requirements.txt`
- `aig/src/server/apis/modelinf.py`
- `chrome_settings.png` (deleted)
- `docker-compose.yml`
- `pid/config.json`
- `pid/resources/videos/Basket.avi` (deleted)
- `web-ui/ProductAssociations.csv`
- `web-ui/main.py`
- `web-ui/templates/portrait.html` (deleted)

---

## Step 3: Review detailed diffs

### aig/src/server/apis/modelinf.py

Key changes observed:
- `start_time = time.time()` moved to before pipeline initialization for accurate end-to-end timing.
- `end_time` moved to after all post-processing steps.
- `pipe.generate()` call refactored: `guidance_scale` is now configurable via `AigServerMetadata.get_model_guidance_scale()` instead of hardcoded `0.0`.
- `negative_prompt` parameter conditionally added when `AigServerMetadata.get_model_negative_prompt()` returns a non-empty string.
- Previously commented-out price overlay and slogan overlay code was uncommented and restored to active functionality.

### aig/src/database/version.py

- Default value of `AIG_MODEL_NUM_INFERENCE_STEPS` changed from `5` to `4`.
- New static method `get_model_guidance_scale()` added (reads `AIG_MODEL_GUIDANCE_SCALE`, default `0.0`).
- New static method `get_model_negative_prompt()` added (reads `AIG_MODEL_NEGATIVE_PROMPT`, default empty string).
- Logger initialization order cleaned up (moved `logger = logging.getLogger(__name__)` up and removed redundant `logger.setLevel(logging.INFO)`).

### aig/src/requirements.txt

- `diffusers` downgraded from `0.38.0` to `0.33.1`.
- `urllib3` downgraded from `2.7.0` to `2.6.3`.
- `pillow` updated from `12.1.1` to `12.2.0` (security fix).

### aig/export-requirements.txt

- `urllib3==2.7.0` removed.
- `diffusers` downgraded from `0.38.0` to `0.33.1`.

### aig/Dockerfile

- Base image changed from `ubuntu:24.04` to `ubuntu:22.04`.
- Intel GPU driver and compiler packages changed to older versions (compute-runtime 25.13.33276.16, igc v2.10.8).
- `software-properties-common` removed from apt dependencies.

### .env

- `AIG_MODEL_NUM_INFERENCE_STEPS` comment updated; value already `4`.
- `AIG_MODEL_GUIDANCE_SCALE=0.0` added.
- `AIG_MODEL_NEGATIVE_PROMPT=` added (empty by default).
- Default image dimensions changed: `AIG_IMG_WIDTH_DEFAULT` and `AIG_IMG_HEIGHT_DEFAULT` both changed from `448` to `512`.
- `TIME_TO_DISPLAY_AD_SECONDS`, `OBJECT_RECENCY_FRAME_COUNT`, and `OBJECT_CONFIDENCE_THRESHOLD` variables removed.

### docker-compose.yml

- `dlstreamer-pipeline-server` image downgraded from `2026.1.0-ubuntu24-rc1` to `2026.0.0-ubuntu24-rc1`.
- Object detection model volume mount renamed from `./pid/models/object_detection:/home/pipeline-server/object_detection` to `./pid/models/object_detection:/home/pipeline-server/yolo_models`.
- Duplicate `chroma_data:/tmp` volume entry removed from `ase-chromadb` service.
- `AIG_MODEL_GUIDANCE_SCALE` and `AIG_MODEL_NEGATIVE_PROMPT` env vars added to `aig-server` service.
- `OPENVINO_LOG_LEVEL` env var removed from `aig-server` service.
- `TIME_TO_DISPLAY_AD_SECONDS`, `OBJECT_RECENCY_FRAME_COUNT`, `OBJECT_CONFIDENCE_THRESHOLD` env vars removed from `web-ui` service.

### pid/config.json

- `gvawatermark` display configuration parameters removed from the GStreamer pipeline string.
- Object detection model path updated to use new container mount path `/home/pipeline-server/yolo_models/yolo11s/INT8/yolo11s.xml`.
- Object detection device changed from `"CPU"` to `"GPU"`.

### web-ui/main.py

- Removed helper functions: `normalize_product_key`, `resolve_product_label`.
- Removed `product_association_lookup` dict and all lookups through it.
- Removed complex `Ad_Generator` state: `last_n_messages_labels`, `last_generated_timestamp`, `last_selected_item`, `product_generation_count`, `last_association_index_by_label`, `time_to_display_ad`.
- Removed complex product-selection methods: `find_product_for_ad_generation`, `find_high_priced_candidate`, `find_rotating_candidate`, `choose_association_index`, `get_product_max_price`.
- Removed `TIME_TO_DISPLAY_AD_SECONDS` throttle gate in the `Ad_Generator` run loop.
- Replaced rolling-window MQTT recency/confidence filter with a simplified handler: reads the first detection tensor, checks confidence > 0.5, deduplicates against the last 3 processed labels, and enqueues the single label string.
- Removed `http_session = requests.Session()` from `Ad_Generator.__init__`.
- Added `ad_generating_in_progress` flag to `Ad_Generator`.
- Removed `/portrait` Flask route; `web-ui/templates/portrait.html` deleted.

### README.md

- Removed "Web UI: Object Selection and Ad Generation Flow" section documenting the now-removed detection pipeline.
- Added SD 1.5 LCM setup instructions with download and `.env` configuration steps.
- Removed Chrome GPU workaround section and `chrome_settings.png` reference.
- Removed "Switch the Simulation Video" advanced configuration section.

---

## Step 4: Write release notes

Release notes written and saved to:
`/home/ecgv-d1-l3t15/digital-signage/digital-signage/.github/skills/generate-release-notes-workspace/iteration-1/eval-2-object-detection/without_skill/outputs/release-notes-draft.md`
