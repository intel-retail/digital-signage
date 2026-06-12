# API Reference

This page documents the REST APIs exposed by the Digital Signage microservices.

## AIG (Advertise Image Generator) API

**Base URL:** `https://<HOST_IP>:5000/aig-api/`

### `POST /aig/minf/`

Generates an advertisement image from text input and optional overlay parameters.

**Request Body (JSON):**

```json
{
  "prompt": "string",      // Description for image generation (required)
  "logo_path": "string",   // Path to logo file (optional)
  "slogan": "string",      // Slogan text to overlay (optional)
  "price": "string"        // Price text to overlay (optional)
}
```

**Response:** Generated advertisement image (binary or base64-encoded).

---

### `POST /ase/predef/`

Stores a predefined advertisement image and its metadata in ChromaDB.

**Request Body:** Ad metadata and image data.

---

### `POST /ase/predef/query/ad`

Queries ChromaDB for predefined advertisements matching the given product or context.

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

- [DL Streamer Pipeline Server API Reference](https://docs.openedgeplatform.intel.com/2025.2/edge-ai-libraries/dlstreamer-pipeline-server/api-reference.html)
