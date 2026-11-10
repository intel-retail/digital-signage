# REST API Usage

All ten operations (nine paths) of the AIG server, with runnable `curl` examples, plus the nginx
URL map and the web UI endpoint. `docs/user-guide/api-reference.md` documents only three of the
AIG operations (`/aig/minf/`, `POST /ase/predef/`, `/ase/predef/query/ad`).

## Reaching the API

The AIG server listens on port 5003 **inside** the compose network and is not published. Two
ways in:

**Through nginx** (from the host — note the `/aig-api/` prefix is stripped before forwarding,
and `-k` is needed for the self-signed certificate):

```bash
curl -k https://<HOST_IP>:5000/aig-api/aig/hstatus/1
```

nginx is published only on `HOST_IP` (default `127.0.0.1`), so use that address — `localhost`
only works while `HOST_IP=127.0.0.1`. Request bodies up to 500 MB are accepted (base64 images).

**From inside the network** (useful when isolating whether nginx is the problem):

```bash
docker exec web-ui curl -s http://aig-server:5003/aig/hstatus/1
```

Interactive Swagger UI is at `https://<HOST_IP>:5000/swaggerui/`, and the raw spec at
`https://<HOST_IP>:5000/swagger.json` (nginx rewrites its `basePath` to `/aig-api` so "Try it
out" works). The Swagger page is the fastest way to experiment with the large overlay payloads.

Everything nginx exposes on `https://<HOST_IP>:5000`:

| URL prefix | Goes to | Notes |
|---|---|---|
| `/` | web-ui (Flask, :5000) | UI (`/`, `/portrait`), `/get_current_advertisement`, and `/ad_rendered` (404 unless `BENCHMARK_MODE=true`) |
| `/aig-api/` | aig-server (:5003), prefix stripped | The AIG/ASe endpoints below |
| `/swaggerui/`, `/swagger.json` | aig-server | Swagger UI and spec |
| `/dsps-api/` | dlstreamer-pipeline-server (:8080), prefix stripped | DL Streamer Pipeline Server REST API (pipeline status/management); see its upstream docs |
| `/mcp` | web-ui MCP server (:5100) | Streamable HTTP; see `docs/user-guide/how-to-guides/use-mcp-agent-tools.md` |
| `/samplestream/` | MediaMTX (:8889) | WebRTC page; `/samplestream/whip` and `/whep` are the signalling routes |

Examples below use the nginx form. Substitute `<HOST>` with your `HOST_IP` value.

---

## Endpoint summary

| Method | Path | Purpose |
|---|---|---|
| GET | `/aig/hstatus/<int:id>` | Health check — echoes the id back |
| GET | `/aig/versions` | AIG version plus every installed Python package and version |
| POST | `/aig/minf/` | Generate an ad image with SDXL-Turbo. Returns JPEG |
| POST | `/aig/mvid/` | Generate an ad video with LTX-Video. Returns an animated WEBP |
| POST | `/ase/predef/` | Store or update a predefined ad |
| GET | `/ase/predef/<id>` | Fetch one predefined ad |
| DELETE | `/ase/predef/<id>` | Delete one predefined ad |
| POST | `/ase/predef/query` | Semantic search, returns matching ads unmodified |
| POST | `/ase/predef/query/ad` | Semantic search, returns a **list** with overlays applied |
| POST | `/ase/predef/query/firstad` | Same, returns a **single JPEG** |

`/aig/*` is the generation namespace, `/ase/*` the Qdrant-backed predefined-ad search.

---

## Health and version

```bash
curl -k https://<HOST>:5000/aig-api/aig/hstatus/1
# {"status": "ok", "id": 1}

curl -k https://<HOST>:5000/aig-api/aig/versions
# [{"component": "AIG Server", "version": "<IMAGE_SUFFIX>", "observation": "...", "lastverification": "..."}, ...]
```

`hstatus` is the cheapest liveness probe — it touches no models and no database, so a success
here with failures elsewhere localizes the problem past the web tier. `versions` lists every
installed package, so the output is long.

---

## Generate an ad — `POST /aig/minf/`

Returns `image/jpeg` on success. Only `description` and `device` are required. The image size is
`AIG_IMG_WIDTH_DEFAULT` x `AIG_IMG_HEIGHT_DEFAULT`; there is no per-request size.

```bash
curl -k -X POST https://<HOST>:5000/aig-api/aig/minf/ \
  -H 'Content-Type: application/json' \
  -o ad.jpg \
  -d '{
    "description": "A 35mm photo of fresh bananas on a market stall, 8k",
    "device": "GPU"
  }'
```

Response codes: `200` JPEG, `500` unsupported/unavailable device or invalid generated image,
`503` after three failed generation attempts **or** when the preloaded model for the configured
device failed to load (`Device ... unavailable: model failed to load`; retried after 5 minutes).

`device` must be one of `CPU`, `GPU`, `NPU`. Match it to `AIG_INFERENCE_DEVICE` (the server's
`AIG_MODEL_DEVICE`) or the server builds a fresh pipeline for the request instead of reusing the
preloaded one, which is much slower. An optional integer `seed` makes generation reproducible
(same seed and similar prompt gives a structurally similar image).

### Overlay options

Five optional nested objects decorate the generated image. **`price_details`, `promo_details`,
`framed_details` and `logo_details` take effect; `slogan_details` is accepted and validated but
the slogan step is a deliberate no-op** in `aig/src/server/apis/modelinf.py`. Use
`/ase/predef/query/ad` if you need slogan rendering.

Applied in order: price → promo → frame → logo → slogan *(inert)*. The price is only drawn when
`price` is non-empty.

```bash
curl -k -X POST https://<HOST>:5000/aig-api/aig/minf/ \
  -H 'Content-Type: application/json' -o ad.jpg \
  -d '{
    "description": "Fresh oranges in a wooden crate, studio lighting",
    "device": "GPU",
    "promo_details": {
      "promo_text": "Buy 1, Get 50% off the 2nd",
      "text_color": "white", "rect_color": "black",
      "rect_padding": 10, "rect_radius": 20,
      "align": "center", "valign": "bottom",
      "marperc_from_border": 2.0, "font_size": 20, "line_width": 20
    },
    "framed_details": { "activate": true, "marperc_from_border": 2.0 },
    "logo_details": { "align": "left", "valign": "top", "logo_percentage": 25.0, "margin_px": 10 }
  }'
```

Field reference for all five objects:

| Object | Fields |
|---|---|
| `price_details` | `price`, `align`, `valign`, `marperc_from_border`, `font_size`, `line_width`, `price_color`, `price_in_circle`, `price_circle_color` |
| `promo_details` | `promo_text`, `text_color`, `rect_color`, `rect_padding`, `rect_radius`, `align`, `valign`, `marperc_from_border`, `font_size`, `line_width` |
| `logo_details` | `align`, `valign`, `logo_percentage`, `margin_px` |
| `slogan_details` | `slogan_text`, `text_color`, `align`, `valign`, `marperc_from_border`, `font_size`, `line_width` |
| `framed_details` | `activate` *(boolean — not `framed`)*, `marperc_from_border` |

`align` is `left|center|right`, `valign` is `top|middle|bottom`. Colors are PIL named colors;
an invalid name silently falls back to the default rather than erroring. `marperc_from_border`
is a percentage of image size, not pixels — which is why the web UI scales `font_size` and
`logo_percentage` to the browser's reported dimensions.

Beware `framed_details`: the schema is defined twice in the source under the same name, once
with an `activate` field and once with `framed`. The handler reads **`activate`**; sending
`framed` silently does nothing.

---

## Generate an ad video — `POST /aig/mvid/`

Optional feature; needs the LTX-Video model (`AIG_VIDEO_MODEL_PATH`, `make download_models`).
Same body as `/aig/minf/` (including `seed` and the five overlay objects, applied to every
frame; the slogan is again a no-op). Returns `image/webp` — an **animated WEBP** that loops over
`AIG_VIDEO_LOOP_SECONDS`. `device` must be `CPU` or `GPU` for this model (use
`AIG_VIDEO_INFERENCE_DEVICE`); `NPU` isn't supported by it.

```bash
curl -k --max-time 900 -X POST https://<HOST>:5000/aig-api/aig/mvid/ \
  -H 'Content-Type: application/json' -o ad.webp \
  -d '{
    "description": "A cup of coffee with steam rising, commercial product video, subtle natural motion",
    "device": "GPU",
    "seed": 12345
  }'
```

Expect about 30 s on an Intel iGPU with the default `f16` precision once the model is loaded
(~3 minutes with `f32`; the first request also loads the model unless
`AIG_PRELOAD_VIDEO_MODEL=true`). Codes: `200` WEBP, `500` unsupported device, no
`AIG_VIDEO_MODEL_PATH`, unavailable device or model missing, `503` after three failed attempts.
The web UI never calls this from the camera flow; only the MCP `trigger_video_ad` tool does, with
a 15-minute timeout.

---

## Predefined ads

Backed by Qdrant. Ids must be integers (they become Qdrant point ids).

### Store — `POST /ase/predef/`

The image must be **JPEG** encoded as base64. `id` is optional; the server assigns a random one if
omitted. Returns `400` for a missing/invalid image or a non-JPEG format, `500` if storing fails
(for example ASe not initialized).

```bash
IMG=$(base64 -w0 web-ui/pre-defined-ads/apple_orange.jpg)
curl -k -X POST https://<HOST>:5000/aig-api/ase/predef/ \
  -H 'Content-Type: application/json' \
  -d "{\"id\": 431937, \"description\": \"Fresh oranges promotion\", \"imgb64\": \"$IMG\", \"source\": \"Marketing\"}"
# {"message": "Success"}
```

The description is what semantic search matches against, so it matters more than the id — write
it the way a detected product would be described.

Posting an existing id updates that entry. The web UI POSTs every `ProductAssociations.csv` row
naming a `pre_defined_ad_image` at startup **without an id**, so each run adds new entries
(a fresh `make down && make up` clears them).

### Fetch and delete

```bash
curl -k https://<HOST>:5000/aig-api/ase/predef/431937      # 200 with base64 image, or 404
curl -k -X DELETE https://<HOST>:5000/aig-api/ase/predef/431937   # 200, or 404 if absent
```

### Search — `POST /ase/predef/query`

Returns matching ads **as stored**, with no overlays. Best for diagnosing threshold problems.

```bash
curl -k -X POST https://<HOST>:5000/aig-api/ase/predef/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "What is the ad most related to oranges?", "n_results": 3}'
```

Results whose cosine similarity is below `ASE_QDRANT_SCORE_MIN_THRESHOLD` (`0.8` by default —
higher is stricter) are dropped, so an empty list `[]` usually means the threshold is too strict
rather than that nothing is stored. No scores are returned. Compare against a `GET` of a known id
to confirm the ad exists, and temporarily set the threshold to `0.0` to see what the nearest
entries are.

### Search with overlays — `POST /ase/predef/query/ad`

Same search, but applies the overlay objects to each result. Returns a **list** of
`{"imgb64": ...}` items (empty when nothing matches). This is the endpoint the web UI uses, and
unlike `/aig/minf/` it also renders the slogan.

```bash
curl -k -X POST https://<HOST>:5000/aig-api/ase/predef/query/ad \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "oranges",
    "n_results": 1,
    "use_default_ad_onempty": false,
    "price_details": { "price": "0.5 $/lb", "align": "right", "valign": "bottom",
                       "font_size": 28, "price_color": "white",
                       "price_in_circle": true, "price_circle_color": "black" },
    "promo_details": { "promo_text": "2 for 1 today", "align": "center", "valign": "bottom" },
    "logo_details":  { "align": "left", "valign": "top", "logo_percentage": 20.0 },
    "slogan_details":{ "slogan_text": "The best price in town", "align": "right", "valign": "top" },
    "framed_details":{ "activate": true }
  }'
```

`use_default_ad_onempty` returns `ASE_IMG_DEFAULT_AD` when the query matches nothing — but that
file (`/opt/sharedata/default_ad.jpg`) is **not present in the repo**, so leave it `false`
unless you have added one to `aig/sharedata/`. The web UI sets it to `false` for this reason,
falling back to dynamic generation instead.

### Single image — `POST /ase/predef/query/firstad`

Identical body; `n_results` is forced to 1 and the response is a raw JPEG rather than JSON.
Convenient for eyeballing a result:

```bash
curl -k -X POST https://<HOST>:5000/aig-api/ase/predef/query/firstad \
  -H 'Content-Type: application/json' -o result.jpg \
  -d '{"query": "oranges", "n_results": 1, "use_default_ad_onempty": false}'
```

---

## Web UI endpoint

`GET /get_current_advertisement?width=<w>&height=<h>&client_id=<id>`

Returns the current ad with an `X-Generation-Time` header: a JPEG for image ads, or the clip
itself (`image/webp` for generated video ads; `video/mp4`/`image/gif` for predefined videos) while
an MCP video ad is live. Returns **204 No Content** if the given `client_id` has already received
the current ad, or after it has received a live video ad until that ad expires. The browser polls
this every 2 seconds; `client_id` is a fingerprint of user agent, resolution, timezone and tab id.
While an MCP-triggered image ad is live (`display_seconds`, default 60) it is returned on every
poll, so you get 200s rather than 204s.

A stream of 204s with no video playing means the ad generator isn't producing anything new —
check web-ui logs, not the browser.

```bash
curl -k -i "https://<HOST>:5000/get_current_advertisement?width=1920&height=1080&client_id=test1"
```

Using a fresh `client_id` forces a 200 with the current image, which is a quick way to confirm
an ad exists at all.

The other web UI routes are `/` and `/portrait` (HTML pages) and `POST /ad_rendered`, a
benchmark-only timing sink that returns 404 unless `BENCHMARK_MODE=true`. The MCP tools
(`/mcp`) are covered in `docs/user-guide/how-to-guides/use-mcp-agent-tools.md`.
