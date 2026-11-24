# API Reference

This page documents the REST APIs exposed by the Digital Signage microservices.

## AIG (Advertise Image Generator) API

**Base URL:** `https://<HOST_IP>:5000/aig-api/`

### `POST /aig/minf/`

Generates an advertisement image from text input and optional overlay parameters.

**Request Body (JSON):**

```json
{
  "description": "string",      // Text prompt used to generate the image e.g. "A 35mm photo with bananas, 8k" (required)
  "device": "enum",   // Inference device: CPU, GPU, or NPU (required)
  "promo_details": "object",      // Promo banner overlaid on the image (optional)
  "logo_details": "object",        // Logo overlaid on the image (optional)
  "framed_details": "object"        // Double-border frame around the image (optional)
}
```

**Response:** Generated advertisement image (`image/jpeg` binary stream).

---

### `POST /aig/mvid/`

Generates an animated video advertisement from a text description using the optional LTX-Video model. See [Download LTX-Video Model](get-started.md#download-ltx-video-model-optional-for-trigger_video_ad) for setup.

**Request Body (JSON):**

```json
{
  "description": "A 35mm photo with bananas, 8k",
  "device": "GPU",
  "seed": 12345
}
```

`description` and `device` (`CPU` or `GPU` for video generation) are required. Although the request schema also accepts `NPU`, LTX-Video does not support it, and this endpoint does not apply the configuration-driven GPU fallback; requesting `NPU` fails during pipeline creation. `seed` and the `price_details`, `promo_details`, `logo_details`, `slogan_details`, and `framed_details` overlay objects are optional.

**Response:** Generated looping animated WEBP (`image/webp` binary stream).

---

### `POST /ase/predef/`

Stores a predefined advertisement image and its metadata in Qdrant.

**Request Body:** Ad metadata and image data.

---

### `POST /ase/predef/query/ad`

Queries Qdrant for predefined advertisements matching the given product or context.

**Request Body:** Query parameters (product label, context).

**Response:** List of matching predefined advertisement records.

---

## Web UI API

**Base URL:** `https://<HOST_IP>:5000/`

### `GET /get_current_advertisement`

Returns the current advertisement for the requesting browser client.

- Client IDs are tracked per browser session.
- Each client receives a new advertisement once per generation cycle.
- Returns the ad image or a reference to the current ad asset.

---

## PID (Product Identification) API

**Base URL:** `https://<HOST_IP>:5000/dsps-api/`

PID is powered by DL Streamer Pipeline Server. The full REST API reference for pipeline management and status is available at:

- [DL Streamer Pipeline Server API Reference](https://docs.openedgeplatform.intel.com/2026.3/edge-ai-libraries/dlstreamer-pipeline-server/api-reference.html)
