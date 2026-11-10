# Architecture

Service boundaries, the seams between them, and what a change to one forces on another.

## Contents

- [End-to-end flow](#end-to-end-flow)
- [Services](#services)
- [Startup order and its consequences](#startup-order-and-its-consequences)
- [The seams](#the-seams)
- [Volumes and what survives a restart](#volumes-and-what-survives-a-restart)
- [Repository layout](#repository-layout)

## End-to-end flow

1. **dlstreamer-pipeline-server** runs a GStreamer pipeline defined in `configs/pid/config.json`.
   It decodes a looping `.avi` (or RTSP stream), runs `gvadetect` with YOLO11s, and splits the
   result: metadata to MQTT, frames to WebRTC.
2. **mqtt-broker** carries detection metadata on topic `yolo_od_results`.
3. **web-ui** subscribes. `MQTTSubscriber` filters by recency and confidence, then enqueues
   accepted labels. `Ad_Generator` (a separate thread) dequeues, picks one product, builds an
   overlay payload, and asks the AIG server for an image.
4. **aig-server** answers one of two ways: a semantic lookup against **ase-qdrant** for a
   predefined ad, or SDXL-Turbo generation (GPU, CPU or NPU). The web UI tries predefined first.
5. **mediamtx** + **coturn** deliver the video over WebRTC.
6. **nginx** terminates TLS and is the single door into the stack — it proxies the web UI, the
   AIG API, Swagger, the MCP server and the WebRTC signalling paths.

A second, agent-driven path bypasses steps 1–3: an MCP client calls tools on `web-ui/mcp_server.py`
(via nginx `/mcp`), and the resulting image or video ad **overrides** the camera-driven one for a
fixed time. Video ads (LTX-Video via `POST /aig/mvid/`) exist only on this path.

Detection and ad generation are decoupled by the MQTT queue, so a slow generation backs up ads
without stalling the video. That decoupling is why ad latency and video smoothness are
independent symptoms.

## Services

Eight services start by default, all `read_only: true` with `no-new-privileges`, on the
`app_network` bridge. A ninth, `model-download`, sits behind the `model-download` compose profile
and is only started by `scripts/download_models.sh` (see below).

| Service / container | Image | Internal port | Depends on |
|---|---|---|---|
| `mqtt-broker` | `eclipse-mosquitto:2.0.22` | 1883 | — |
| `ase-qdrant` | `qdrant/qdrant:v1.20.0-unprivileged` | 6333 (REST) | — |
| `mediamtx` | `bluenviron/mediamtx:1.21.2` | 8889 (WHIP/WHEP) | — |
| `coturn` | `coturn/coturn:4.18.0-alpine` | 3478 | — |
| `dlstreamer-pipeline-server` | `intel/dlstreamer-pipeline-server:2026.2.0-ubuntu24` | 8080 | `mediamtx` |
| `aig-server` | built from `aig/Dockerfile` | 5003 | `ase-qdrant` |
| `web-ui` | built from `web-ui/Dockerfile` | 5000 (Flask), 5100 (MCP) | `mediamtx`, `aig-server` |
| `nginx` (container `nginx_proxy`) | `nginx:1.31.7` | 15443 → **host 5000** | `web-ui`, `mqtt-broker`, `mediamtx`, `coturn` |
| `model-download` (profile only) | `intel/model-download:2026.2.0` | 8000 → host `127.0.0.1:${MODEL_DOWNLOAD_PORT}` | — |

Only two host ports exist during normal runs: **5000** (nginx, HTTPS) and **`COTURN_UDP_PORT`**
(3478, TCP+UDP). Both are published on `${HOST_IP:-127.0.0.1}` — loopback unless `HOST_IP` is set
to a reachable IPv4. `make up` runs `validate_host_ip`, which rejects anything that is not
dotted-quad IPv4, so `localhost` is no longer valid; remote browsers also need `HOST_IP` for the
TURN URL mediamtx hands out. Anything you add is unreachable from the host unless nginx proxies it
— adding an endpoint means checking whether `configs/nginx/nginx.conf` already routes to it
(web-ui's MCP port 5100 is reached only through nginx `/mcp`).

Models are not baked into images: `make download_models` runs `scripts/download_models.sh`, which
starts the `model-download` service to fetch YOLO11s, SDXL-Turbo and MiniLM into
`configs/pid/models/` and `aig/models/`, then exports LTX-Video with `optimum-cli` (skipped when
`CI` is set). `make up` only gates on the first three (`check_models`).

MQTT is anonymous and unencrypted (`allow_anonymous true`, no TLS). MediaMTX has hardcoded
credentials in `docker-compose.yml` (`publisher`/`pubpass`, `viewer`/`viewpass` on path `cam1`),
not in `.env`.

## Startup order and its consequences

`depends_on` in this compose file waits for *container start*, not readiness, and two behaviors
depend on that:

- **web-ui seeds Qdrant at startup.** `main.py` first polls aig-server's root URL until it answers
  200, then `initialize_app()` reads `ProductAssociations.csv` and POSTs each row with a
  `pre_defined_ad_image` to `/ase/predef/` with a **15-second timeout**. The first POST also
  triggers aig-server's lazy Qdrant + embedding-model init, so a slow or failed init makes that row
  fail with a log line and no retry — predefined ads sometimes just aren't there after a start.
- **web-ui exits on MQTT failure.** `main.py` calls `os._exit(1)` if the MQTT connect fails
  rather than retrying, so any broker hiccup presents as a container restart loop.

If you add a cross-service call at startup, give it a retry rather than following the existing
pattern — the existing pattern is the source of both of the above.

nginx resolves its upstreams at config-load time, so a dead `web-ui` prevents nginx from
starting at all.

## The seams

Three contracts hold the system together. Changing one side without the other produces silent
misbehavior, not an error.

### web-ui → aig-server (HTTP)

`web-ui/main.py` builds four URLs at module level:

```python
AIG_SERVER_URL = os.getenv('AIG_SERVER_URL', 'http://aig-server:5003')
AIG_DYNAMIC_AD_ENDPOINT          = f"{AIG_SERVER_URL}/aig/minf/"
AIG_DYNAMIC_VIDEO_AD_ENDPOINT    = f"{AIG_SERVER_URL}/aig/mvid/"
AIG_PREDEFINED_AD_STORE_ENDPOINT = f"{AIG_SERVER_URL}/ase/predef/"
AIG_PREDEFINED_AD_QUERY_ENDPOINT = f"{AIG_SERVER_URL}/ase/predef/query/ad"
```

`AIG_SERVER_URL` is not set in `.env` or compose; the default is correct on the compose network.
The web UI is the **only** consumer of these endpoints, so a schema change has exactly one caller
to update — but nothing enforces it. Flask-RESTX validates the request against `@api.expect`, so
an unknown field is rejected while a *missing optional* field is silently defaulted.

Timeouts differ sharply by path: **15 seconds** for the predefined query and for seeding, **400
seconds** for dynamic image generation, **900 seconds** for video. A *timeout* on the predefined
query is not a miss: the exception aborts that whole `generate_advertisement` call (logged as
"Error processing message"), so there is no dynamic fallback and the displayed ad just stops
changing. Only a non-200 or an empty result list falls through to generation.

The device string web-ui sends comes from its own env (`AIG_INFERENCE_DEVICE`,
`AIG_VIDEO_INFERENCE_DEVICE`), which compose sets from the same `.env` keys that feed aig-server's
`AIG_MODEL_DEVICE` / `AIG_VIDEO_MODEL_DEVICE`. Keep them in step or every request builds a
throwaway pipeline instead of reusing the loaded one.

### pipeline → web-ui (MQTT)

The pipeline publishes to `yolo_od_results` (set in `config.json`); the web UI subscribes to
`os.getenv('MQTT_TOPIC', 'yolo_od_results')`. Changing the topic requires editing **both**, and
`MQTT_TOPIC` isn't in `.env`, so the fallback is doing the work today.

Message shape the web UI parses:

```
metadata.gva_meta[i].tensor[j].label
metadata.gva_meta[i].tensor[j].confidence
```

A different detection element or model-proc that changes this structure breaks label extraction
without an exception — the parse just finds nothing.

### aig-server → browser (via web-ui)

The browser polls `/get_current_advertisement` every 2 seconds and relies on **204 No Content**
meaning "you already have the current ad". Returning 200 with unchanged bytes instead would
work but wastes bandwidth on every client every 2 seconds; returning 204 when the ad *has*
changed makes the panel appear stuck. The `client_id` that drives this is a browser fingerprint,
not a session — see `web-ui-service.md`. The response can also be an animated video ad, and an
agent-commanded *image* override is the exception to the 204 rule (re-sent on every poll until it
expires) — priority order is in `web-ui-service.md`.

### agent → web-ui (MCP over nginx)

`/mcp` on nginx proxies to `web-ui:5100`, where `web-ui/mcp_server.py` runs FastMCP
(Streamable HTTP) in a daemon thread of the web-ui process. The tools call functions in
`main.py` directly (via `sys.modules['__main__']`), so they share the live in-memory ad state —
and `main.py` must run as the entry script. No authentication is configured; reachability is
whatever `HOST_IP` and your network allow. Tool list and behaviour: `web-ui-service.md`.

## Volumes and what survives a restart

| Volume | Mounted at | Survives `make down`? |
|---|---|---|
| `qdrant_data`, `qdrant_snapshots` | ase-qdrant `/qdrant/storage`, `/qdrant/snapshots` | **No** — `make down` passes `-v` |
| `vol_pipeline_root`, `vol_nginx_tmpfs` | tmpfs | No |
| `./aig/models` | aig-server `/opt/models` (host bind) | Yes |
| `./aig/sharedata` | aig-server `/opt/sharedata` (host bind; ad images land in `imgs/`) | Yes |
| `./aig/src` | aig-server `/home/aigserver/src` (host bind) | Yes |
| `${AIG_NPU_CACHE_HOST_DIR:-./aig/npu_cache}` | aig-server `/opt/npu_cache` (host bind) | Yes |
| `./configs/pid/models`, `./configs/pid/videos`, `config.json` | pipeline server (host binds) | Yes |
| `./web-ui/ProductAssociations.csv`, `./web-ui/pre-defined-ads`, `./web-ui/context_rules.json` | web-ui, read-only | Yes |

Two consequences worth internalizing:

- **Qdrant is ephemeral, the ad images are not.** Every `make up` re-seeds vectors from the CSV,
  so there is no migration concern and no way to accumulate ads across runs except through the
  CSV. But the JPEGs behind each point live in `./aig/sharedata/imgs/`, which survives
  `make down`, and web-ui seeds without an `id` (aig-server picks a random one) — so each reseed
  leaves orphan image files, and restarting only `web-ui` (Qdrant still up) adds duplicate points.
- **`aig/src` is bind-mounted**, so Python edits under `aig/src/` take effect on a
  `docker restart aig-server` without a rebuild (Flask debug/reloader is off; the restart is what
  reloads). `web-ui/main.py` and `mcp_server.py` are baked into the image and need `make build`.
  This asymmetry is the single biggest factor in how fast you can iterate.

## Repository layout

```
aig/
  src/
    __main__.py            entry point; argparse on AIG_PORT, starts Flask (debug=False, threaded)
    server/aig_server.py   Flask app wrapper; background video preload, Server-Timing in benchmark mode
    server/apis/           REST layer
      __init__.py          Api() + add_namespace registration
      status.py            GET /aig/hstatus/<id>
      version.py           GET /aig/versions
      modelinf.py          POST /aig/minf/  — SDXL-Turbo generation; apply_ad_overlays()
      videoinf.py          POST /aig/mvid/  — LTX-Video generation, animated WEBP
      predefinedads.py     the six /ase/predef* operations
    database/
      version.py           AigServerMetadata + AseServerMetadata singletons, all env accessors,
                           Qdrant client and helpers  (~1,000 lines — the centre of gravity)
      utils.py             sample-data loading
      testASE.py           live REST-call test example
      testqdrant.py        live Qdrant-call test example
    imgproc/
      img_frame.py         ImgDecorator — all overlay drawing
  models/                  never committed
  npu_cache/               compiled NPU blobs (host bind), contents never committed
  sharedata/               mounted at /opt/sharedata
  Dockerfile, run.sh, src/requirements.txt

web-ui/
  main.py                  Flask app, MQTTSubscriber, Ad_Generator, MCP core functions  (~1,550 lines)
  mcp_server.py            FastMCP tools on port 5100, thin wrappers over main.py
  context_rules.json       context → product rules for select_dynamic_ad
  templates/               index.html (landscape), portrait.html
  ProductAssociations.csv  product → price/promo/slogan/cross-sell/prompt/image/video
  pre-defined-ads/         JPEGs seeded into Qdrant at startup (and any predefined video clips)

configs/
  pid/config.json          GStreamer pipeline + payload destinations
  pid/models/              never committed
  pid/videos/              sample .avi files
  mosquitto/config/        anonymous listener on 1883
  nginx/nginx.conf         TLS termination + all routing (envsubst template)
  nginx/nginx-cert-gen.sh  self-signed cert generation on every start

scripts/                   download_models.sh (model-download microservice), check-stack.sh
performance-tools/         git submodule for `make benchmark-*` (empty until `make update-submodules`)
```

`aig/src/database/version.py` is misnamed — it holds both singletons, every environment accessor,
and the whole Qdrant layer, not version metadata. Most AIG changes touch it.
