# Troubleshooting

Symptom-driven. Each entry gives the check that confirms the cause before the fix, because most
of these symptoms have more than one plausible explanation.

Run `make status` first for anything that isn't obviously a build problem — it
separates "container is dead" from "container is running but returning nothing", which halves
the search space immediately.

## Contents

- [Bring-up failures](#bring-up-failures) — `make build` / `make up` won't complete
- [Containers](#containers) — start but restart, exit, or misbehave
- [Video panel](#video-panel) — black, frozen, or never connects
- [Ads](#ads) — missing, static, repetitive, or wrong
- [Performance](#performance) — slow generation, memory pressure
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

### `Error: configs/pid/models directory does not exist.` / `... is empty.`

Models haven't been downloaded. Run `make download_models`.

Note this check only tests for a **non-empty directory**. A download that died partway leaves
files behind, passes the check, and fails later with an OpenVINO "cannot read model" error at
inference time. If the stack starts but inference fails, re-run with
`make download_models FORCE=1` (or just the affected half — `make download_models_pid` /
`make download_models_aig`).

### `HOST_IP (...) is not a valid IPv4 address format or localhost.`

`HOST_IP` must be exactly `localhost` or a dotted quad. A hostname, an IPv6 address, or an
address with a port or CIDR suffix all fail. Get the LAN address with `hostname -I | awk '{print $1}'`.

### `make build` fails pulling images or installing packages

Almost always proxy. Configure Docker's daemon proxy for the image pulls *and* export
`http_proxy`, `https_proxy`, `no_proxy` in the shell for the build args compose forwards. Both
are needed — the daemon proxy covers `docker pull`, the environment covers `pip`/`apt` inside
the build.

If it fails on disk space, the SDXL export plus the DL Streamer image want roughly 40 GB.
`docker system prune -a` between attempts.

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
  `/opt/models/sdxl_turbo_ov/int8` and that `aig/models/sdxl_turbo_ov/int8/` on the host has an
  `.xml`/`.bin` pair.
- **nginx_proxy** — certificate generation failed, or an upstream name doesn't resolve. nginx
  refuses to start if it can't resolve an upstream at config-load time, so a dead `web-ui` can
  take nginx down with it.

### `mediamtx` logs "no space left on device"

MediaMTX writes into a tmpfs. Either free host memory or reduce what's being buffered; a
`make down && make up` clears it.

### Everything looks up but nothing responds on port 5000

Confirm nginx is actually listening. The host port **5000 maps to container port 15443**, which
is HTTPS — hitting `http://localhost:5000` gives a protocol error rather than a page. Use
`https://localhost:5000`.

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
(`turn:${HOST_IP}:${COTURN_UDP_PORT}`), so with `HOST_IP=localhost` a remote browser tries to
reach a TURN server on its own machine. Set the host's real LAN IP and `make up`.

Also confirm `COTURN_UDP_PORT` (3478) is reachable — it's published on both TCP and UDP, and a
host firewall blocking UDP 3478 breaks relay while leaving everything else working.

### Certificate warning, then nothing loads

The certificate is self-signed with `CN=localhost`, regenerated on every nginx start. You must
accept the warning **for the iframe origin as well**, which browsers treat separately in some
configurations. Loading `https://<host>:5000/samplestream/` directly once and accepting there
clears it.

Use Chrome. The page is developed against it and other browsers vary in how they handle the
self-signed certificate on a nested WHEP request.

### Video plays but detections aren't drawn

Detection overlay comes from `gvawatermark` in the pipeline, but the WebRTC frame destination
is configured with `overlay: false` — the boxes are burned in by the pipeline itself. If the
video is clean, detection isn't producing results: check that the model path in
`configs/pid/config.json` matches what's actually in `configs/pid/models/`.

---

## Ads

### No ad ever appears

Work backwards from the browser.

1. **Is the API alive?** `curl -k https://localhost:5000/aig-api/aig/hstatus/1` should return
   `{"status": "ok", "id": 1}`. If not, the problem is aig-server, not ad logic.
2. **Can it generate at all?** Post a minimal request to `/aig/minf/` — see `api-usage.md`. If
   that returns a JPEG, generation works and the problem is upstream in detection or selection.
3. **Are detections arriving?** `docker logs web-ui | tail -50`. The web UI logs the labels it
   accepts. No labels means MQTT or detection is the problem.

The most common cause of "detections happen but no ad" is the filtering thresholds: a label must
appear in at least `OBJECT_RECENCY_FRAME_COUNT` (5) messages within a rolling window of twice
that, with mean confidence at least `OBJECT_CONFIDENCE_THRESHOLD` (0.5). Lower both to confirm.

The second most common is label mismatch: the detected label must map to a `primary_product` row
in `web-ui/ProductAssociations.csv` after normalization (lowercased, `-` and `_` become spaces).
A model whose class names don't match the CSV produces detections that select nothing.

### Ads appear but are always generated, never predefined

The semantic lookup is failing its distance threshold. `ASE_DISTANCE_MAX_THRESHOLD=0.2` is
strict. Query the API directly with `/ase/predef/query` (see `api-usage.md`) and look at the
returned distances — if they cluster above 0.2, raise the threshold toward 0.4–0.5.

Also confirm the ads were seeded. The web UI POSTs every CSV row that names a
`pre_defined_ad_image` into ChromaDB at startup with a 5-second timeout; if aig-server wasn't
ready yet, seeding silently fails. `make down && make up` retries. Remember `make down -v`
removes the ChromaDB volume, so seeding happens fresh every time.

If `ASE_MODEL_PATH` doesn't load, the code falls back to ChromaDB's default embedding function
without erroring — similarity scores change completely and previously-tuned thresholds stop
working. Check aig-server logs for the fallback.

### The same ad repeats

There is anti-repeat logic in both product selection (`find_rotating_candidate` prefers the
least-recently-shown product) and variant selection, but with few detected products it has
little to work with. If only one product is ever detected, that's a detection-coverage problem,
not an ad problem.

Also check `TIME_TO_DISPLAY_AD_SECONDS` — it's a floor on display time, so a large value looks
like a stuck ad.

### Ad panel is stuck on one image but the API works

The browser polls `/get_current_advertisement` every 2 seconds and the endpoint returns **204
No Content** when the client already has the current ad. A stuck panel with 204s in the network
tab means the ad generator thread isn't producing new ads — check web-ui logs. A stuck panel
with 200s means the browser is rendering stale content; hard-reload.

---

## Performance

### First generation takes minutes

Expected. OpenVINO compiles the model for the target device on first use and caches the result.
Subsequent generations are much faster.

### Every generation is slow

Two likely causes:

- **`AIG_KEEP_MODEL_IN_MEMORY=false`** — the model is unloaded after each request and reloaded
  for the next. Set it to `true` if you have the ~10 GB.
- **Device mismatch** — `/aig/minf/` only reuses the preloaded pipeline when the request's
  `device` field equals `AIG_MODEL_DEVICE`. The web UI hardcodes `"GPU"`, so setting
  `AIG_MODEL_DEVICE=CPU` causes a fresh pipeline build on every single ad. Keep them aligned.

Falling back to CPU when you expected GPU also does this: check `docker logs aig-server` for
OpenVINO device availability, and confirm `/dev/dri` exists and is non-empty on the host.

### Memory pressure

`AIG_KEEP_MODEL_IN_MEMORY=false` drops resident usage from roughly 10 GB to 2 GB at the cost of
per-request reload latency. `AIG_MODEL_NUM_INFERENCE_STEPS` doesn't change memory meaningfully —
SDXL-Turbo is designed for 1–4 steps and raising it only costs time.

---

## Known repo defects

Tell the user these are repository bugs so they don't keep debugging their own setup.

| Symptom | Reality |
|---|---|
| API docs are incomplete | `docs/user-guide/api-reference.md` covers 4 of 9 endpoints. See `api-usage.md` |
| `docs/user-guide/get-started.md` model steps are a long manual block | Superseded by `make download_models`; the doc hasn't been updated |
| Sample data never loads | `ASE_ENABLE_SAMPLEDATA=1` but `ASE_ENABLE_SAMPLEDATA_DIR=/opt/sharedata/sample` doesn't exist in the repo, so loading is a no-op |
| `use_default_ad_onempty` returns nothing useful | `ASE_IMG_DEFAULT_AD=/opt/sharedata/default_ad.jpg` doesn't exist in `aig/sharedata/` |
| aig-server runs Flask in debug mode | `aig/src/__main__.py` passes `pdebug=True` even in the compose deployment. Not a functional problem for the demo, but don't expose it beyond a lab network |
