# Digital Signage Release Notes — Version 2026.2 (September 2026)

## Overview

This release introduces SD 1.5 LCM model support for lighter-weight image generation, simplifies object-detection processing in the Web UI, restores previously disabled image overlay features (price, slogan), and updates infrastructure dependencies.

---

## New Features

### SD 1.5 LCM Model Support

Adds support for the [SimianLuo/LCM_Dreamshaper_v7](https://huggingface.co/SimianLuo/LCM_Dreamshaper_v7) model as an alternative to SDXL-Turbo. SD 1.5 LCM uses less GPU memory and performs faster on integrated GPUs while still producing quality advertisement images.

New environment variables:

| Variable | Default | Description |
|---|---|---|
| `AIG_MODEL_GUIDANCE_SCALE` | `0.0` | Guidance scale for classifier-free guidance. Use `0.0` for SDXL-Turbo, `1.0` for SD 1.5 LCM. |
| `AIG_MODEL_NEGATIVE_PROMPT` | _(empty)_ | Negative prompt to steer the model away from undesired artifacts. Recommended for SD 1.5 LCM; leave empty for SDXL-Turbo. |

To use SD 1.5 LCM, export the model with:

```bash
cd aig && \
rm -rf .modelenv && python3 -m venv .modelenv && source ./.modelenv/bin/activate && \
pip3 install -r export-requirements.txt && \
export HF_HUB_ENABLE_HF_TRANSFER=1 && \
optimum-cli export openvino --model SimianLuo/LCM_Dreamshaper_v7 --task stable-diffusion --weight-format int8 ./models/sd15_lcm_ov/int8 && \
deactivate && cd ../
```

Then set in `.env`:
```
AIG_MODEL_PATH=/opt/models/sd15_lcm_ov/int8
AIG_MODEL_NUM_INFERENCE_STEPS=4
AIG_MODEL_GUIDANCE_SCALE=1.0
AIG_MODEL_NEGATIVE_PROMPT=blurry, low quality, distorted, deformed, ugly, bad anatomy, watermark, text, logo, banner
```

---

## Improvements

### Price Overlay and Slogan Overlay Re-enabled

The price-circle and slogan overlays in the AI Image Generator (`aig/src/server/apis/modelinf.py`) were previously commented out and always bypassed. Both features are now fully active. When `price_details` or `slogan_details` are included in an `/aig/minf/` request, the corresponding overlay is rendered onto the generated image.

### Simplified Object-Detection Processing in Web UI

The MQTT message handler in `web-ui/main.py` has been refactored to reduce complexity:

- Removed the rolling-window recency filter that required a detected label to appear across multiple consecutive frames (`OBJECT_RECENCY_FRAME_COUNT`) before triggering ad generation.
- Removed configurable `OBJECT_CONFIDENCE_THRESHOLD` and `TIME_TO_DISPLAY_AD_SECONDS` environment variables.
- Removed the complex product-selection strategy (first-time high-price prioritization, rotation with repeat prevention, per-product generation counters, association-variant cycling).
- The handler now reads the first detection tensor from the first `gva_meta` entry, applies a fixed 0.5 confidence threshold, and enqueues the label if it has not appeared in the last three processed detections.

**Removed environment variables** (no longer recognized):
- `OBJECT_RECENCY_FRAME_COUNT`
- `OBJECT_CONFIDENCE_THRESHOLD`
- `TIME_TO_DISPLAY_AD_SECONDS`

### Object Detection Runs on GPU

The YOLO object-detection model configured in `pid/config.json` now targets the GPU device (`"device": "GPU"`) instead of CPU, improving inference throughput.

### Image Generation Inference Timing Fix

`start_time = time.time()` is now captured before pipeline initialization and model loading, providing a more accurate end-to-end latency measurement. `end_time` is captured after all image post-processing steps complete.

### Default Image Dimensions Updated

Default output image dimensions for the AIG model changed from **448 × 448** to **512 × 512** pixels, aligning with the native training resolution used by both SDXL-Turbo and SD 1.5 LCM.

---

## Bug Fixes

### Default Inference Steps Corrected for SDXL-Turbo

The default value of `AIG_MODEL_NUM_INFERENCE_STEPS` was corrected from `5` to `4`, restoring the original recommended step count for SDXL-Turbo and matching the documented default.

### Duplicate ChromaDB Volume Mount Removed

A duplicate `chroma_data:/tmp` volume entry was removed from the `ase-chromadb` service in `docker-compose.yml`.

---

## Security

### Pillow Updated to 12.2.0

Pillow was upgraded from 12.1.1 to 12.2.0 to address a FITS GZIP decompression bomb vulnerability.

---

## Dependency Changes

| Package | Previous | Updated | Notes |
|---|---|---|---|
| `pillow` | 12.1.1 | 12.2.0 | Security fix |
| `diffusers` | 0.38.0 | 0.33.1 | Downgraded for compatibility |
| `urllib3` | 2.7.0 | 2.6.3 | Downgraded in runtime requirements |

`urllib3` has been removed from `aig/export-requirements.txt`.

---

## Infrastructure Changes

### AIG Docker Base Image Changed to Ubuntu 22.04

The `aig-server` Dockerfile base image was changed from `ubuntu:24.04` to `ubuntu:22.04`.

### Intel GPU Driver Versions Updated

Intel compute runtime and graphics compiler packages in the AIG Dockerfile were updated to:

- `intel-compute-runtime` 25.13.33276.16 (from 26.14.37833.4)
- `intel-igc` v2.10.8 (from v2.32.7)

### DL Streamer Pipeline Server Image Downgraded

The `dlstreamer-pipeline-server` container image was changed from `intel/dlstreamer-pipeline-server:2026.1.0-ubuntu24-rc1` to `intel/dlstreamer-pipeline-server:2026.0.0-ubuntu24-rc1`.

### Object Detection Model Mount Path Renamed

The host-side model directory is now mounted into the container at `/home/pipeline-server/yolo_models` (previously `/home/pipeline-server/object_detection`).

---

## Removals

- **Portrait mode** (`/portrait` route and `web-ui/templates/portrait.html`) has been removed.
- Sample video `pid/resources/videos/Basket.avi` has been removed from the repository.
- `chrome_settings.png` and associated Chrome GPU workaround documentation have been removed from the README.
- `OPENVINO_LOG_LEVEL` environment variable is no longer passed to the `aig-server` container.
- `software-properties-common` removed from the AIG Dockerfile build dependencies.
