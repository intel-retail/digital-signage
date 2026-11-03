# Environment Variable Reference

Every variable in `.env`, what reads it, and what happens if it's wrong.

`.env` is `include`d by the `Makefile`, which then `export`s every key, and is also read by
`docker-compose.yml` for `${VAR}` substitution. Values are read **at container start**, so any
change requires `make up` (which tears down and recreates), not `docker restart`.

## Contents

- [Gating variables](#gating-variables) — these three block `make up`
- [Docker Compose, images and model download](#docker-compose-images-and-model-download)
- [Pipeline server](#pipeline-server-pid)
- [WebRTC and TURN](#webrtc-and-turn)
- [Telemetry](#telemetry)
- [AIG — image generation](#aig--image-generation)
- [AIG — video generation](#aig--video-generation)
- [ASe — semantic ad search](#ase--semantic-ad-search)
- [Web UI — ad behavior](#web-ui--ad-behavior)
- [Compose-only and benchmark variables](#compose-only-and-benchmark-variables)
- [Code defaults that disagree with .env](#code-defaults-that-disagree-with-env)
- [Referenced but absent from .env](#referenced-but-absent-from-env)

---

## Gating variables

`make up` runs three validation targets before starting anything. These are the only variables
that can stop a deployment outright.

| Variable | Validation | Shipped value |
|---|---|---|
| `MTX_WEBRTCICESERVERS2_0_USERNAME` | `^[A-Za-z]{5,}$` — letters only, min 5 | **empty** |
| `MTX_WEBRTCICESERVERS2_0_PASSWORD` | `^[A-Za-z0-9]{8,}$` **and** contains a digit **and** contains a letter | **empty** |
| `HOST_IP` | dotted-quad IPv4, each octet 0–255. **`localhost` and hostnames are rejected** | `127.0.0.1` |

The two credentials ship empty, so **every fresh clone fails `make up` until they are set**.
They are TURN credentials for the coturn server; they are not checked against anything external,
so any conforming value works. `usernam` / `passw0rd1` are valid; `user` (too short) and
`password` (no digit) are not.

Note the validation greps `.env` directly with `cut -d'=' -f2` — a value containing `=` is
truncated, and quotes are kept literally, so don't quote these.

`HOST_IP` does four jobs, which is why the loopback default only suits a browser on the same
machine:

- `nginx` (host port 5000) and `coturn` (3478 TCP+UDP) are published as
  `${HOST_IP:-127.0.0.1}:<port>`, so with `127.0.0.1` nothing is reachable from another machine —
  not just WebRTC.
- It becomes the TURN URL handed to the browser: `turn:${HOST_IP}:${COTURN_UDP_PORT}`.
- It is appended to `no_proxy` for the pipeline server, MediaMTX and nginx.
- nginx adds it to the self-signed certificate's Subject Alternative Names (alongside `localhost`,
  `127.0.0.1`, `host.docker.internal`), regenerated on every nginx start.

For remote access set the host's real IPv4 (`hostname -I | awk '{print $1}'`) and run `make up`
so the containers are recreated with the new port bindings.

There is a fourth gate that isn't a variable: `make check_models` fails unless these files exist
and are non-empty: `configs/pid/models/object_detection/yolo11s/INT8/yolo11s.{xml,bin}`,
`aig/models/sdxl_turbo_ov/int8/graph.pbtxt` and `aig/models/all-MiniLM-L12-v2/config.json`. It
does not look at the LTX-Video model, so a missing video model never blocks `make up`.

---

## Docker Compose, images and model download

| Variable | Default | Notes |
|---|---|---|
| `COMPOSE_HTTP_TIMEOUT` | `200` | Raise if builds time out on a slow link |
| `COMPOSE_PROJECT_NAME` | `digitalsignage` | Prefixes networks and volumes |
| `DOCKER_REGISTRY` | *(empty)* | Prefixed to **every** image name, including the model-download and DL Streamer images, so a wrong value breaks pulls. Include the trailing `/`, e.g. `localhost:5000/`. Also what `make push_images` pushes to |
| `IMAGE_SUFFIX` | `2026.3.0` | Tag of the locally built `aig-server` and `web-ui` images (`intel/aig-server`, `intel/digital-signage-webui`); also reported by `/aig/versions` as the AIG version. Empty falls back to the tag `latest` |
| `WEEKLY_BUILD_DATE` | *(empty)* | `yyyymmdd`. When set, the tag becomes `<IMAGE_SUFFIX>-<date>-weekly` to select a weekly-build image |
| `AIG_SERVER_IMAGE`, `WEB_UI_IMAGE`, `DLSTREAMER_PIPELINE_SERVER_IMAGE` | `intel/aig-server`, `intel/digital-signage-webui`, `intel/dlstreamer-pipeline-server:2026.2.0-ubuntu24` | Image names; the first two get the tag above |
| `MODEL_DOWNLOAD_IMAGE` | `intel/model-download:2026.2.0` | Image `make download_models` runs |
| `MODEL_DOWNLOAD_PORT` | `8000` | Host port (bound to `127.0.0.1` only) for the model-download container; change it if 8000 is taken |

`make build` builds with the tag above and `make up` runs `docker compose up -d`, so skipping
the build makes compose try to **pull** `intel/aig-server:<IMAGE_SUFFIX>` instead.

### Model download knobs

`make download_models` runs `scripts/download_models.sh`. None of these are in `.env`; export
them in the shell or add them to `.env` (the Makefile exports every key in `.env`):

| Variable | Default | Notes |
|---|---|---|
| `HF_TOKEN` / `HUGGINGFACEHUB_API_TOKEN` | *(unset)* | Optional Hugging Face token passed into the container; either one works. Never commit it |
| `MODEL_DOWNLOAD_PLUGINS` | `huggingface,openvino,ultralytics` | Plugins the microservice loads |
| `MODEL_DOWNLOAD_TIMEOUT_SECONDS` | `7200` | Total wait for the download jobs |
| `MODEL_DOWNLOAD_POLL_INTERVAL_SECONDS` | `10` | Job status polling period |
| `MODEL_DOWNLOAD_CA_BUNDLE` | auto: `/etc/ssl/certs/ca-certificates.crt`, else `/etc/pki/tls/certs/ca-bundle.crt` | Host CA bundle mounted into the container; set it for a corporate TLS-intercepting proxy |
| `SKIP_LTX_VIDEO_EXPORT` | unset; defaults to `$CI` | `1`/`true` skips the optional LTX-Video export. `0` forces it even under `CI` |
| `http_proxy`, `https_proxy`, `no_proxy` | *(shell)* | Forwarded into the container (upper-case forms too) |

The script exits early only when **all** of YOLO11s, SDXL-Turbo, MiniLM **and** the LTX-Video
scheduler file exist. With the LTX export skipped and no LTX model on disk, every run repeats the
three downloads.

## Pipeline server (PID)

| Variable | Default | Notes |
|---|---|---|
| `HOST_IP` | `127.0.0.1` | See gating above |
| `REST_SERVER_PORT` | `8080` | DL Streamer Pipeline Server's internal REST port, proxied by nginx at `/dsps-api/`. Not published to the host |
| `RTSP_CAMERA_IP` | *(empty)* | Only consumed if you edit `configs/pid/config.json` to use `rtspsrc`; setting it alone changes nothing |

The detection model path and inference device are **not** environment variables — they live in
`configs/pid/config.json` (`device` is `CPU` in the shipped file; `GPU` and `NPU` are valid).
See `customize.md`.

## WebRTC and TURN

| Variable | Default | Notes |
|---|---|---|
| `WHIP_SERVER_PORT` | `8889` | MediaMTX WHIP/WHEP port; nginx proxies `/samplestream/whip` and `/whep` to it |
| `MTX_WEBRTCICESERVERS2_0_USERNAME` | *(empty)* | Gating — see above |
| `MTX_WEBRTCICESERVERS2_0_PASSWORD` | *(empty)* | Gating — see above |
| `COTURN_UDP_PORT` | `3478` | Published to the host as both TCP and UDP, bound to `${HOST_IP:-127.0.0.1}`. The only published ports are this and nginx's 5000 (plus the transient model-download port, 127.0.0.1 only) |

MediaMTX also has hardcoded stream credentials in `docker-compose.yml` (`publisher`/`pubpass`
for publishing, `viewer`/`viewpass` for reading path `cam1`). These are not in `.env` and
changing them means editing compose.

## Telemetry

The collector is not part of this compose file, so exporting needs one stood up separately.
Compose hardcodes `ENABLE_OPEN_TELEMETRY: true` on the pipeline server, so the `.env` flag below
is **not** read, and `PROMETHEUS_PORT` isn't referenced by compose at all; only the three
`OTEL_*` values are passed through.

| Variable | Default |
|---|---|
| `ENABLE_OPEN_TELEMETRY` | `false` *(not consumed)* |
| `OTEL_COLLECTOR_HOST` | `otel-collector` |
| `OTEL_COLLECTOR_PORT` | `4318` |
| `OTEL_EXPORT_INTERVAL_MILLIS` | `5000` |
| `PROMETHEUS_PORT` | `9999` *(not consumed)* |

## AIG — image generation

Consumed by `aig/src/database/version.py` via `os.getenv`. Paths are **container paths**;
`aig/models/` is mounted at `/opt/models` and `aig/sharedata/` at `/opt/sharedata`.

| Variable | Default | Notes |
|---|---|---|
| `USER` | `digitalsignageuser` | Build arg for the non-root container user |
| `UID` | `1000` | Build arg. Ships with a trailing space, which is harmless here but will break a strict consumer |
| `AIG_PORT` | `5003` | Internal only; nginx proxies it at `/aig-api/` |
| `AIG_LOGO_PATH` | `/opt/sharedata/sample_logo.png` | Must be RGBA with transparency for the overlay to look right |
| `AIG_FONT_PATH` | `/usr/share/fonts/ttf/IntelOneMono-Bold.ttf` | Installed by the Dockerfile; changing it means adding the font to the image |
| `AIG_MODEL_PATH` | `/opt/models/sdxl_turbo_ov/int8` | Must match where `make download_models` put the export |
| `AIG_INFERENCE_DEVICE` | `GPU` | `CPU`, `GPU` or `NPU` (experimental). The `.env` name; compose passes it to aig-server as `AIG_MODEL_DEVICE` and to web-ui as `AIG_INFERENCE_DEVICE`. Case-insensitive; an unknown value becomes `CPU` in aig-server. Checked against `ov.Core().available_devices` when the model loads |
| `AIG_NPU_CACHE_HOST_DIR` | `./aig/npu_cache` | Host directory bind-mounted at `/opt/npu_cache` (container var `AIG_NPU_CACHE_DIR`) to hold compiled NPU blobs. Must be writable by `UID`; `make up` creates it; **survives `make down`** |
| `AIG_MODEL_NUM_INFERENCE_STEPS` | `4` | SDXL-Turbo is designed for 1–4 steps. Raising it costs latency for little gain |
| `AIG_IMG_WIDTH_DEFAULT` | `448` | Size of every generated image — `/aig/minf/` has no per-request size. On the NPU the pipeline is compiled for exactly this size |
| `AIG_IMG_HEIGHT_DEFAULT` | `448` | |
| `AIG_KEEP_MODEL_IN_MEMORY` | `true` | `true` holds ~10 GB resident and keeps subsequent generations fast; `false` drops to ~2 GB but reloads the model every request (on the NPU, a reload per request is very costly — keep `true`) |

NPU: the first start compiles for about 3 minutes and writes roughly 7 GB of cache **per image
size** (changing `AIG_IMG_*_DEFAULT` triggers a fresh compile and more cache). The web UI warms
up AIG with a throw-away ad before it starts consuming detections, so the first compile delays
the first real ad. `GPU` requires a populated `/dev/dri` on the host; `NPU` requires
`/dev/accel`. The Makefile probes both at parse time and substitutes `/dev/null` when missing,
so the container starts fine and fails at inference instead.

`/aig/minf/` accepts a `device` field and reuses the preloaded pipeline only when it equals the
configured device. The web UI sends `AIG_INFERENCE_DEVICE` from the same `.env` value (falling
back to `GPU` only if it isn't `CPU`/`GPU`/`NPU`), so the two normally can't drift; a manual
request for a different device builds a temporary pipeline, which is slow. If the preloaded
model failed to load (for example an NPU compile error), requests for the configured device
return `503` and the load is not retried for 5 minutes; restart `aig-server` to retry sooner.

## AIG — video generation

Optional. Used only by the MCP `trigger_video_ad` tool when an item has no predefined video, via
`POST /aig/mvid/`. Needs the LTX-Video model from `make download_models`
(`aig/models/ltx_video_ov/int8`). If `AIG_VIDEO_MODEL_PATH` is unset or the model is missing,
video requests fail with 500 and everything else keeps working.

| Variable | Default | Notes |
|---|---|---|
| `AIG_VIDEO_MODEL_PATH` | `/opt/models/ltx_video_ov/int8` | Unset disables dynamic video generation |
| `AIG_VIDEO_INFERENCE_DEVICE` | `GPU` | `CPU` or `GPU`. `NPU` is not supported for video and is changed to `GPU` (with a warning). Compose gives aig-server this as `AIG_VIDEO_MODEL_DEVICE` and web-ui as `AIG_VIDEO_INFERENCE_DEVICE`, so the two stay in sync |
| `AIG_VIDEO_WIDTH_DEFAULT` / `AIG_VIDEO_HEIGHT_DEFAULT` | `704` / `480` | Independent of the image size; must be divisible by 32 |
| `AIG_VIDEO_NUM_FRAMES` | `25` | Must be 8k+1 (17, 25, 33, 41…). The main lever on generation time |
| `AIG_VIDEO_NUM_INFERENCE_STEPS` | `50` | More steps = better quality, slower |
| `AIG_VIDEO_GUIDANCE_SCALE` | `5.0` | LTX-Video needs real guidance; much higher oversaturates |
| `AIG_VIDEO_FRAME_RATE` | `8` | Frame rate for the model's temporal generation |
| `AIG_VIDEO_LOOP_SECONDS` | `3` | Playback length of one pass of the encoded animated WEBP. Keep equal to `VIDEO_AD_DISPLAY_SECONDS` |
| `AIG_VIDEO_NEGATIVE_PROMPT` | `"worst quality, inconsistent motion, blurry, jittery, distorted"` | Quoted in `.env` |
| `AIG_VIDEO_PRECISION` | `f16` | `f16` or `f32`; `f16` is roughly 5–6× faster on an Intel iGPU. `f32` needs more memory |
| `AIG_PRELOAD_VIDEO_MODEL` | `false` | `true` loads the model at aig-server start (needs `AIG_KEEP_MODEL_IN_MEMORY=true` to be useful; ~8 GB while idle) instead of on the first video request |

With `f16` on an iGPU expect on the order of 30 s per video after the model is loaded; `f32` is
about 3 minutes. The video model is held in memory only while `AIG_KEEP_MODEL_IN_MEMORY=true`.

## ASe — semantic ad search

Backed by the `ase-qdrant` container (Qdrant, cosine distance). Vectors live in the named
volumes `qdrant_data`/`qdrant_snapshots`, which **`make down` deletes**; ad image files stay on
the host in `aig/sharedata/imgs/`.

| Variable | Default | Notes |
|---|---|---|
| `ASE_MODEL_PATH` | `/opt/models/all-MiniLM-L12-v2` | Sentence-transformers embedding model. There is **no fallback**: if it fails to load, ASe stays disabled and every `/ase/*` call fails. A model whose vector size differs from an existing collection also disables ASe until the collection is recreated (`make down`) or `ASE_COLLECTION_NAME` changes |
| `ASE_COLLECTION_NAME` | `ase-collection` | |
| `ASE_QDRANT_HOST` | `ase-qdrant` | Qdrant service name on the compose network (compose also defaults it) |
| `ASE_QDRANT_PORT` | `6333` | Internal; not published |
| `ASE_IMG_PATH` | `/opt/sharedata/imgs` | Where stored ad images are written as `img_<id>.jpg` |
| `ASE_IMG_DEFAULT_AD` | `/opt/sharedata/default_ad.jpg` | **This file does not exist in the repo.** Only used when a query returns nothing *and* the request sets `use_default_ad_onempty` |
| `ASE_ENABLE_SAMPLEDATA` | `1` | Non-zero enables sample-data loading |
| `ASE_ENABLE_SAMPLEDATA_DIR` | `/opt/sharedata/sample` | **This directory does not exist in the repo**, so sample loading is a no-op despite being enabled |
| `ASE_QDRANT_SCORE_MIN_THRESHOLD` | `0.8` | Minimum cosine **similarity** for a match; results scoring below it are discarded. **Higher is stricter** — the opposite of the old distance threshold it replaced |

`ASE_QDRANT_SCORE_MIN_THRESHOLD` is the main tuning knob for "predefined ads never show". At
`0.8` the query must be quite close to the stored description; lowering it lets looser matches
through, at the cost of occasionally showing an ad for the wrong product. Ad ids must be
integers (they are Qdrant point ids).

## Web UI — ad behavior

Consumed by `web-ui/main.py`.

| Variable | Default | Notes |
|---|---|---|
| `TIME_TO_DISPLAY_AD_SECONDS` | `5` | Minimum seconds an ad stays before the generator picks a new one. This is a floor, not a period — generation can take longer |
| `OBJECT_RECENCY_FRAME_COUNT` | `5` | A label must appear in at least this many messages within a rolling window of `2 ×` this value before it counts as detected |
| `OBJECT_CONFIDENCE_THRESHOLD` | `0.5` | Mean confidence across those messages must reach this |
| `VIDEO_AD_DISPLAY_SECONDS` | `3` | How long an MCP `trigger_video_ad` clip stays on screen, looping. Must match `AIG_VIDEO_LOOP_SECONDS`; a predefined video longer than this (+0.5 s) is rejected at load time. Some docs still say 5; the shipped `.env` value is 3 |

Raise `OBJECT_RECENCY_FRAME_COUNT` or `OBJECT_CONFIDENCE_THRESHOLD` to stop spurious detections
triggering ads; lower them if products are detected but no ad ever fires.

The web UI also runs the MCP server on internal port 5100 (nginx exposes it at `/mcp`); it has no
variables of its own. `select_dynamic_ad` reads `web-ui/context_rules.json`.

## Compose-only and benchmark variables

Not in `.env`, but read by `docker-compose.yml` or the Makefile:

| Variable | Default | Notes |
|---|---|---|
| `DRI_MOUNT_PATH`, `ACCEL_MOUNT_PATH` | `/dev/dri`, `/dev/accel` if present, else `/dev/null` | Set by the Makefile at parse time. Export them yourself if you run `docker compose` directly |
| `BENCHMARK_MODE` | `false` | `true` turns on stage timing and trace logging in aig-server and web-ui (and the web UI's `/ad_rendered` endpoint). `make benchmark-*` sets it; leave it off for normal runs |
| `MODEL_DOWNLOAD_HOST_GID`, `MODEL_DOWNLOAD_CA_BUNDLE` | host gid / auto | Set by `scripts/download_models.sh` |

`make benchmark-*` also tune `PID_DEVICE` (default `CPU`), `AIG_DEVICE` (`GPU`),
`BENCHMARK_DURATION`, `BENCHMARK_ITERATIONS` and `BENCHMARK_WARMUP_SECONDS` (`300`); see
`docs/user-guide/how-to-guides/benchmarking.md`. Note they **rewrite** the detection `device` in
`configs/pid/config.json` and `AIG_INFERENCE_DEVICE` in `.env` unless
`SKIP_BENCHMARK_DEVICE_CONFIG=true`.

---

## Code defaults that disagree with `.env`

Several `os.getenv` calls specify a fallback different from the shipped `.env` value. The
fallback is only reached when the container is run **outside compose**: inside compose a key
missing from `.env` is passed through as an *empty string*, not as "unset" — so numeric settings
(`AIG_IMG_*`, `AIG_VIDEO_*`, `TIME_TO_DISPLAY_AD_SECONDS`, `OBJECT_*`, `VIDEO_AD_DISPLAY_SECONDS`,
`ASE_QDRANT_PORT`) fail with `invalid literal for int()` rather than falling back. Either way,
keep every entry present.

| Variable | `.env` | Code fallback | Effect of the fallback |
|---|---|---|---|
| `AIG_KEEP_MODEL_IN_MEMORY` | `true` | `false` | Model reloads every request; generation gets much slower (an empty string behaves the same inside compose) |
| `AIG_MODEL_NUM_INFERENCE_STEPS` | `4` | `5` | One extra step per image |
| `AIG_IMG_WIDTH_DEFAULT` / `_HEIGHT_DEFAULT` | `448` | `512` | Larger images, slower; a different NPU compile size |
| `AIG_VIDEO_NUM_FRAMES` | `25` | `41` | Roughly 60% more frames, much slower generation |
| `AIG_VIDEO_LOOP_SECONDS` | `3` | `5` | Clip plays slower than it was generated |
| `VIDEO_AD_DISPLAY_SECONDS` (web-ui) | `3` | `5` | Mismatch with the loop length above |
| `ASE_ENABLE_SAMPLEDATA` | `1` | `0` | Sample loading off (already a no-op, see above) |
| `MQTT_BROKER` (web-ui) | *(set by compose to `mqtt-broker`)* | `ia-mqtt-broker` | MQTT connect fails and `main.py` calls `os._exit(1)` |

These now **agree** (no action needed): `ASE_QDRANT_SCORE_MIN_THRESHOLD` (`0.8`), the video
size/steps/guidance/frame-rate/precision settings, and `TIME_TO_DISPLAY_AD_SECONDS` / `OBJECT_*`.
The old `ASE_DISTANCE_MAX_THRESHOLD` disagreement is gone with ChromaDB.

Treat the `.env` values as authoritative.

## Referenced but absent from `.env`

Not defined in `.env` — they resolve empty or to code defaults unless exported in the shell:

- `http_proxy`, `https_proxy`, `no_proxy` — interpolated by compose as build args and container
  env; export before `make build` / `make up` / `make download_models` behind a proxy
- `AIG_SERVER_URL` — web-ui falls back to `http://aig-server:5003`, which is correct on the
  compose network, so this is fine in practice
- `MQTT_TOPIC` — web-ui falls back to `yolo_od_results`, which matches what the pipeline
  publishes. Changing the topic means changing it in **both** `configs/pid/config.json` and the
  web-ui environment (compose doesn't pass `MQTT_TOPIC`, so add it to the `web-ui` service)
- `MR_*`, `MR_MINIO_*`, `OPCUA_*`, S3 variables — model-registry and OPC-UA features of the
  DL Streamer image that this deployment does not use
