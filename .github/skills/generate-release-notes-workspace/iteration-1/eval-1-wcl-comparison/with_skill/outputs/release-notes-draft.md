# Release Notes: Digital Signage

## Version 2026.1

**June 2026**

This release introduces **WCL integration with persistent session and smart ad-skip logic**,
**round-robin ad selection prioritized by price**, and **an upgraded AIG container base image**,
along with various fixes and documentation improvements.

**New**

- **WCL Integration**: The ad-generation flow now reuses a persistent HTTP session for AIG
  calls and skips ad generation when no new high-priced item is detected, reducing redundant
  inference requests and improving end-to-end pipeline performance.
- **Round-Robin Ad Selection**: The Web UI now normalizes detected product labels, prioritizes
  first-time product selections by configured price (highest to lowest), tracks per-product
  selection counts, and rotates ad variants to avoid showing the same creative consecutively.

**Improved**

- **AIG Container Base Image**: The AIG server Dockerfile has been upgraded from Ubuntu 22.04
  to Ubuntu 24.04, with updated Intel GPU compute runtime (26.14.37833.4) and Intel Graphics
  Compiler (2.32.7).
- **Product Associations**: The `ProductAssociations.csv` inventory spreadsheet has been
  revamped with improved cross-sell mappings and generative prompts; grape and lime product
  entries have been added.
- **Bounding Box Display**: The DL Streamer pipeline now configures `gvawatermark` with
  custom font scale, thickness, and color index for clearer, more visible bounding box
  overlays in the video feed.
- **Security**: Upgraded `diffusers` from 0.33.1 to 0.38.0 and `urllib3` from 2.6.3 to
  2.7.0 in the AIG service requirements.
- **Documentation**: README updated with optimized RTSP pipeline details, Web UI local
  setup tips, bounding box configuration guidance, Geti model deployment fixes, and updated
  DL Streamer Pipeline Server image tag.

**Fixed**

- **Object Detection Model Path**: Corrected the YOLO model path in `pid/config.json` from
  `yolo_models/` to `object_detection/`, aligning the configuration with the actual model
  directory layout.
- **Geti Model Path**: Fixed the Geti-based object detection model path referenced in the
  README and deployment configuration.

---
