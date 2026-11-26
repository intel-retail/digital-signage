# Container Images

## Digital Signage Web UI

The Digital Signage Web UI is a Flask service that receives product detections over MQTT, filters them across recent frames, and selects cross-sell products using `ProductAssociations.csv`. It looks for a predefined ad through the Advertise Searcher (ASe) and requests an AI-generated image from AIG if no match is found. The browser displays the current ad alongside the live WebRTC stream from MediaMTX.

The Web UI also exposes a Model Context Protocol (MCP) server so external agents can inspect the display, trigger image or video ads, and clear agent-triggered ads.

## Advertise Image Generator Server

The Advertise Image Generator (AIG) server uses OpenVINO™ GenAI to generate ad images from text with Stable Diffusion XL Turbo (`POST /aig/minf/`). The API accepts optional overlays such as price, promotion text, and a slogan. Image generation runs on CPU or GPU, with experimental Intel NPU support.

With the optional LTX-Video model, the server can also generate looping video ads on CPU or GPU (`POST /aig/mvid/`). The same container hosts the Advertise Searcher (ASe) API, which stores and searches predefined ads in Qdrant.

## Supported Versions

> **Note**: The tags suffixed with `-weekly` and `-rcX` are developmental builds, may not be stable.

### [2026.3.0](https://docs.openedgeplatform.intel.com/2026.3/edge-ai-suites/ai-suite-retail/digital-signage/release-notes.html#version-2026-3-0)

#### Deploy using Docker Compose

For more details on deployment, refer to the [documentation](https://docs.openedgeplatform.intel.com/2026.3/edge-ai-suites/ai-suite-retail/digital-signage/get-started.html)


### [2026.2.0](https://docs.openedgeplatform.intel.com/2026.2/edge-ai-suites/ai-suite-retail/digital-signage/release-notes.html#version-2026-2-0)

#### Deploy using Docker Compose

For more details on deployment, refer to the [documentation](https://docs.openedgeplatform.intel.com/2026.2/edge-ai-suites/ai-suite-retail/digital-signage/get-started.html)

## License Agreement
---
Copyright (C) 2026 Intel Corporation.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

## Legal Information
---
Intel, the Intel logo, and Xeon are trademarks of Intel Corporation in the U.S. and/or other countries.

*Other names and brands may be claimed as the property of others.
