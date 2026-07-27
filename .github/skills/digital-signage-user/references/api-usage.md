# REST API Usage

All nine endpoints of the AIG server, with runnable `curl` examples.
`docs/user-guide/api-reference.md` documents only four of these.

## Reaching the API

The AIG server listens on port 5003 **inside** the compose network and is not published. Two
ways in:

**Through nginx** (from the host — note the `/aig-api/` prefix is stripped before forwarding,
and `-k` is needed for the self-signed certificate):

```bash
curl -k https://localhost:5000/aig-api/aig/hstatus/1
```

**From inside the network** (useful when isolating whether nginx is the problem):

```bash
docker exec web-ui curl -s http://aig-server:5003/aig/hstatus/1
```

Interactive Swagger UI is at `https://localhost:5000/swaggerui/`, and the raw spec at
`https://localhost:5000/swagger.json`. The Swagger page is the fastest way to experiment with
the large overlay payloads.

Examples below use the nginx form. Substitute `<HOST>` with `localhost` or your `HOST_IP`.

---

## Endpoint summary

| Method | Path | Purpose |
|---|---|---|
| GET | `/aig/hstatus/<int:id>` | Health check — echoes the id back |
| GET | `/aig/versions` | Component and dependency versions |
| POST | `/aig/minf/` | Generate an ad image with SDXL-Turbo. Returns JPEG |
| POST | `/ase/predef/` | Store or update a predefined ad |
| GET | `/ase/predef/<id>` | Fetch one predefined ad |
| DELETE | `/ase/predef/<id>` | Delete one predefined ad |
| POST | `/ase/predef/query` | Semantic search, returns matching ads unmodified |
| POST | `/ase/predef/query/ad` | Semantic search, returns a **list** with overlays applied |
| POST | `/ase/predef/query/firstad` | Same, returns a **single JPEG** |

---

## Health and version

```bash
curl -k https://<HOST>:5000/aig-api/aig/hstatus/1
# {"status": "ok", "id": 1}

curl -k https://<HOST>:5000/aig-api/aig/versions
# [{"component": "...", "version": "...", "observation": "...", "lastverification": "..."}, ...]
```

`hstatus` is the cheapest liveness probe — it touches no models and no database, so a success
here with failures elsewhere localizes the problem past the web tier.

---

## Generate an ad — `POST /aig/minf/`

Returns `image/jpeg` on success. Only `description` and `device` are required.

```bash
curl -k -X POST https://<HOST>:5000/aig-api/aig/minf/ \
  -H 'Content-Type: application/json' \
  -o ad.jpg \
  -d '{
    "description": "A 35mm photo of fresh bananas on a market stall, 8k",
    "device": "GPU"
  }'
```

Response codes: `200` JPEG, `500` unavailable device or invalid generated image, `503` after
three failed generation attempts.

`device` must be one of `CPU`, `GPU`, `NPU`, and must be present on the host — it is checked
against OpenVINO's `available_devices`. Match it to `AIG_MODEL_DEVICE` or the server builds a
fresh pipeline for the request instead of reusing the preloaded one, which is much slower.

### Overlay options

Five optional nested objects decorate the generated image. **Currently only `promo_details`,
`framed_details` and `logo_details` take effect** — the price and slogan blocks are commented
out in `aig/src/server/apis/modelinf.py`, though the API still accepts and validates them. Use
`/ase/predef/query/ad` if you need price or slogan rendering today.

Applied in order: price *(inert)* → promo → frame → logo → slogan *(inert)*.

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

## Predefined ads

### Store — `POST /ase/predef/`

The image must be **JPEG** encoded as base64. `id` is optional; the server assigns one if
omitted.

```bash
IMG=$(base64 -w0 web-ui/pre-defined-ads/oranges.jpg)
curl -k -X POST https://<HOST>:5000/aig-api/ase/predef/ \
  -H 'Content-Type: application/json' \
  -d "{\"id\": 431937, \"description\": \"Fresh oranges promotion\", \"imgb64\": \"$IMG\", \"source\": \"Marketing\"}"
# {"message": "Success"}
```

The description is what semantic search matches against, so it matters more than the id — write
it the way a detected product would be described.

Posting an existing id updates that entry. The web UI does exactly this at startup for every
`ProductAssociations.csv` row naming a `pre_defined_ad_image`.

### Fetch and delete

```bash
curl -k https://<HOST>:5000/aig-api/ase/predef/431937      # 200 with base64 image, or 404
curl -k -X DELETE https://<HOST>:5000/aig-api/ase/predef/431937
```

### Search — `POST /ase/predef/query`

Returns matching ads **as stored**, with no overlays. Best for diagnosing threshold problems.

```bash
curl -k -X POST https://<HOST>:5000/aig-api/ase/predef/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "What is the ad most related to oranges?", "n_results": 3}'
```

Results whose distance exceeds `ASE_DISTANCE_MAX_THRESHOLD` (`0.2` by default) are filtered
out, so an empty response usually means the threshold is too strict rather than that nothing is
stored. Compare against a `GET` of a known id to confirm the ad exists.

### Search with overlays — `POST /ase/predef/query/ad`

Same search, but applies the overlay objects to each result. Returns a **list**. This is the
endpoint the web UI uses, and unlike `/aig/minf/` its price and slogan handling is live.

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

Returns the current ad as JPEG with an `X-Generation-Time` header, or **204 No Content** if the
given `client_id` has already received the current ad. The browser polls this every 2 seconds;
`client_id` is a fingerprint of user agent, resolution, timezone and tab id.

A stream of 204s means the ad generator isn't producing anything new — check web-ui logs, not
the browser.

```bash
curl -k -i "https://<HOST>:5000/get_current_advertisement?width=1920&height=1080&client_id=test1"
```

Using a fresh `client_id` forces a 200 with the current image, which is a quick way to confirm
an ad exists at all.
