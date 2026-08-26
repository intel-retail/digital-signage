# Release Notes: Digital Signage

## Version 2026.2.0

**Sep 2026**

This release introduces **multi-object detection with priority-based ad selection**,
**WCL integration for improved product matching**, and **CI/CD GitHub Actions workflows**,
along with deployment hardening, expanded user-guide coverage, and various dependency
upgrades and bug fixes.

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
- **Web UI Runtime Configuration**: web UI now uses configurable runtime parameters
  from environment settings, with matching updates in Compose, CI workflows, and
  troubleshooting guidance.
- **Deployment Hardening**: hardened repository download and extraction handling in
  container build and deployment flows to reduce risk from malformed zip payloads.
- **PTL Platform Support**: added Intel PTL platform drivers for the AIG module.
- **Configurable AIG Inference Steps**: AIG inference steps are now configurable via
  the environment.
- **Documentation**: expanded the user guide with setup, API reference, troubleshooting,
  custom-model usage notes, and an updated architecture diagram.
- **Security**: fixed a vulnerability in web UI request handling; upgraded urllib3,
  diffusers, pillow, requests, and flask to latest available versions.

**Fixed**

- **ChromaDB Startup**: fixed a connectivity issue that prevented the ASe service from
  starting correctly.
- **AIG API Proxy Routing**: fixed AIG API endpoint behavior behind nginx so
  proxied requests and swagger-triggered calls resolve to the correct service routes.
- **Nginx Runtime User**: fixed nginx container runtime user mapping to UID 2999 for
  consistent execution in the deployed stack.
- **Tokenizer Compatibility**: fixed an openvino-tokenizers version mismatch in AIG
  requirements and model inference dependency alignment.

---

For information on older versions, check [release notes 1.0.0](./release-notes/release-notes-1.0.0.md)
