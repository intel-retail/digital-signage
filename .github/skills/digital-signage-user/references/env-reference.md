# Environment Variable Reference

Every variable in `.env`, what reads it, and what happens if it's wrong.

`.env` is `include`d by the `Makefile`, which then `export`s every key, and is also read by
`docker-compose.yml` for `${VAR}` substitution. Values are read **at container start**, so any
change requires `make up` (which tears down and recreates), not `docker restart`.

## Contents

- [Gating variables](#gating-variables) — these three block `make up`
- [Docker Compose](#docker-compose)
- [Pipeline server](#pipeline-server-pid)
- [WebRTC and TURN](#webrtc-and-turn)
- [Telemetry](#telemetry)
- [AIG — image generation](#aig--image-generation)
- [ASe — semantic ad search](#ase--semantic-ad-search)
- [Web UI — ad behavior](#web-ui--ad-behavior)
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
| `HOST_IP` | `localhost`, or dotted-quad IPv4 with each octet 0–255 | `localhost` |

The two credentials ship empty, so **every fresh clone fails `make up` until they are set**.
They are TURN credentials for the coturn server; they are not checked against anything external,
so any conforming value works. `usernam` / `passw0rd1` are valid; `user` (too short) and
`password` (no digit) are not.

Note the validation greps `.env` directly with `cut -d'=' -f2` — a value containing `=` is
truncated, and quotes are kept literally, so don't quote these.

`HOST_IP` is substituted into `MTX_WEBRTCICESERVERS2_0_URL=turn:${HOST_IP}:${COTURN_UDP_PORT}`,
which the browser receives as its ICE server. With `localhost`, a browser on another machine
tries to reach a TURN server on itself and WebRTC fails — set the host's real LAN IP for any
remote access.

There is a fourth gate that isn't a variable: `make check_models` fails unless both
`configs/pid/models/` and `aig/models/` exist and are non-empty. It only checks emptiness, so a
partially downloaded model passes this check and fails later at inference.

---

## Docker Compose

| Variable | Default | Notes |
|---|---|---|
| `COMPOSE_HTTP_TIMEOUT` | `200` | Raise if builds time out on a slow link |
| `COMPOSE_PROJECT_NAME` | `digitalsignage` | Prefixes networks and volumes |
| `DOCKER_REGISTRY` | *(empty)* | Needed only for `make push_images`; include the trailing `/`, e.g. `localhost:5000/` |

## Pipeline server (PID)

| Variable | Default | Notes |
|---|---|---|
| `HOST_IP` | `localhost` | See gating above |
| `REST_SERVER_PORT` | `8080` | DL Streamer Pipeline Server's internal REST port, proxied by nginx at `/dsps-api/`. Not published to the host |
| `RTSP_CAMERA_IP` | *(empty)* | Only consumed if you edit `configs/pid/config.json` to use `rtspsrc`; setting it alone changes nothing |

The detection model path and inference device are **not** environment variables — they live in
`configs/pid/config.json`. See `customize.md`.

## WebRTC and TURN

| Variable | Default | Notes |
|---|---|---|
| `WHIP_SERVER_PORT` | `8889` | MediaMTX WHIP/WHEP port; nginx proxies `/samplestream/whip` and `/whep` to it |
| `MTX_WEBRTCICESERVERS2_0_USERNAME` | *(empty)* | Gating — see above |
| `MTX_WEBRTCICESERVERS2_0_PASSWORD` | *(empty)* | Gating — see above |
| `COTURN_UDP_PORT` | `3478` | Published to the host as both TCP and UDP. The **only** published port besides 5000 |

MediaMTX also has hardcoded stream credentials in `docker-compose.yml` (`publisher`/`pubpass`
for publishing, `viewer`/`viewpass` for reading path `cam1`). These are not in `.env` and
changing them means editing compose.

## Telemetry

Off by default; the collector is not part of this compose file, so enabling it requires
standing one up separately.

| Variable | Default |
|---|---|
| `ENABLE_OPEN_TELEMETRY` | `false` |
| `OTEL_COLLECTOR_HOST` | `otel-collector` |
| `OTEL_COLLECTOR_PORT` | `4318` |
| `OTEL_EXPORT_INTERVAL_MILLIS` | `5000` |
| `PROMETHEUS_PORT` | `9999` |

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
| `AIG_MODEL_DEVICE` | `GPU` | `CPU`, `GPU` or `NPU`. Validated against `ov.Core().available_devices` at request time |
| `AIG_MODEL_NUM_INFERENCE_STEPS` | `4` | SDXL-Turbo is designed for 1–4 steps. Raising it costs latency for little gain |
| `AIG_IMG_WIDTH_DEFAULT` | `448` | Used when the request omits dimensions |
| `AIG_IMG_HEIGHT_DEFAULT` | `448` | |
| `AIG_KEEP_MODEL_IN_MEMORY` | `true` | `true` holds ~10 GB resident and keeps subsequent generations fast; `false` drops to ~2 GB but reloads the model every request |

`AIG_MODEL_DEVICE` interacts with the request body: `/aig/minf/` accepts a `device` field, and
only when it equals `AIG_MODEL_DEVICE` does the request reuse the preloaded pipeline. A
mismatch builds a fresh pipeline per request, which is slow. The web UI hardcodes `"GPU"` in
its dynamic-ad request, so setting `AIG_MODEL_DEVICE=CPU` while leaving the UI alone gives you
a per-request reload on every ad.

`GPU` requires a populated `/dev/dri` on the host; `NPU` requires `/dev/accel`. The Makefile
probes both at parse time and substitutes `/dev/null` when missing, so the container starts
fine and fails at inference instead.

## ASe — semantic ad search

| Variable | Default | Notes |
|---|---|---|
| `ASE_MODEL_PATH` | `/opt/models/all-MiniLM-L12-v2` | Sentence-transformers embedding model. On load failure the code silently falls back to ChromaDB's default embedding function, which changes similarity scores |
| `ASE_COLLECTION_NAME` | `ase-collection` | |
| `ASE_CHROMADB_PORT` | `8000` | Internal |
| `ASE_IMG_PATH` | `/opt/sharedata/imgs` | Where stored ad images are written as `img_<id>.jpg` |
| `ASE_IMG_DEFAULT_AD` | `/opt/sharedata/default_ad.jpg` | **This file does not exist in the repo.** Only used when a query returns nothing *and* the request sets `use_default_ad_onempty` |
| `ASE_ENABLE_SAMPLEDATA` | `1` | Non-zero enables sample-data loading |
| `ASE_ENABLE_SAMPLEDATA_DIR` | `/opt/sharedata/sample` | **This directory does not exist in the repo**, so sample loading is a no-op despite being enabled |
| `ASE_DISTANCE_MAX_THRESHOLD` | `0.2` | Results with a distance above this are discarded. Lower is stricter |

`ASE_DISTANCE_MAX_THRESHOLD` is the main tuning knob for "predefined ads never show". At `0.2`
the match must be very close; raising it toward `0.5` lets looser matches through, at the cost
of occasionally showing an ad for the wrong product.

## Web UI — ad behavior

Consumed by `web-ui/main.py`.

| Variable | Default | Notes |
|---|---|---|
| `TIME_TO_DISPLAY_AD_SECONDS` | `5` | Minimum seconds an ad stays before the generator picks a new one. This is a floor, not a period — generation can take longer |
| `OBJECT_RECENCY_FRAME_COUNT` | `5` | A label must appear in at least this many messages within a rolling window of `2 ×` this value before it counts as detected |
| `OBJECT_CONFIDENCE_THRESHOLD` | `0.5` | Mean confidence across those messages must reach this |

Raise `OBJECT_RECENCY_FRAME_COUNT` or `OBJECT_CONFIDENCE_THRESHOLD` to stop spurious detections
triggering ads; lower them if products are detected but no ad ever fires.

---

## Code defaults that disagree with `.env`

Several `os.getenv` calls specify a fallback different from the shipped `.env` value. This only
matters when a variable is removed from `.env` or a container is run outside compose — but when
it does matter, the behavior change is silent and confusing.

| Variable | `.env` | Code fallback | Effect if `.env` entry is missing |
|---|---|---|---|
| `AIG_KEEP_MODEL_IN_MEMORY` | `true` | `false` | Model reloads every request; generation gets much slower |
| `ASE_DISTANCE_MAX_THRESHOLD` | `0.2` | `1.5` | Nearly every query matches something, so unrelated predefined ads start appearing |
| `MQTT_BROKER` (web-ui) | *(set by compose to `mqtt-broker`)* | `ia-mqtt-broker` | MQTT connect fails and `main.py` calls `os._exit(1)` |

Treat the `.env` values as authoritative and keep entries present even when set to their
default.

## Referenced but absent from `.env`

`docker-compose.yml` interpolates these but `.env` does not define them, so they resolve empty
unless exported in the shell:

- `http_proxy`, `https_proxy`, `no_proxy` — build args; export before `make build` behind a proxy
- `AIG_SERVER_URL` — web-ui falls back to `http://aig-server:5003`, which is correct on the
  compose network, so this is fine in practice
- `MQTT_TOPIC` — web-ui falls back to `yolo_od_results`, which matches what the pipeline
  publishes. Changing the topic means changing it in **both** `configs/pid/config.json` and the
  web-ui environment
- `MR_*`, `MR_MINIO_*`, `OPCUA_*`, S3 variables — model-registry and OPC-UA features of the
  DL Streamer image that this deployment does not use
