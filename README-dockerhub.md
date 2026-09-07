# Container Images

## Digital Signage Web UI

The Digital Signage web UI is a Flask-based microservice that subscribes to product detection events published over MQTT, applies temporal filtering and product-selection logic against `ProductAssociations.csv`, and requests a predefined or AI-generated advertisement (from ASe or AIG) for each selected product. It then serves the live video stream and the current advertisement to browser clients.

## Advertise Image Generator Server

The Advertise Image Generator (AIG) server is an AI microservice that generates dynamic advertisement images using a Stable Diffusion XL Turbo text-to-image model via OpenVINO™ GenAI. It receives product details (price, promo text, slogan) from the Web UI's `/aig/minf/` request and returns a generated ad image when no predefined advertisement is available.

## Supported Versions

> **Note**: The tags suffixed with `-weekly` and `-rcX` are developmental builds, may not be stable.

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
