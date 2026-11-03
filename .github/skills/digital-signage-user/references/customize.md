# Customizing the Deployment

Changing input source, inference device, models, and ad content. Every change here needs
`make up` afterwards — `.env`, `config.json` and the CSV are all read at container start.

## Contents

- [Where the knobs live](#where-the-knobs-live)
- [Switch the simulation video](#switch-the-simulation-video)
- [Use a live RTSP camera](#use-a-live-rtsp-camera)
- [Change the inference device](#change-the-inference-device)
- [Swap the detection model](#swap-the-detection-model)
- [Add or change predefined ads](#add-or-change-predefined-ads)
- [Enable AI video ads](#enable-ai-video-ads)
- [Drive the display from an agent (MCP)](#drive-the-display-from-an-agent-mcp)
- [Tune ad behavior](#tune-ad-behavior)
- [Benchmark](#benchmark)

## Where the knobs live

Newcomers reliably look in the wrong place, so start here:

| To change | Edit | Not |
|---|---|---|
| Video source, detection model, detection device | `configs/pid/config.json` | `.env` |
| Generation device (image/video), model path, NPU cache, overlay defaults | `.env` | `config.json` |
| Which products map to which ads (image or video) | `web-ui/ProductAssociations.csv` | code |
| Ad images / predefined videos | `web-ui/pre-defined-ads/` + the CSV | the API directly |
| Context → product rules for the MCP `select_dynamic_ad` tool | `web-ui/context_rules.json` | code |
| Detection sensitivity, ad cadence | `.env` | `config.json` |
| Which host address the UI/TURN listen on | `HOST_IP` in `.env` | compose |

The pipeline server's model and device are pipeline *payload parameters*, not environment
variables — `RTSP_CAMERA_IP` existing in `.env` misleads people into thinking otherwise. It is
only a value you may interpolate manually into the pipeline string.

## Switch the simulation video

The repo ships `test_shopping_items.avi` (in use) and `Basket.avi` in `configs/pid/videos/`,
which is mounted into the container at `/home/pipeline-server/resources/externalvideos/`.

1. Put your `.avi` in `configs/pid/videos/`.
2. In `configs/pid/config.json`, change the `location=` in the pipeline string:

```
multifilesrc loop=TRUE location=/home/pipeline-server/resources/externalvideos/Basket.avi name=source ! h264parse ! decodebin ! ...
```

3. `make up`.

The path is the **container** path, so keep the `/home/pipeline-server/resources/externalvideos/`
prefix and change only the filename. `loop=TRUE` restarts the file endlessly, which is what
makes the demo run unattended.

The pipeline begins `multifilesrc ! h264parse`, so the file must contain H.264. A video in
another codec parses as garbage and the pipeline errors out — re-encode first:

```bash
ffmpeg -i input.mp4 -c:v libx264 -an configs/pid/videos/my_video.avi
```

Detection quality depends on the video containing objects in the YOLO11s class set that also
appear as `primary_product` values in `ProductAssociations.csv`. A video full of products the
CSV doesn't list will detect fine and generate no ads.

## Use a live RTSP camera

Replace the `multifilesrc` head of the pipeline with `rtspsrc` in `configs/pid/config.json`:

```
rtspsrc location=rtsp://<user>:<pass>@10.0.0.42:554/stream1 latency=100 ! rtph264depay ! h264parse ! decodebin ! videoconvert ! video/x-raw,format=BGR ! gvadetect name=detection ! queue ! gvawatermark displ-cfg="font-scale=1.5,thickness=3,color-idx=2,font-type=plain" ! gvafpscounter ! appsink name=destination
```

Two things change versus the file source: `rtspsrc` needs `rtph264depay` before `h264parse` to
strip RTP framing, and `loop=TRUE` goes away since a live source doesn't end.

The RTSP path is camera-specific — check your camera's documentation rather than guessing.
Verify the URL works before wiring it in:

```bash
ffplay rtsp://<user>:<pass>@10.0.0.42:554/stream1
```

`RTSP_CAMERA_IP` in `.env` exists as a convenience but nothing reads it automatically; if you
want to use it, interpolate it yourself. Note that credentials embedded in `config.json` are
stored in plaintext in the repo — prefer a camera account with view-only rights.

Raise `latency=` if the stream stutters; lower it for responsiveness on a reliable network. The
how-to guide (`docs/user-guide/how-to-guides/configure-rtsp-camera.md`) uses `latency=0
drop-on-latency=true` with `rtph264depay ! video/x-h264,stream-format=byte-stream ! decodebin3`
and no `protocols=udp` — a good starting point on a reliable network.

## Change the inference device

There are **two independent devices** and confusing them is a common mistake.

**Detection (DL Streamer)** — `configs/pid/config.json`, under
`payload.parameters.detection-properties`:

```json
"detection-properties": {
    "model": "/home/pipeline-server/object_detection/yolo11s/INT8/yolo11s.xml",
    "device": "CPU"
}
```

Set to `CPU`, `GPU`, or `NPU`.

**Image generation (AIG / SDXL-Turbo)** — `AIG_INFERENCE_DEVICE` in `.env`, default `GPU`; `CPU`,
`GPU` or `NPU` (experimental). The same variable feeds both aig-server and the web UI, so the
device the web UI requests always matches the preloaded pipeline.

**Video generation (LTX-Video)** — `AIG_VIDEO_INFERENCE_DEVICE`, default `GPU`; `CPU` or `GPU`
only (`NPU` is changed to `GPU`). See [Enable AI video ads](#enable-ai-video-ads).

Each requires the corresponding host device to exist. `GPU` needs a populated `/dev/dri`; `NPU`
needs `/dev/accel`. The Makefile probes for these when it is parsed and substitutes `/dev/null`
if absent, so a missing device produces a container that starts normally and then fails at
inference (requests return `503`) — check `docker logs` rather than assuming the mount worked.

For NPU access on the host you may need the udev rule in `configs/pid/scripts/cfgNPUAccess.sh`,
which grants access to `/dev/accel/accel0`. It is not run by `make up`; run it on the host once.
No host user-mode NPU driver is needed for AIG — the aig-server image bundles it, so rebuild the
image (`make build`) after pulling updates.

### Running image ads on the NPU (experimental)

```text
AIG_INFERENCE_DEVICE=NPU
AIG_KEEP_MODEL_IN_MEMORY=true
```

then `make up`. What to expect:

- The model is compiled for a fixed size, `AIG_IMG_WIDTH_DEFAULT` x `AIG_IMG_HEIGHT_DEFAULT`
  (448 x 448); the first start takes about 3 minutes.
- Compiled blobs are cached in `AIG_NPU_CACHE_HOST_DIR` (default `./aig/npu_cache`, mounted at
  `/opt/npu_cache`). It survives `make down`, must be writable by `UID`, and takes about 7 GB per
  image size — delete the directory's contents to reclaim space.
- Keep `AIG_KEEP_MODEL_IN_MEMORY=true`; otherwise every request reloads the model.
- If the NPU load fails, requests return `503` and the load isn't retried for 5 minutes
  (restart `aig-server` to retry). See `troubleshooting.md` § NPU.

Switching device later means `make up` again. `make benchmark-*` targets also rewrite the
detection `device` and `AIG_INFERENCE_DEVICE` (see [Benchmark](#benchmark)).

## Swap the detection model

The default is YOLO11s quantized to INT8. To use a different model — including one exported
from Intel Geti:

1. Place the OpenVINO IR (`.xml` + `.bin`) under `configs/pid/models/object_detection/<name>/`.
   That directory is mounted into the container at `/home/pipeline-server/object_detection/`.
2. Update the `model` path in `config.json` to the **container** path,
   e.g. `/home/pipeline-server/object_detection/my_model/my_model.xml`.
3. If the model needs a model-proc file for output parsing, add
   `"model-proc": "/home/pipeline-server/object_detection/<name>/<name>.json"` alongside `model`.
4. `make up`.

The step people skip: **the model's class labels must match `primary_product` values in
`ProductAssociations.csv`**, after normalization (lowercased, `-` and `_` become spaces). A
model that emits `Orange_Fruit` won't match a CSV row for `orange`. Either rename the CSV rows
or post-process the labels. Detections will look fine in the video overlay while no ad ever
fires — that mismatch is the single most common cause.

Keep the original model directory in place until the new one works: `make check_models` (part of
`make up`) requires `yolo11s/INT8/yolo11s.xml` and `.bin` to exist, so deleting the default model
blocks startup even if your replacement is fine. The check can't tell whether the new model works.

## Add or change predefined ads

Predefined ads are seeded into Qdrant (the `ase-qdrant` container) by the web UI at every startup
from `web-ui/ProductAssociations.csv`. There is no persistent state to migrate — `make down`
removes the Qdrant volumes and the next `make up` re-seeds.

1. Put a **JPEG** in `web-ui/pre-defined-ads/`. Existing files there are the naming precedent:
   `apple_orange.jpg`, `oven_microwave.jpg`.
2. Add or edit a row in `web-ui/ProductAssociations.csv`.
3. `make up`.

CSV columns:

| Column | Meaning |
|---|---|
| `primary_product` | Detected label this row responds to. Must match a model class name after normalization |
| `price` | Numeric price, rendered in the overlay |
| `unit` | Price unit, e.g. `/Kg` |
| `weight` | Quantity basis |
| `cross_sell_discount` | Discount text, e.g. `30%` |
| `promo_details` | Promo banner text |
| `slogan` | Slogan text |
| `associated_cross_sell` | The cross-sold product |
| `dynamic_ad_prompt` | Prompt used when generating an ad with SDXL-Turbo |
| `pre_defined_ad_image` | Filename in `pre-defined-ads/` (JPEG). **Leave empty to force dynamic generation** for this row |
| `pre_defined_ad_video` | Optional filename in `pre-defined-ads/` of a ready-made clip for MCP `trigger_video_ad` (see [Enable AI video ads](#enable-ai-video-ads)). Camera-driven ads never use it |

Multiple rows may share a `primary_product` — they become variants, and the selection logic
rotates between them to avoid repetition. That is the cheapest way to add variety. The shipped CSV
has about 100 rows over 50 products, but only a handful name an image.

A row with an empty `pre_defined_ad_image` always generates dynamically, which is slower but
needs no artwork. Rows with an image still fall back to generation when the semantic match
scores below `ASE_QDRANT_SCORE_MIN_THRESHOLD`.

Matching is semantic rather than by filename. At seeding the stored **description** is
`"<primary_product> and <associated_cross_sell>"`, and the lookup query is built the same way, so
those two columns — not the prompt or the image — decide which ad a row retrieves. Seeding adds
entries without ids on every web-ui start; `make down && make up` gives a clean set.

## Enable AI video ads

Video ads are produced only by the MCP `trigger_video_ad` tool (never by the camera flow). They
use a predefined clip when the item has one, otherwise the LTX-Video model generates one.

1. Get the model: `make download_models` exports it to `aig/models/ltx_video_ov/int8` (long and
   large; skipped when `CI` is set or `SKIP_LTX_VIDEO_EXPORT=1`; force with
   `SKIP_LTX_VIDEO_EXPORT=0`). Review the LTX-Video license first. It is not needed for `make up`.
2. Check `.env`: `AIG_VIDEO_MODEL_PATH` (default `/opt/models/ltx_video_ov/int8`; unset disables
   generation) and `AIG_VIDEO_INFERENCE_DEVICE` (`GPU` or `CPU`). Budget ~8 GB extra GPU/shared
   memory with the default `AIG_VIDEO_PRECISION=f16` (~11 GB with `f32`); 32 GB RAM recommended.
3. Optionally `AIG_PRELOAD_VIDEO_MODEL=true` (with `AIG_KEEP_MODEL_IN_MEMORY=true`) to load it at
   start instead of on the first video request.
4. Keep `VIDEO_AD_DISPLAY_SECONDS` equal to `AIG_VIDEO_LOOP_SECONDS` (both `3`); change
   `AIG_VIDEO_NUM_FRAMES` (must be 8k+1) / `AIG_VIDEO_FRAME_RATE` together with them so the motion
   isn't stretched.
5. `make up`.

Generation takes about 30 s on an Intel iGPU in `f16` (minutes in `f32`). The resolution default
is 704x480 (divisible by 32). To skip generation for a product, add a `.mp4`, `.webp` or `.gif`
to `web-ui/pre-defined-ads/` and name it in the row's `pre_defined_ad_video`; it must be no longer
than `VIDEO_AD_DISPLAY_SECONDS` + 0.5 s or it is skipped with a warning at startup.

## Drive the display from an agent (MCP)

The web UI runs an MCP server reachable through nginx at `https://<HOST_IP>:5000/mcp` (Streamable
HTTP, self-signed certificate). Tools: `describe`, `get_current_ad`, `get_catalog`,
`select_dynamic_ad(weather, demand, age_mix, daypart, display_seconds)`,
`trigger_ad(item, display_seconds, promo_text, slogan)`, `trigger_video_ad(item | description)`
and `clear_ad`. Agent ads override the camera-driven flow (default 60 s for images) until they
expire or `clear_ad` runs. `select_dynamic_ad` maps context to a product through
`web-ui/context_rules.json` (`rules` with `weather` / `demand` / `age_mix` / `daypart` → `product`,
best match wins, else `default_product`); every product named there must exist in the CSV.
Edit the JSON and `make up` to change the rules. Setup and a Python client are in
`docs/user-guide/how-to-guides/use-mcp-agent-tools.md`; failures in `troubleshooting.md`
§ MCP and video ads.

## Tune ad behavior

All in `.env`, all requiring `make up`:

| Goal | Change |
|---|---|
| Ads change too fast / too slow | `TIME_TO_DISPLAY_AD_SECONDS` (default 5) — a minimum, not a period |
| Spurious detections trigger ads | Raise `OBJECT_RECENCY_FRAME_COUNT` (5) or `OBJECT_CONFIDENCE_THRESHOLD` (0.5) |
| Products detected but no ads | Lower those same two |
| Predefined ads never chosen | **Lower** `ASE_QDRANT_SCORE_MIN_THRESHOLD` (0.8) in small steps, e.g. 0.7 |
| Wrong predefined ads chosen | **Raise** it, or improve the `primary_product` / `associated_cross_sell` text |
| Generation too slow | `AIG_KEEP_MODEL_IN_MEMORY=true`; check `AIG_INFERENCE_DEVICE` is a device the host has |
| Memory too high | `AIG_KEEP_MODEL_IN_MEMORY=false` — roughly 10 GB down to 2 GB, at a latency cost |
| Video clips too slow to generate | Lower `AIG_VIDEO_NUM_FRAMES` / `AIG_VIDEO_NUM_INFERENCE_STEPS`, keep `AIG_VIDEO_PRECISION=f16` |
| UI reachable from other machines | `HOST_IP` = the host's real IPv4, then `make up` |

`OBJECT_RECENCY_FRAME_COUNT` is subtler than it looks: a label must appear in at least that many
messages within a rolling window of **twice** that value. Raising it makes detection both
stricter and slower to react.

## Benchmark

Not part of deployment. `make update-submodules` fetches the `performance-tools` submodule
(it isn't checked out by default), then `make benchmark-pid | benchmark-aig | benchmark-web-ui |
benchmark-qdrant | benchmark-metrics | benchmark-e2e | benchmark-all` run the stack with
`BENCHMARK_MODE=true`, wait `BENCHMARK_WARMUP_SECONDS` (300) and write results to
`results/<timestamp>/`; `make consolidate-benchmarks` merges them. They **restart the stack** and,
unless `SKIP_BENCHMARK_DEVICE_CONFIG=true`, rewrite the detection `device` in
`configs/pid/config.json` (`PID_DEVICE`, default `CPU`) and `AIG_INFERENCE_DEVICE` in `.env`
(`AIG_DEVICE`, default `GPU`) — re-check both afterwards. Set `COLLECT_METRICS=false` to skip host
metrics. Full guide: `docs/user-guide/how-to-guides/benchmarking.md`.
