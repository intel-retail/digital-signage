## Version 2026.1

**June 2026**

This release introduces WCL integration along with improvements to the ad-generation pipeline, bounding-box display, RTSP pipeline performance, and updated dependencies and base images.

---

### **New**

- **WCL Integration:** Integrated the Web Content Library (WCL) into the ad-generation flow and AIG server/runtime configuration, enabling updated integration and testing capabilities including performance and telemetry adjustments.

- **Persistent HTTP Session for AIG Calls:** The Web UI now reuses a persistent `requests.Session` for all calls to the AIG server, reducing connection overhead and improving throughput for ad generation requests.

- **Product Label Normalization:** Added `normalize_product_key` and `resolve_product_label` helpers that normalize incoming MQTT detection labels (stripping whitespace, lowercasing, replacing hyphens and underscores) to reliably match them against CSV product entries.

- **Round-Robin Ad Variant Rotation:** Ad selection now tracks per-product generation counts and rotates through ad variants using a round-robin strategy, preventing repeated display of the same ad creative.

- **First-Time Product Prioritization by Price:** On a product's first detection, the system prioritizes items by their highest configured price before entering rotation, ensuring high-value products surface first.

- **Extended Product Associations:** Added grape and lime product entries to `ProductAssociations.csv` to support dynamic ad generation for additional detected items.

- **New Inventory Spreadsheet:** Added a new inventory spreadsheet covering all detectable objects, with improved cross-sell pairings and richer AI generation prompts.

---

### **Improved**

- **Ad Generation Skip on No New Item:** The ad-generation loop now skips processing when `find_product_for_ad_generation` returns `None` (i.e., no high-priced new item is detected), reducing unnecessary AIG server calls.

- **Accurate Image Generation Timing:** Moved the `start_time` measurement in the AIG model inference server to begin only after the pipeline is initialized, so reported latency reflects actual image generation time rather than pipeline warm-up.

- **Bounding Box Display Configuration:** Updated the GStreamer pipeline to pass `gvawatermark` display configuration (`font-scale=1.5`, `thickness=3`, `color-idx=2`, `font-type=plain`) for clearer bounding box overlays on detected objects.

- **Object Detection Model Path Fix:** Corrected the YOLO model path in `config.json` from `yolo_models/yolo11s/INT8/yolo11s.xml` to `object_detection/yolo11s/INT8/yolo11s.xml`.

- **Object Detection Device:** Changed the default object detection device from `GPU` to `CPU` in `config.json` to improve compatibility across deployment targets.

- **AIG Base Image Upgrade:** The AIG Dockerfile base image has been updated from `ubuntu:22.04` to `ubuntu:24.04`, with `software-properties-common` added to the dependency set.

- **Updated Intel GPU Drivers:** Upgraded Intel Compute Runtime to `26.14.37833.4` and Intel Graphics Compiler to `v2.32.7`, with updated package names and versions for `intel-ocloc`, `intel-opencl-icd`, `libigdgmm12`, and `libze-intel-gpu1`.

- **Dependency Upgrades:**
  - **diffusers:** Upgraded from `0.33.1` to `0.38.0`
  - **urllib3:** Upgraded from `2.6.3` to `2.7.0`

- **Documentation:** Updated `README.md` with optimized RTSP pipeline details, bounding box configuration guidance, GETI model deployment fixes, and tips for running the Web UI locally.
