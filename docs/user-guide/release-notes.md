# Release Notes: Digital Signage

## Version 2026.2.0

**Sep 2026**

This release introduces **multi-object detection with priority-based ad selection**,
**WCL integration for improved product matching**, and **CI/CD GitHub Actions workflows**,
along with a repository reorganization and various dependency upgrades and bug fixes.

**New**

- **Multi-Object Detection**: the web UI now tracks detected objects across a configurable
  number of recent frames and selects the highest-value item for ad generation, with
  configurable ad display duration, confidence threshold, and a new portrait-mode template.
- **WCL Integration**: web UI label normalization maps detected labels to CSV product keys
  using a first-time high-price priority strategy followed by rotation with anti-repeat logic;
  HTTP connections to AIG and ASe are now reused for improved throughput.
- **CI/CD Workflows**: added a GitHub Actions PR workflow that builds images, downloads
  models, and deploys and undeploys the stack, alongside a reusable scans workflow running
  Trivy, Bandit, ClamAV, Docker Bench Security, CodeQL, and Pylint.

**Improved**

- **Repository Structure**: PID configuration, models, and videos moved under `configs/pid/`;
  Makefile, Docker Compose mounts, and documentation updated to reflect the new layout.
- **Nginx**: the nginx reverse proxy service is now active in the Docker Compose deployment.
- **AIG Container**: AIG base image updated to Ubuntu 24.04 with aligned container and
  dependency versions.
- **PTL Platform Support**: added Intel PTL platform drivers for the AIG module.
- **Configurable AIG Inference Steps**: AIG inference steps are now configurable via
  the environment.
- **Security**: fixed a vulnerability in web UI request handling; upgraded urllib3,
  diffusers, pillow, requests, and flask to latest available versions.

**Fixed**

- **ChromaDB Startup**: fixed a connectivity issue that prevented the ASe service from
  starting correctly.

---

## Version 1.0.0

**Jan 2026**

This is the initial pre-production release of the **Context-Aware, Cross-Selling Digital
Signage** application, introducing the **full end-to-end containerized stack**, **AIG memory
optimizations**, **container security hardening**, and comprehensive documentation.

**New**

- **Product Identification (PID)**: DL Streamer Pipeline Server with YOLO11s object
  detection publishing results via MQTT, with support for file-based simulation video
  and RTSP live camera input including hardware-optimized decoding for Axis cameras.
- **Advertise Image Generator (AIG)**: dynamic advertisement generation using Stable
  Diffusion XL Turbo (OpenVINO™ int8) and all-MiniLM-L12-v2 sentence embeddings, with
  logo, slogan, and price overlays; lazy-loaded initialization and post-inference model
  unloading reduce runtime memory from ~10 GB to ~2 GB.
- **Advertise Searcher (ASe)**: ChromaDB-backed vector search for predefined advertisements
  via REST API endpoints.
- **Business Offer Recommendations (BOR)**: server and scripts for product association
  rules, weekly and hourly product probability models, transaction database, and
  MQTT-based integration.
- **Product Category Association (PCA)**: association rules engine with product and
  transaction APIs, weekly and weekly-hh24 probability processing, and MQTT topic
  management.
- **Web UI**: browser-based interface serving a live WebRTC video stream alongside
  dynamically generated or predefined advertisements, with Intel One Mono Bold font
  for price and label overlays.
- **Supporting Services**: MediaMTX for WebRTC relay, Mosquitto MQTT broker, ChromaDB
  vector database, COTURN TURN server, and nginx reverse proxy.
- **iGPU/NPU Device Detection**: Docker Compose device mounts for DRI and ACCEL are
  conditional, falling back gracefully on systems without GPU or NPU.

**Improved**

- **Security**: all services run as non-root users with dedicated accounts,
  no-new-privileges option enforced, read-only filesystems applied to ChromaDB and
  other containers, public ports bound to localhost, broad device mounts replaced with
  specific mappings, and Trivy, Bandit, and Docker Bench Security findings resolved.
- **Documentation**: comprehensive README with quick-start, system requirements,
  architecture overview, and advanced configuration; RTSP camera enablement steps added;
  legacy install scripts removed in favour of unified Makefile-based workflows;
  third-party license documentation added.

<!--hide_directive
#:::{toctree}
#:hidden:
#Release Notes 2026 <./release-notes/release-notes-2026>
#:::
hide_directive-->
