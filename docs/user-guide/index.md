# Digital Signage: Context-Aware, Cross-Selling

<!--hide_directive
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/intel-retail/digital-signage/tree/release-2026.2.0/">
     GitHub
  </a>
  <a class="icon_document" href="https://github.com/intel-retail/digital-signage/blob/release-2026.2.0/README.md">
     Readme
  </a>
</div>
hide_directive-->

The Context-Aware, Cross-Selling Digital Signage application is a fully containerized, end-to-end edge AI solution for real-time product detection and dynamic advertisement generation. It is optimized for Intel® platforms in retail and similar environments and follows a microservices design pattern.

**Key Features:**

- **Product Provisioning:** Configure product items with predefined advertisements, slogans, promotional offers, and pricing.
- **Context-Aware Detection:** Real-time product identification from video streams (file-based or RTSP camera input).
- **Cross-Sell & Up-Sell Recommendations:** Intelligent suggestion logic based on detected products and contextual data.
- **Hybrid Advertisement Display:** Serves predefined ads or generates dynamic ads via generative AI when not provisioned.
- **Interactive Web Interface:** Live video stream visualization with near real-time advertisement rendering.
- **Containerized Deployment:** Single-node deployment via Docker Compose.
- **Intel® Optimized AI Pipeline:** DL Streamer Pipeline Server for video analytics and OpenVINO™ GenAI for dynamic ad generation.

## Core Services

| Service                             | Description                                                                                      |
| ----------------------------------- | ------------------------------------------------------------------------------------------------ |
| **PID (Product Identification)**    | Detects products from video streams using DL Streamer Pipeline Server and YOLO models.           |
| **AIG (Advertise Image Generator)** | Generates dynamic advertisements using Stable Diffusion XL Turbo and MiniLM via OpenVINO™ GenAI. |
| **ASe (Advertise Searcher)**        | Retrieves and ranks relevant predefined ads from ChromaDB vector search.                         |
| **Web UI**                          | Displays the live video stream and current advertisements in a browser-based interface.          |

**Supporting Services:** MediaMTX (WebRTC relay), Mosquitto (MQTT broker), ChromaDB (vector database), COTURN (TURN server for WebRTC).

## User Guide

- [Get Started](./get-started.md)
- [How It Works](./how-it-works.md)
- [How-to Guides](./how-to-guides.md)
- [API Reference](./api-reference.md)
- [Troubleshooting](./troubleshooting.md)
- [Release Notes](./release-notes.md)

<!--hide_directive
:::{toctree}
:hidden:

get-started
how-it-works
how-to-guides
api-reference
troubleshooting
Release Notes <./release-notes.md>

:::
hide_directive-->
