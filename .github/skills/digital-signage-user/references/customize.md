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
- [Tune ad behavior](#tune-ad-behavior)

## Where the knobs live

Newcomers reliably look in the wrong place, so start here:

| To change | Edit | Not |
|---|---|---|
| Video source, detection model, detection device | `configs/pid/config.json` | `.env` |
| Generation device, model path, overlay defaults | `.env` | `config.json` |
| Which products map to which ads | `web-ui/ProductAssociations.csv` | code |
| Ad images | `web-ui/pre-defined-ads/` + the CSV | the API directly |
| Detection sensitivity, ad cadence | `.env` | `config.json` |

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

Raise `latency=` if the stream stutters; lower it for responsiveness on a reliable network.

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

**Generation (AIG / SDXL-Turbo)** — `AIG_MODEL_DEVICE` in `.env`, default `GPU`.

Both require the corresponding host device to exist. `GPU` needs a populated `/dev/dri`; `NPU`
needs `/dev/accel`. The Makefile probes for these when it is parsed and substitutes `/dev/null`
if absent, so a missing device produces a container that starts normally and then fails at
inference — check `docker logs` rather than assuming the mount worked.

For NPU access you may need the udev rule in `configs/pid/scripts/cfgNPUAccess.sh`, which grants
access to `/dev/accel/accel0`. It is not run by `make up`; run it on the host once.

One subtlety on the generation side: the web UI hardcodes `"device": "GPU"` in its dynamic-ad
request. Setting `AIG_MODEL_DEVICE=CPU` without changing the UI means every request sees a
device mismatch and builds a fresh pipeline instead of reusing the preloaded one — technically
correct, dramatically slower. Keep them aligned, or change the UI (a code change — use
`digital-signage-dev`).

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

Keep the original model directory in place until the new one works; `make check_models` only
verifies the directory is non-empty, so it won't catch a broken swap.

## Add or change predefined ads

Predefined ads are seeded into ChromaDB by the web UI at every startup from
`web-ui/ProductAssociations.csv`. There is no persistent state to migrate — `make down` removes
the volume and the next `make up` re-seeds.

1. Put a **JPEG** in `web-ui/pre-defined-ads/`. Existing files there are the naming precedent:
   `apple_banana.jpg`, `oven_microwave.jpg`.
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
| `pre_defined_ad_image` | Filename in `pre-defined-ads/`. **Leave empty to force dynamic generation** for this row |

Multiple rows may share a `primary_product` — they become variants, and the selection logic
rotates between them to avoid repetition. That is the cheapest way to add variety.

A row with an empty `pre_defined_ad_image` always generates dynamically, which is slower but
needs no artwork. Rows with an image still fall back to generation when the semantic match
misses the `ASE_DISTANCE_MAX_THRESHOLD` cutoff.

Since matching is semantic rather than by filename, the ad's stored **description** drives
retrieval. The seeding path derives it from the CSV row, so a row whose text doesn't describe
the image well retrieves poorly even when the image is right.

## Tune ad behavior

All in `.env`, all requiring `make up`:

| Goal | Change |
|---|---|
| Ads change too fast / too slow | `TIME_TO_DISPLAY_AD_SECONDS` (default 5) — a minimum, not a period |
| Spurious detections trigger ads | Raise `OBJECT_RECENCY_FRAME_COUNT` (5) or `OBJECT_CONFIDENCE_THRESHOLD` (0.5) |
| Products detected but no ads | Lower those same two |
| Predefined ads never chosen | Raise `ASE_DISTANCE_MAX_THRESHOLD` (0.2) toward 0.4–0.5 |
| Wrong predefined ads chosen | Lower it, or improve the CSV descriptions |
| Generation too slow | `AIG_KEEP_MODEL_IN_MEMORY=true`, and align `AIG_MODEL_DEVICE` with the UI's `GPU` |
| Memory too high | `AIG_KEEP_MODEL_IN_MEMORY=false` — roughly 10 GB down to 2 GB, at a latency cost |

`OBJECT_RECENCY_FRAME_COUNT` is subtler than it looks: a label must appear in at least that many
messages within a rolling window of **twice** that value. Raising it makes detection both
stricter and slower to react.
