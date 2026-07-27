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
4. **aig-server** answers one of two ways: a semantic lookup against **ase-chromadb** for a
   predefined ad, or SDXL-Turbo generation. The web UI tries predefined first.
5. **mediamtx** + **coturn** deliver the video over WebRTC.
6. **nginx** terminates TLS and is the single door into the stack — it proxies the web UI, the
   AIG API, Swagger, and the WebRTC signalling paths.

Detection and ad generation are decoupled by the MQTT queue, so a slow generation backs up ads
without stalling the video. That decoupling is why ad latency and video smoothness are
independent symptoms.

## Services

All eight run `read_only: true` with `no-new-privileges`, on the `app_network` bridge.

| Service / container | Image | Internal port | Depends on |
|---|---|---|---|
| `mqtt-broker` | `eclipse-mosquitto:2.0.22` | 1883 | — |
| `ase-chromadb` | `chromadb/chroma:1.5.9` | 8000 | — |
| `mediamtx` | `bluenviron/mediamtx:1.18.2` | 8889 (WHIP/WHEP) | — |
| `coturn` | `coturn/coturn:4.12.0` | 3478 | — |
| `dlstreamer-pipeline-server` | `intel/dlstreamer-pipeline-server:2026.1.0-ubuntu24` | 8080 | `mediamtx` |
| `aig-server` | built from `aig/Dockerfile` | 5003 | `ase-chromadb` |
| `web-ui` | built from `web-ui/Dockerfile` | 5000 | `mediamtx`, `aig-server` |
| `nginx` (container `nginx_proxy`) | `nginx:1.31.1-trixie-perl` | 15443 → **host 5000** | `web-ui`, `mqtt-broker`, `mediamtx`, `coturn` |

Only two host ports exist: **5000** (nginx, HTTPS) and **`COTURN_UDP_PORT`** (3478, TCP+UDP).
Anything you add is unreachable from the host unless nginx proxies it — adding an endpoint means
checking whether `configs/nginx/nginx.conf` already routes to it.

MQTT is anonymous and unencrypted (`allow_anonymous true`, no TLS). MediaMTX has hardcoded
credentials in `docker-compose.yml` (`publisher`/`pubpass`, `viewer`/`viewpass` on path `cam1`),
not in `.env`.

## Startup order and its consequences

`depends_on` in this compose file waits for *container start*, not readiness, and two behaviors
depend on that:

- **web-ui seeds ChromaDB at startup.** `initialize_app()` reads `ProductAssociations.csv` and
  POSTs each row with a `pre_defined_ad_image` to `/ase/predef/` with a **5-second timeout**. If
  aig-server isn't ready, seeding fails silently for that row and there is no retry. This is why
  predefined ads sometimes just aren't there after a start.
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

`web-ui/main.py` hardcodes three URLs at module level:

```python
AIG_SERVER_URL = os.getenv('AIG_SERVER_URL', 'http://aig-server:5003')
AIG_DYNAMIC_AD_ENDPOINT          = f"{AIG_SERVER_URL}/aig/minf/"
AIG_PREDEFINED_AD_STORE_ENDPOINT = f"{AIG_SERVER_URL}/ase/predef/"
AIG_PREDEFINED_AD_QUERY_ENDPOINT = f"{AIG_SERVER_URL}/ase/predef/query/ad"
```

`AIG_SERVER_URL` is not set in `.env` or compose; the default is correct on the compose network.
The web UI is the **only** consumer of these endpoints, so a schema change has exactly one caller
to update — but nothing enforces it. Flask-RESTX validates the request against `@api.expect`, so
an unknown field is rejected while a *missing optional* field is silently defaulted.

Timeouts differ sharply by path: **5 seconds** for the predefined query and for seeding, **400
seconds** for dynamic generation. If you make the predefined path slower — a bigger embedding
model, more results — you may cross that 5-second line and turn every ad into a generated one
with no error anywhere.

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
not a session — see `web-ui-service.md`.

## Volumes and what survives a restart

| Volume | Mounted at | Survives `make down`? |
|---|---|---|
| `chroma_data` | ase-chromadb `/data` and `/tmp` | **No** — `make down` passes `-v` |
| `vol_pipeline_root`, `vol_nginx_tmpfs` | tmpfs | No |
| `./aig/models` | aig-server `/opt/models` (host bind) | Yes |
| `./aig/sharedata` | aig-server `/opt/sharedata` (host bind) | Yes |
| `./aig/src` | aig-server `/home/aigserver/src` (host bind) | Yes |
| `./configs/pid/models`, `./configs/pid/videos`, `config.json` | pipeline server (host binds) | Yes |
| `./web-ui/ProductAssociations.csv`, `./web-ui/pre-defined-ads` | web-ui, read-only | Yes |

Two consequences worth internalizing:

- **ChromaDB is ephemeral.** Every `make up` re-seeds from the CSV. There is no migration
  concern and no persistent state to corrupt, but also no way to accumulate ads across runs
  except through the CSV.
- **`aig/src` is bind-mounted and Flask runs with `debug=True`**, so Python edits under
  `aig/src/` take effect on a `docker restart aig-server` without a rebuild. `web-ui/main.py` is
  baked into its image and needs `make build`. This asymmetry is the single biggest factor in
  how fast you can iterate.

## Repository layout

```
aig/
  src/
    __main__.py            entry point; argparse on AIG_PORT, starts Flask (debug=True)
    server/apis/           REST layer
      __init__.py          Api() + add_namespace registration
      status.py            GET /aig/hstatus/<id>
      version.py           GET /aig/versions
      modelinf.py          POST /aig/minf/  — SDXL-Turbo generation
      predefinedads.py     the six /ase/predef* endpoints
    database/
      version.py           AigServerMetadata + AseServerMetadata singletons, all env accessors,
                           ChromaDB client and helpers  (646 lines — the centre of gravity)
      utils.py             sample-data loading
      testASE.py           live-call test example
    imgproc/
      img_frame.py         ImgDecorator — all overlay drawing
  models/                  never committed
  sharedata/               mounted at /opt/sharedata
  Dockerfile, run.sh, requirements.txt, export-requirements.txt

web-ui/
  main.py                  Flask app, MQTTSubscriber, Ad_Generator  (766 lines)
  templates/               index.html (landscape), portrait.html
  ProductAssociations.csv  product → price/promo/slogan/cross-sell/prompt/image
  pre-defined-ads/         JPEGs seeded into ChromaDB at startup

configs/
  pid/config.json          GStreamer pipeline + payload destinations
  pid/models/              never committed
  pid/videos/              sample .avi files
  mosquitto/config/        anonymous listener on 1883
  nginx/nginx.conf         TLS termination + all routing (envsubst template)
  nginx/nginx-cert-gen.sh  self-signed cert generation on every start
```

`aig/src/database/version.py` is misnamed — it holds both singletons, every environment accessor,
and the whole ChromaDB layer, not version metadata. Most AIG changes touch it.
