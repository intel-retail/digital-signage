# Release Notes 2026

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
