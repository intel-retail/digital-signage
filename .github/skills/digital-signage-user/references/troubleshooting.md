# Troubleshooting

Symptom-driven. Each entry gives the check that confirms the cause before the fix, because most
of these symptoms have more than one plausible explanation.

Run `make status` first for anything that isn't obviously a build problem — it
separates "container is dead" from "container is running but returning nothing", which halves
the search space immediately.

## Contents

- [Bring-up failures](#bring-up-failures) — `make build` / `make up` won't complete
- [Model download](#model-download) — `make download_models` fails, hangs or times out
- [Containers](#containers) — start but restart, exit, or misbehave
- [Video panel](#video-panel) — black, frozen, or never connects
- [Ads](#ads) — missing, static, repetitive, or wrong
- [MCP and video ads](#mcp-and-video-ads) — agent tools and `trigger_video_ad`
- [Performance](#performance) — slow generation, memory pressure
- [NPU](#npu) — image ads on the NPU
- [Known repo defects](#known-repo-defects) — not your fault

---

## Bring-up failures

### `'MTX_WEBRTCICESERVERS2_0_USERNAME' in ./.env is unassigned.`

The repo ships both WebRTC credentials empty. Set them in `.env`:

```
MTX_WEBRTCICESERVERS2_0_USERNAME=signage
MTX_WEBRTCICESERVERS2_0_PASSWORD=signage123
```

Username must be letters only and at least 5 characters; password must be alphanumeric, at
least 8, with at least one digit and one letter. Don't quote the values — the Makefile greps
them out of the file literally.

### `Missing required model artifact: ...`

Models haven't been downloaded (or a download died partway). Run `make download_models` — see
[Model download](#model-download) if that fails. `make check_models` looks for exactly four
files: `yolo11s.xml` and `yolo11s.bin` under `configs/pid/models/object_detection/yolo11s/INT8/`,
`aig/models/sdxl_turbo_ov/int8/graph.pbtxt` and `aig/models/all-MiniLM-L12-v2/config.json`. A
model that exists but is corrupt still passes and fails later with an OpenVINO "cannot read
model" error at inference. The optional LTX-Video model is not checked.

To redo one model, delete its directory (for example `aig/models/sdxl_turbo_ov/int8`) and re-run
`make download_models`; there is no `FORCE` option or per-half target any more.

### `HOST_IP is not set` / `HOST_IP (...) must be a valid IPv4 address format`

`HOST_IP` must be a dotted-quad IPv4 address with every octet 0–255. **`localhost` is rejected**,
as are hostnames, IPv6 addresses, and anything with a port or CIDR suffix. Use `127.0.0.1` for
local-only access, or the host's LAN address (`hostname -I | awk '{print $1}'`) for remote
access. After changing it, `make up` so the containers are recreated with the new port bindings.

### `make build` fails pulling images or installing packages

Almost always proxy. Configure Docker's daemon proxy for the image pulls *and* export
`http_proxy`, `https_proxy`, `no_proxy` in the shell for the build args compose forwards. Both
are needed — the daemon proxy covers `docker pull`, the environment covers `pip`/`apt` inside
the build. The aig-server build also `curl`s Intel GPU/NPU driver packages from `github.com`,
so that host must be reachable through the proxy.

If it fails on disk space, the images plus models want a lot of room — the docs recommend 500 GB
free. `docker system prune -a` between attempts.

### `make up` tries to pull `intel/aig-server:<tag>` and fails

`make up` runs `docker compose up -d`, which builds nothing. If the images weren't built locally
under the current `IMAGE_SUFFIX`, compose tries to pull them. Run `make build` first, and keep
`IMAGE_SUFFIX` / `WEEKLY_BUILD_DATE` / `DOCKER_REGISTRY` the same between build and up.

---

## Model download

`make download_models` runs `scripts/download_models.sh`, which starts the `model-download`
container (`MODEL_DOWNLOAD_IMAGE`) on `127.0.0.1:${MODEL_DOWNLOAD_PORT:-8000}`, submits three jobs
(YOLO11s, SDXL-Turbo, MiniLM), copies/links the results into place, then exports the optional
LTX-Video model. It prints the container logs whenever a step fails — read those first. Re-running
is safe: finished models are skipped only when **all** artifacts (LTX-Video included) exist.

| Symptom | Cause and fix |
|---|---|
| `Failed to pull model-download image` | Docker Hub unreachable, proxy not configured for the daemon, or `DOCKER_REGISTRY` set to a registry that lacks `intel/model-download`. Check `docker pull <MODEL_DOWNLOAD_IMAGE>` by hand |
| `Timed out waiting for model-download microservice health check` / `exited before becoming healthy` | Waits 180 s. Likely a port clash on 8000 (set `MODEL_DOWNLOAD_PORT` in `.env`; `ss -ltnp \| grep 8000`) or a start-up error in `docker logs model-download` |
| `Failed to submit model download for ...` | The container is up but rejected the job — see the logs it prints; usually an unreachable model hub |
| `Model download job ... ended with status: failed` | Network/proxy/TLS to Hugging Face or Ultralytics, or out of disk. The job JSON and container log are printed |
| `Timed out waiting for model download jobs` | Waits `MODEL_DOWNLOAD_TIMEOUT_SECONDS` (7200 s). The SDXL export is slow; raise the value, or fix a stalled link and retry |
| Slow or rate-limited Hugging Face downloads | Provide a token: `export HF_TOKEN=...` (or `HUGGINGFACEHUB_API_TOKEN`) before `make download_models`. Don't commit it |
| TLS / `certificate verify failed` behind a corporate proxy | The container uses a host CA bundle: it auto-picks `/etc/ssl/certs/ca-certificates.crt` or `/etc/pki/tls/certs/ca-bundle.crt`. Point `MODEL_DOWNLOAD_CA_BUNDLE` at a file that contains your proxy's CA; with no usable default the container has no CA file to verify against |
| Proxy not honoured | Export lower-case `http_proxy`, `https_proxy`, `no_proxy` in the shell running `make` (forwarded into the container) |
| Container can't write models / `Permission denied` under `aig/models` or `configs/pid/models` | The script gives the container your gid and sets group write on those directories. Directories created earlier by root (e.g. via `sudo`) break this — `chown` them back to your user. Never run `make` with `sudo` |
| `Expected ... output was not found` / `Expected exactly one SDXL-Turbo output directory` | A partial or stale staging directory. `rm -rf aig/models/.model-download configs/pid/models/object_detection/.model-download` and retry |
| Helper files fail to download | The compose command rewrites `raw.githubusercontent.com` URLs to `cdn.jsdelivr.net`; allow that host as well as the model hubs |

### The LTX-Video export is slow, fails, or is skipped

It runs last and only matters for `trigger_video_ad`. It creates `scripts/.ltx-export-venv`,
installs `optimum-intel`, and exports Lightricks/LTX-Video as INT8 into
`aig/models/ltx_video_ov/int8` — large and long. It is **skipped when `CI` is set** in the
environment (the script says so) or when `SKIP_LTX_VIDEO_EXPORT=1`; set `SKIP_LTX_VIDEO_EXPORT=0` to
force it. If it fails, the other models are already in place and `make up` still works; without
LTX, `trigger_video_ad` for an item with no predefined video just fails (see
[MCP and video ads](#mcp-and-video-ads)).

---

## Containers

### A container restarts in a loop

```bash
docker logs --tail 50 <name>
```

Common causes by container:

- **web-ui** — MQTT connection failed. `main.py` calls `os._exit(1)` rather than retrying, so
  any MQTT problem presents as a restart loop. Check `mqtt-broker` is up first.
- **aig-server** — model path wrong or model files incomplete. Check `AIG_MODEL_PATH` points at
  `/opt/models/sdxl_turbo_ov/int8` and that `aig/models/sdxl_turbo_ov/int8/` on the host has the
  exported pipeline (`graph.pbtxt` and the model subfolders). Models and Qdrant load lazily, so a
  Qdrant or embedding-model problem does not restart the container — it shows up as failing
  `/ase/*` calls instead (see [Ads](#ads)).
- **nginx_proxy** — certificate generation failed, or an upstream name doesn't resolve. nginx
  refuses to start if it can't resolve an upstream at config-load time, so a dead `web-ui` can
  take nginx down with it.
- **ase-qdrant** — check `docker logs ase-qdrant`. Its data lives in named volumes that
  `make down` deletes, so a clean `make down && make up` is a safe reset.

### `mediamtx` logs "no space left on device"

Usually not disk capacity: the host has run out of inotify watches/instances, open-file limits
or inodes. Check `cat /proc/sys/fs/inotify/max_user_watches /proc/sys/fs/inotify/max_user_instances`
and `df -i`. Raise them (project docs suggest `fs.inotify.max_user_watches=1048576` and
`fs.inotify.max_user_instances=10000` in `/etc/sysctl.conf`, then `sudo sysctl -p`), then
`make up` and watch `docker logs -f mediamtx`.

### Everything looks up but nothing responds on port 5000

Three usual causes:

- **Wrong scheme.** Host port **5000 maps to container port 15443**, which is HTTPS —
  `http://...:5000` gives a protocol error rather than a page. Use `https://<HOST_IP>:5000`.
- **Wrong address.** nginx is published only on `HOST_IP` (default `127.0.0.1`). With a real LAN
  IP set, `https://localhost:5000` no longer works on the host; with `127.0.0.1`, other machines
  can't connect at all. Check with `docker port nginx_proxy`.
- **`HOST_IP` changed without recreating.** Port bindings are fixed when the container is
  created; run `make up`.

---

## Video panel

The video is delivered over WebRTC from MediaMTX, proxied by nginx, and embedded in the page as
an iframe pointing at `/samplestream/`. Failures fall into three layers.

### Check the layers in order

1. **Is anything being published?** `docker logs dlstreamer-pipeline-server | tail -30`. The
   pipeline is `auto_start: true`, so it should be running within seconds of startup. A GStreamer
   error here means nothing downstream can work.
2. **Is MediaMTX receiving it?** `docker logs mediamtx | tail -30` should show a publisher on
   the `samplestream` path.
3. **Can the browser negotiate?** Open the browser console. WebRTC failures show as ICE
   connection errors.

### Black panel, browser console shows ICE failure

`HOST_IP` is wrong. It's substituted into the TURN URL the browser is handed
(`turn:${HOST_IP}:${COTURN_UDP_PORT}`), so with the default `127.0.0.1` a remote browser tries
to reach a TURN server on its own machine. Set the host's real IPv4 address (`localhost` is not
accepted) and `make up`.

Also confirm `COTURN_UDP_PORT` (3478) is reachable — it's published on both TCP and UDP on
`HOST_IP`, and a host firewall blocking UDP 3478 breaks relay while leaving everything else
working.

### Certificate warning, then nothing loads

The certificate is self-signed with `CN=localhost` and Subject Alternative Names for
`localhost`, `127.0.0.1`, `host.docker.internal` and `HOST_IP`, regenerated on every nginx start.
Browse to a name in that list — anything else fails hostname verification as well as trust. You
must accept the warning **for the iframe origin as well**, which browsers treat separately in
some configurations. Loading `https://<HOST_IP>:5000/samplestream/` directly once and accepting
there clears it.

Use Chrome. The page is developed against it and other browsers vary in how they handle the
self-signed certificate on a nested WHEP request.

### Video plays but detections aren't drawn

Detection overlay comes from `gvawatermark` in the pipeline, but the WebRTC frame destination
is configured with `overlay: false` — the boxes are burned in by the pipeline itself. If the
video is clean, detection isn't producing results: check that the model path in
`configs/pid/config.json` matches what's actually in `configs/pid/models/`, and that its
`device` (`CPU` by default) is available on the host.

---

## Ads

### No ad ever appears

Work backwards from the browser.

1. **Is the API alive?** `curl -k https://<HOST_IP>:5000/aig-api/aig/hstatus/1` should return
   `{"status": "ok", "id": 1}`. If not, the problem is aig-server, not ad logic.
2. **Can it generate at all?** Post a minimal request to `/aig/minf/` — see `api-usage.md`. If
   that returns a JPEG, generation works and the problem is upstream in detection or selection.
   A `503` `Device GPU unavailable: model failed to load` means the configured device is missing
   or the model failed to load — it does **not** fall back to CPU. Check `docker logs aig-server`
   for `Device ... is not available` / `Failed to load model`, and `/dev/dri` (or `/dev/accel`)
   on the host.
3. **Are detections arriving?** `docker logs web-ui | tail -50`. The web UI logs the labels it
   accepts. No labels means MQTT or detection is the problem.

Right after `make up` the web UI first waits for aig-server, then sends a warm-up generation, and
only then subscribes to MQTT — so the first real ad can lag by however long the model takes to
load (minutes on a cold NPU).

The most common cause of "detections happen but no ad" is the filtering thresholds: a label must
appear in at least `OBJECT_RECENCY_FRAME_COUNT` (5) messages within a rolling window of twice
that, with mean confidence at least `OBJECT_CONFIDENCE_THRESHOLD` (0.5). Lower both to confirm.

The second most common is label mismatch: the detected label must map to a `primary_product` row
in `web-ui/ProductAssociations.csv` after normalization (lowercased, `-` and `_` become spaces).
A model whose class names don't match the CSV produces detections that select nothing.

### Ads appear but are always generated, never predefined

First, is that expected? Only rows with a `pre_defined_ad_image` in `ProductAssociations.csv` can
ever be served from ASe — 7 of the shipped rows at the time of writing. Everything else is
generated by design.

For rows that do have an image, the semantic lookup is failing its threshold.
`ASE_QDRANT_SCORE_MIN_THRESHOLD` (default `0.8`) is a minimum cosine **similarity** — higher is
stricter, and the old distance-style tuning advice is inverted. The query the web UI sends is
`"<primary_product> and <associated_cross_sell>"`, matched against the description stored at
seeding time (same text). To see whether anything matches at all, temporarily set the threshold
to `0.0`, `make up`, and call `/ase/predef/query` (see `api-usage.md`); if that returns ads, step
the threshold down gradually (for example `0.8` → `0.7`) until the right ones return without
wrong ones. The API returns no scores, so this bisecting is the only probe.

Then confirm the ads were seeded. At startup the web UI POSTs every CSV row that names a
`pre_defined_ad_image` to `/ase/predef/` with a 15-second timeout; the first call also lazily
loads the embedding model and connects to Qdrant, so a slow first call can fail
(`docker logs web-ui | grep -i "pre-defined"`). Check the other side with `docker logs aig-server`.
`make down && make up` retries from scratch — `make down` removes the Qdrant volumes, so seeding
happens fresh every time. Restarting only `web-ui` re-seeds on top of existing data under new
random ids, creating duplicates.

If ASe itself is broken, every `/ase/*` call fails. Causes: `ASE_MODEL_PATH` doesn't load (there is
no fallback embedding model any more — look for `Error initializing embedding model` in the
aig-server log), `ase-qdrant` is down or unreachable (`ASE_QDRANT_HOST`/`PORT`, and `ase-qdrant`
must be in `no_proxy` — compose already sets it for aig-server), or you changed to an embedding
model with a different vector size than the existing collection (the log says the collection
"expects vectors of size ..."): `make down && make up`, or change `ASE_COLLECTION_NAME`.

### The same ad repeats

There is anti-repeat logic in both product selection (the first time a product is seen the
highest-priced candidate wins; after that `find_rotating_candidate` prefers the least-shown
product and avoids an immediate repeat) and variant selection, but with few detected products it
has little to work with. If only one product is ever detected, that's a detection-coverage
problem, not an ad problem.

Also check `TIME_TO_DISPLAY_AD_SECONDS` — it's a floor on display time, so a large value looks
like a stuck ad.

### Ad panel is stuck on one image but the API works

The browser polls `/get_current_advertisement` every 2 seconds and the endpoint returns **204
No Content** when the client already has the current ad. A stuck panel with 204s in the network
tab means the ad generator thread isn't producing new ads — check web-ui logs. A stuck panel
with 200s means the browser is rendering stale content; hard-reload.

Two other legitimate causes: an MCP-triggered ad is live (`trigger_ad`/`select_dynamic_ad` hold the
screen for `display_seconds`, default 60, and the override is served on every poll), or a video ad
is playing (204s for its `VIDEO_AD_DISPLAY_SECONDS`). The MCP `clear_ad` tool returns the display
to the camera flow.

---

## MCP and video ads

The MCP server runs inside `web-ui` (port 5100, internal) and nginx exposes it at
`https://<HOST_IP>:5000/mcp` (Streamable HTTP). Tools: `describe`, `get_current_ad`,
`get_catalog`, `select_dynamic_ad`, `trigger_ad`, `trigger_video_ad`, `clear_ad`. Details in
`docs/user-guide/how-to-guides/use-mcp-agent-tools.md`.

| Symptom | Cause and fix |
|---|---|
| Client can't connect or fails TLS | The certificate is self-signed; the client must skip verification or trust it, and connect to `localhost`, `127.0.0.1`, `host.docker.internal` or `HOST_IP` (the SANs). Port 5100 isn't published — always go through nginx |
| 502 Bad Gateway on `/mcp` | `docker logs web-ui \| grep -i mcp`. `MCP server thread started` is normal; `mcp package not available` or a bind error means MCP is disabled (nginx has nothing on 5100) while the rest of the app keeps working |
| `select_dynamic_ad` says no context or "could not resolve" | Needs at least one of `weather`, `demand`, `age_mix`, `daypart`, and an exact (case-insensitive) match in `web-ui/context_rules.json`; otherwise `default_product` (`banana`) is used. If that file is missing/invalid the tool is unavailable (log: `Could not load context rules`). The resolved product must exist in the CSV |
| `Unknown item: ...` | `trigger_ad`/`trigger_video_ad` take a `primary_product` from the CSV (normalized like detections). The error lists `available_items`; `get_catalog` shows them |
| `Another ad generation is already in progress` | Another agent ad holds the generation lock (the call waits ~6 s first). Retry shortly |
| `trigger_video_ad` rejected: video still playing / already generating | By design — it never preempts. Retry after the clip ends (3 s) or the generation finishes. After `clear_ad` during generation, the abandoned request must still finish before a new trigger is accepted |
| `Provide either item or description` / `not both` | `trigger_video_ad` takes exactly one of the two |
| Video call returns "generating", nothing ever appears | Generation failed in the background. `docker logs web-ui` shows `AIG server error while generating video ad ...: 500`; `docker logs aig-server` shows why. Typical: LTX-Video model missing (`aig/models/ltx_video_ov/int8` — see [Model download](#model-download)), `AIG_VIDEO_MODEL_PATH` unset, or the video device unavailable |
| Video takes minutes | Expected: about 30 s on an iGPU with `AIG_VIDEO_PRECISION=f16` once loaded, ~3 min with `f32`, plus ~20 s on the first request unless `AIG_PRELOAD_VIDEO_MODEL=true`. The web UI waits up to 15 minutes |
| Video looks wrong or the wrong length | `AIG_VIDEO_NUM_FRAMES` must be 8k+1 and `AIG_VIDEO_LOOP_SECONDS` should equal `VIDEO_AD_DISPLAY_SECONDS` (both 3 as shipped); size must be divisible by 32 |
| Predefined video ignored | In `docker logs web-ui` at startup look for `Pre-defined video ad file not found`, `Unsupported pre-defined video ad extension`, or `exceeds ...s`. Only `.mp4`, `.webp`, `.gif` in `web-ui/pre-defined-ads/`, no longer than `VIDEO_AD_DISPLAY_SECONDS` + 0.5 s, are accepted |

---

## Performance

### First generation takes minutes

Expected. The image model loads lazily on the first request (the web UI's start-up warm-up
triggers it), so the first ad after `make up` is slow; later ones are fast while
`AIG_KEEP_MODEL_IN_MEMORY=true`. On the NPU the first compile takes about 3 minutes and is then
cached on disk (see [NPU](#npu)).

### Every generation is slow

Likely causes:

- **`AIG_KEEP_MODEL_IN_MEMORY=false`** — the model is unloaded after each request and reloaded
  for the next. Set it to `true` if you have the ~10 GB.
- **Device mismatch on manual calls** — `/aig/minf/` only reuses the preloaded pipeline when the
  request's `device` equals the configured `AIG_INFERENCE_DEVICE`; the web UI sends that same
  value, so only hand-written requests hit this.
- **Chrome competing for the GPU** on low-resource hosts. The project docs suggest Chrome with GPU
  acceleration disabled (`--disable-gpu`, or turn off *Use graphics acceleration when available*).

A missing GPU does not slow things down — it returns `503`s (see
[No ad ever appears](#no-ad-ever-appears)). Confirm `/dev/dri` exists and is non-empty on the host.

### Memory pressure

`AIG_KEEP_MODEL_IN_MEMORY=false` drops resident usage from roughly 10 GB to 2 GB at the cost of
per-request reload latency. `AIG_MODEL_NUM_INFERENCE_STEPS` doesn't change memory meaningfully —
SDXL-Turbo is designed for 1–4 steps and raising it only costs time. The video model adds about
8 GB (f16) to 11 GB (f32) of GPU/shared memory while loaded; `AIG_PRELOAD_VIDEO_MODEL=true` holds it
from start-up.

---

## NPU

Experimental, image ads only (`AIG_INFERENCE_DEVICE=NPU`). The video model cannot use the NPU and
falls back to `GPU`. PID can also run on the NPU via `device` in `configs/pid/config.json`. Full
guide: `docs/user-guide/how-to-guides/change-inference-device.md`.

| Symptom | Check |
|---|---|
| First start takes ~3 minutes | Normal first compile (static shape = `AIG_IMG_WIDTH/HEIGHT_DEFAULT`); requests queue behind it. Wait it out; the blob cache then makes later starts fast |
| Long compile on every start | Cache not persisting: `AIG_NPU_CACHE_HOST_DIR` (default `./aig/npu_cache`) must exist and be writable by `UID` (`ls -ld aig/npu_cache`); changing the image size forces a new compile |
| Disk fills up | About 7 GB per image size is cached. Clear `aig/npu_cache` if you no longer need old sizes |
| `[AIG] Device NPU is not available` in `docker logs aig-server` | `/dev/accel` missing on the host or not mounted (the Makefile substitutes `/dev/null` silently). `docker exec aig-server ls -l /dev/accel`; check `ACCEL_MOUNT_PATH` if you ran compose by hand |
| Permission denied on `/dev/accel/accel0` | The container user isn't in the device's group. Compose adds render gids 109/110/992/990; otherwise add `stat -c %g /dev/accel/accel0` to `group_add`. For host access rules see `configs/pid/scripts/cfgNPUAccess.sh` |
| `503 Device NPU unavailable: model failed to load` on every request | The compile failed; the retry is held off for 5 minutes. Read `Failed to load model on NPU` in the log, fix, then restart `aig-server` |
| NPU not listed by OpenVINO | `ZE_ENABLE_ALT_DRIVERS` must be `libze_intel_npu.so` (set in compose); the NPU user-mode driver is bundled in the aig-server image, so rebuild the image after pulling updates |

---

## Known repo defects

Tell the user these are repository bugs so they don't keep debugging their own setup.

| Symptom | Reality |
|---|---|
| API docs are incomplete | `docs/user-guide/api-reference.md` covers 3 of the 10 AIG operations (plus the web UI's `get_current_advertisement`); `/aig/mvid/`, `hstatus`, `versions`, fetch/delete and two query variants are missing. See `api-usage.md` |
| `docs/user-guide/get-started.md` says `make up` "downloads and prepares the required models" | It only checks them (`make check_models`); run `make download_models` first |
| `get-started.md` lists `AIG_INFERENCE_DEVICE` as `CPU` or `GPU` | `NPU` is accepted (experimental) |
| Docs give `VIDEO_AD_DISPLAY_SECONDS` default 5 | The shipped `.env` sets 3 (5 is only the web-ui code fallback) |
| Sample data never loads | `ASE_ENABLE_SAMPLEDATA=1` but `ASE_ENABLE_SAMPLEDATA_DIR=/opt/sharedata/sample` doesn't exist in the repo, so loading is a no-op |
| `use_default_ad_onempty` returns nothing useful | `ASE_IMG_DEFAULT_AD=/opt/sharedata/default_ad.jpg` doesn't exist in `aig/sharedata/` |
| `slogan_details` has no effect on `/aig/minf/` and `/aig/mvid/` | The slogan step is a deliberate no-op there; it does work on `/ase/predef/query/ad` and `/firstad` |
| `ENABLE_OPEN_TELEMETRY` / `PROMETHEUS_PORT` in `.env` do nothing | Compose hardcodes telemetry on for the pipeline server and doesn't reference `PROMETHEUS_PORT` |

