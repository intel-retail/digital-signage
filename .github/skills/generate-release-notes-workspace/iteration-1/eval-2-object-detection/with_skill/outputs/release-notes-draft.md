# Release Notes: Digital Signage

## Version 2026.2

**September 2026**

This release introduces **SD 1.5 LCM model support**, along with **restored price and slogan image overlays**, **optimized object detection pipeline configuration**, and various fixes and documentation improvements.

**New**

- **SD 1.5 LCM Model Support**: SD 1.5 LCM (LCM_Dreamshaper_v7) is now available as an alternative image generation model, suited for systems with limited GPU memory. New environment variables `AIG_MODEL_GUIDANCE_SCALE` and `AIG_MODEL_NEGATIVE_PROMPT` enable per-model configuration of classifier-free guidance and negative prompting, and download and export instructions are documented in the README.

**Improved**

- **Price and Slogan Overlays**: Price badge and slogan rendering in the image generation pipeline have been re-enabled; the overlay logic was previously commented out and is now fully active.
- **Object Detection Pipeline**: The default inference device for YOLO object detection has been changed from CPU to GPU; the model volume mount path has been renamed from `object_detection` to `yolo_models`; and the `gvawatermark` display configuration string has been removed for a simplified pipeline.
- **Web UI Ad Selection**: Complex temporal filtering, confidence gating, price-based prioritization, and product rotation logic have been removed in favor of a simpler `ad_generating_in_progress` flag. The `TIME_TO_DISPLAY_AD_SECONDS`, `OBJECT_RECENCY_FRAME_COUNT`, and `OBJECT_CONFIDENCE_THRESHOLD` environment variables have been removed.
- **Default Image Resolution**: Default image generation dimensions updated from 448×448 to 512×512.
- **AIG Server Base Image**: The AIG server container base image has been updated from Ubuntu 24.04 to Ubuntu 22.04, with updated Intel GPU driver packages.
- **DL Streamer Pipeline Server**: Updated to image version 2026.0.0.
- **Security**: Pillow upgraded from 12.1.1 to 12.2.0 to address a FITS GZIP decompression bomb vulnerability.
- **Documentation**: README updated with SD 1.5 LCM model download and configuration instructions; verbose object selection flow documentation removed; RTSP camera and Intel® Geti™ model sections simplified.

**Fixed**

- **Default Inference Steps**: The default value for `AIG_MODEL_NUM_INFERENCE_STEPS` has been corrected from 5 to 4 for backward compatibility with SDXL-Turbo.
- **Duplicate Volume Mount**: A duplicate `chroma_data:/tmp` volume entry in `docker-compose.yml` has been removed.

---
