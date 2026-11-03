# Pipeline and Runtime Config

The GStreamer pipeline, nginx routing, and compose wiring — the non-Python configuration a code
change often has to move with it.

## Contents

- [The pipeline](#the-pipeline)
- [Payload destinations](#payload-destinations)
- [Changing the source](#changing-the-source)
- [Changing the detection model](#changing-the-detection-model)
- [nginx routing](#nginx-routing)
- [Compose wiring](#compose-wiring)

## The pipeline

`configs/pid/config.json` defines one pipeline, `items_detection`, with `auto_start: true` and
`queue_maxsize: 50`:

```
multifilesrc loop=TRUE location=/home/pipeline-server/resources/externalvideos/test_shopping_items.avi name=source
  ! h264parse ! decodebin ! videoconvert ! video/x-raw,format=BGR
  ! gvadetect name=detection
  ! queue
  ! gvawatermark displ-cfg="font-scale=1.5,thickness=3,color-idx=2,font-type=plain"
  ! gvafpscounter
  ! appsink name=destination
```

Element by element:

| Element | Role |
|---|---|
| `multifilesrc loop=TRUE` | Replays the file endlessly — what makes the demo run unattended |
| `h264parse ! decodebin` | The source file must contain H.264; another codec parses as garbage |
| `videoconvert ! video/x-raw,format=BGR` | `gvadetect` needs BGR |
| `gvadetect name=detection` | Inference. Model and device come from the payload block, not here |
| `queue` | Decouples inference from the overlay/sink so a slow sink can't stall detection |
| `gvawatermark` | Burns detection boxes into the frame |
| `gvafpscounter` | Logs throughput — useful when diagnosing pipeline slowness |
| `appsink name=destination` | Where the pipeline server picks up frames and metadata |

The `name=` attributes are load-bearing: `name=detection` is how the payload parameters bind to
the element, and `name=source` / `name=destination` are the pipeline server's conventional
handles. Renaming them breaks the binding silently.

`gvawatermark` draws the boxes into the frame itself, which is why the WebRTC destination sets
`overlay: false` — the overlay is already there. Setting both would double-draw.

## Payload destinations

```json
"payload": {
    "destination": {
        "metadata": { "type": "mqtt",   "topic": "yolo_od_results" },
        "frame":    { "type": "webrtc", "peer-id": "samplestream", "overlay": false }
    },
    "parameters": {
        "detection-properties": {
            "model": "/home/pipeline-server/object_detection/yolo11s/INT8/yolo11s.xml",
            "device": "CPU"
        }
    }
}
```

Both destination values are contracts with other services:

- **`topic: yolo_od_results`** must match what the web UI subscribes to,
  `os.getenv('MQTT_TOPIC', 'yolo_od_results')`. `MQTT_TOPIC` isn't in `.env`, so the fallback is
  what's in use — change the topic and you must change both places.
- **`peer-id: samplestream`** must match the path nginx proxies (`location ^~ /samplestream/`)
  and the iframe URL the templates build (`${window.location.origin}/samplestream/`). Three
  places, one string.

Note the model path is the **container** path — `configs/pid/models/object_detection/` on the
host is mounted at `/home/pipeline-server/object_detection/`. The `device` value may be `CPU`,
`GPU` or `NPU`; GPU/NPU also need the host device mounted (the Makefile sets `DRI_MOUNT_PATH` /
`ACCEL_MOUNT_PATH` from `/dev/dri` and `/dev/accel`, else `/dev/null`). Note that
`make benchmark-*` runs `benchmark-configure-devices`, which **rewrites this `device` value**
(from `PID_DEVICE`, default `CPU`) in `configs/pid/config.json` and `AIG_INFERENCE_DEVICE` in
`.env`; pass `SKIP_BENCHMARK_DEVICE_CONFIG=true` to keep your edits.

## Changing the source

Videos live in `configs/pid/videos/`, mounted at
`/home/pipeline-server/resources/externalvideos/`. To switch files, change only the filename in
`location=`.

For a live camera, replace the head of the pipeline:

```
rtspsrc location=rtsp://user:pass@10.0.0.42:554/stream1 latency=100
  ! rtph264depay ! h264parse ! decodebin ! videoconvert ! video/x-raw,format=BGR
  ! gvadetect name=detection ! queue ! gvawatermark displ-cfg="..." ! gvafpscounter ! appsink name=destination
```

Two differences from the file source: `rtspsrc` needs `rtph264depay` to strip RTP framing before
`h264parse`, and `loop=TRUE` is meaningless on a live stream. `RTSP_CAMERA_IP` exists in `.env`
but nothing interpolates it automatically.

## Changing the detection model

Update `model` (and add `model-proc` if the model needs custom output parsing):

```json
"detection-properties": {
    "model":      "/home/pipeline-server/object_detection/my_model/my_model.xml",
    "model-proc": "/home/pipeline-server/object_detection/my_model/my_model.json",
    "device": "CPU"
}
```

The step that bites: **class labels must survive normalization into `ProductAssociations.csv`
keys**. The web UI lowercases and converts `-`/`_` to spaces, then looks up the result. A model
emitting `Orange_Fruit` never matches a CSV row for `orange`, and the failure is silent —
detections render in the video while no ad ever fires. Either align the CSV or extend
`normalize_product_key` in `web-ui/main.py`.

`device` here is independent of `AIG_MODEL_DEVICE`; this one is detection, that one is
generation.

## nginx routing

`configs/nginx/nginx.conf` is a template — `nginx-cert-gen.sh` runs `envsubst` over
`$MEDIAMTX_SERVER` and `$WHIP_SERVER_PORT` at container start, then generates a self-signed
RSA-3072/SHA-384 certificate with `CN=localhost`, valid 365 days, regenerated on every start. The
cert carries a SAN list — `localhost`, `127.0.0.1`, `host.docker.internal`, plus `HOST_IP` (compose
passes it to the nginx container) — so clients other than literal `localhost` can verify it
(still self-signed, so they must trust it or use `-k`).

One server block, `listen 15443 ssl`, TLSv1.3 only, `secp384r1`, HSTS + `X-Content-Type-Options`
+ `X-Frame-Options SAMEORIGIN`, `client_max_body_size 500M` (large because ads travel as base64).

| Location | Upstream | Notes |
|---|---|---|
| `/dsps-api/` | `dlstreamer-pipeline-server:8080/` | Trailing slash on `proxy_pass` strips the prefix |
| `/aig-api/` | `aig-server:5003/` | Same prefix stripping; adds `X-Forwarded-Prefix: /aig-api` (aig-server doesn't read it) |
| `/swaggerui/` | `aig-server:5003/swaggerui/` | |
| `= /swagger.json` | `aig-server:5003/swagger.json` | Exact match; `sub_filter` rewrites `"basePath": "/"` to `/aig-api` so Swagger "Try it out" hits the proxy path |
| `/mcp` | `web-ui:5100` | MCP Streamable HTTP; 400 s read timeout. A bare prefix `location /mcp` (no trailing slash) so FastMCP's `/mcp` is proxied directly rather than via a slash redirect that would report the wrong scheme/host |
| `~ ^/samplestream/(whip\|whep)(/.*)?$` | `${MEDIAMTX_SERVER}:${WHIP_SERVER_PORT}$request_uri` | Regex — wins over the prefix rule below. CORS `*`, 300s timeouts |
| `^~ /samplestream/` | `${MEDIAMTX_SERVER}:${WHIP_SERVER_PORT}` | 300s timeouts |
| `/` | `web-ui:5000/` | Catch-all |

Ordering matters here: nginx evaluates regex locations before prefix locations, which is what
lets the WHIP/WHEP rule take precedence over `^~ /samplestream/`. The `^~` on the prefix rule
would otherwise suppress regex matching. Don't reorder these casually.

New endpoints under `/aig/` or `/ase/` need **no** nginx change — they're already covered by
`/aig-api/`. New MCP tools need none either — they're served from the same `/mcp` endpoint. A new
top-level prefix, or a new service, needs a new `location` block plus a `depends_on` entry, since
nginx resolves upstreams at config-load time and fails to start if one doesn't resolve.

`proxy_buffering off` is set throughout because responses are images and streams. Keep it for
anything new that returns binary.

There's a commented-out `stream {}` block for TLS-wrapping MQTT on 1883 (its upstream still uses
the old `ia-mqtt-broker` name; the service is `mqtt-broker`). Enabling it also needs the port
published in `docker-compose.yml`.

## Compose wiring

Adding an environment variable takes **three** edits, and skipping any one means it never reaches
the process:

1. `.env` — the value, with a comment
2. `docker-compose.yml` — the service's `environment:` block
3. The code — an accessor with a default matching `.env` (for AIG, a static method in
   `aig/src/database/version.py`; for web-ui, an `os.getenv` near the other constants)

Other compose facts that shape changes:

- The eight default services are `read_only: true` with `no-new-privileges`. Anything that needs
  to write needs an explicit volume or tmpfs — aig-server and the pipeline server bind the
  host's `/tmp`, while web-ui mounts a tmpfs `/tmp` (compose notes it as scratch space for video
  clips).
- Published ports are bound to `${HOST_IP:-127.0.0.1}` (nginx 5000, coturn). `HOST_IP` must be an
  IPv4 — `validate_host_ip` rejects `localhost` — and it also feeds the TURN URL and the nginx
  cert SAN. The `model-download` service is the one exception: it is behind the
  `model-download` profile (not started by `docker compose up`), publishes
  `127.0.0.1:${MODEL_DOWNLOAD_PORT:-8000}`, and mounts `configs/pid/models/object_detection` and
  `aig/models` so `scripts/download_models.sh` can fill them.
- `aig-server` bind-mounts `./aig/src` at `/home/aigserver/src`, so Python edits there apply on
  `docker restart aig-server`. `web-ui` has no source mount and needs a rebuild. aig-server also
  bind-mounts `${AIG_NPU_CACHE_HOST_DIR:-./aig/npu_cache}` at `/opt/npu_cache`; `make up` creates
  that directory, and it must be writable by `UID`.
- Some `.env` keys are renamed on the way in: `AIG_INFERENCE_DEVICE` → `AIG_MODEL_DEVICE`
  (aig-server) and `AIG_VIDEO_INFERENCE_DEVICE` → `AIG_VIDEO_MODEL_DEVICE`. web-ui gets the
  `.env` names. `VIDEO_AD_DISPLAY_SECONDS` (web-ui) must equal `AIG_VIDEO_LOOP_SECONDS`
  (aig-server); nothing enforces it.
- `BENCHMARK_MODE` is passed to aig-server and web-ui from the Makefile (`make up` → `false`
  by default; `make benchmark-*` → `true`), not defined in `.env`.
- `ase-qdrant` mounts `qdrant_data` at `/qdrant/storage` and `qdrant_snapshots` at
  `/qdrant/snapshots`; both are dropped by `make down` (`down -v`).
- `docker-compose.yml` passes `BASE_IMAGE: "ubuntu:22.04"` as a build arg to `aig`, but the
  Dockerfile hardcodes `FROM ubuntu:24.04` and never reads it. Don't trust that arg.
- `build_copyleft_sources` passes `COPYLEFT_SOURCES=true`, which neither Dockerfile consumes.
- Compose passes `UID`, `USER`, and the proxy variables as build args to both custom images; the
  Dockerfiles declare only `USER` and `UID` (the proxy variables are Docker's predefined build
  args).

`make up` runs `down` first (unless `UP_SKIP_DOWN=true`, which the benchmark targets use after
their own `down`), so any config change reaches the containers through `make up`, never
`docker restart` — except the `aig/src` bind mount noted above. `make up` is gated by
`check_env_variables` (WebRTC credentials), `validate_host_ip` and `check_models`.

Benchmarking (`make benchmark-pid|aig|web-ui|qdrant|metrics|e2e|all`, `consolidate-benchmarks`)
needs the `performance-tools` git submodule — empty until `make update-submodules`. The targets
reset the stack, wait `BENCHMARK_WARMUP_SECONDS` (300), and write results under
`results/<run-id>/`.
