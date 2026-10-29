# Change Inference Device (CPU/GPU/NPU)

By default, PID performs inference on `CPU` and AIG uses `GPU`. You can customize the target device for each component independently.

| Component | `CPU` | `GPU` | `NPU` |
|---|---|---|---|
| PID (object detection) | Yes | Yes | Yes |
| AIG image ads (SDXL-Turbo) | Yes | Yes | Yes (experimental) |
| AIG video ads (LTX-Video) | Yes | Yes | No, falls back to `GPU` |

## PID (Product Identification)

Update the `device` parameter in `configs/pid/config.json`:

```json
"parameters": {
   "detection-properties": {
      "model": "<model_path>",
      "device": "CPU"
   }
}
```

**Available options:** `CPU`, `GPU`, `NPU`

## AIG (Advertise Image Generator)

Set the `AIG_INFERENCE_DEVICE` variable in `.env`:

```text
AIG_INFERENCE_DEVICE=GPU
```

**Available options:** `CPU`, `GPU`, `NPU` (experimental)

### Running AIG on the NPU (experimental)

The image model (SDXL-Turbo, INT8) can run on the Intel NPU. This applies to image ads only; see
[Video](#aig-video-text2videopipeline-used-by-trigger_video_ad) for the video model.

#### Prerequisites

- An Intel NPU (for example Core Ultra / Panther Lake) with the kernel driver loaded, so that the
  host exposes `/dev/accel/accel0`:

  ```bash
  ls -l /dev/accel/
  ```

- No host user-mode NPU driver is needed. The `aig-server` image bundles the NPU driver
  (`linux-npu-driver` v1.38.0) and Level Zero loader, so rebuild the image after pulling this change.
- `make up` detects `/dev/accel` and passes it to the container through `ACCEL_MOUNT_PATH`. If you run
  `docker compose` directly, export it first (and `DRI_MOUNT_PATH=/dev/dri` for the GPU):

  ```bash
  export ACCEL_MOUNT_PATH=/dev/accel DRI_MOUNT_PATH=/dev/dri
  ```

- The device node belongs to the `render` group. The compose file already adds the render group IDs
  of Ubuntu 20.04 to 26.04 hosts (`109`, `110`, `992`, `990`) to `aig-server`. On other hosts, add the
  value of `stat -c %g /dev/accel/accel0` to `group_add`.

#### Configure

```text
AIG_INFERENCE_DEVICE=NPU
AIG_KEEP_MODEL_IN_MEMORY=true
```

Then redeploy (see [Apply Changes](#apply-changes)). `AIG_INFERENCE_DEVICE` is case-insensitive.

#### What to expect

- **Static shapes.** The NPU cannot run dynamic shapes, so the pipeline is reshaped to
  `AIG_IMG_WIDTH_DEFAULT` x `AIG_IMG_HEIGHT_DEFAULT` (448 x 448 by default) and compiled for that size.
- **First start is slow.** The first compile takes about 3 minutes on Panther Lake. Compiled blobs are
  cached in `/opt/npu_cache`, a bind mount of the host directory `AIG_NPU_CACHE_HOST_DIR` (default
  `./aig/npu_cache`). It is disk-backed, not the memory-backed `vol_pipeline_root` volume, and
  `make down` does not delete it, so the cache survives restarts. With a warm cache the model loads in
  under 20 seconds.
- **Cache directory.** `make up` creates the host directory if it is missing. The container runs as
  `UID` from `.env` (default 1000), so the directory must be writable by that user. If you run
  `docker compose` directly, create it first (`mkdir -p aig/npu_cache`), otherwise Docker creates it as
  root and the cache cannot be written. To keep the cache elsewhere, set `AIG_NPU_CACHE_HOST_DIR` in
  `.env`.
- **Cache size.** The cache is about 7 GB for one image size, and every new image size adds another
  set of blobs. Make sure the host disk has enough free space, and clear the directory if you change the
  image size and no longer need the old blobs.
- **Speed.** Once loaded, an image takes about 1 second on Panther Lake (compared with about
  2.6 seconds on the integrated GPU in the same system).
- **Keep the model in memory.** With `AIG_KEEP_MODEL_IN_MEMORY=false` the model is unloaded after each
  request, so every request pays the load time again. Use `true` on the NPU.
- **Request device.** The model is only reused when a request asks for the configured device. A request
  for another device builds a temporary pipeline on that device, which on the NPU repeats the load.
- **Load failures.** If the NPU model fails to load, requests return `503` (`Device NPU unavailable`) and
  the load is not retried for 5 minutes, to avoid repeating a failed multi-minute compile. Restart
  `aig-server` to retry sooner.

#### Troubleshooting

| Symptom | Check |
|---|---|
| `Device NPU is not available` in the `aig-server` log | `/dev/accel/accel0` is missing on the host or not mounted. Run `docker exec aig-server ls -l /dev/accel` and check `ACCEL_MOUNT_PATH`. |
| The NPU is not listed by OpenVINO | `ZE_ENABLE_ALT_DRIVERS` must be `libze_intel_npu.so` (the v1.38 driver library name). `libze_intel_vpu.so` hides the NPU. |
| Permission denied on `/dev/accel/accel0` | The container user is not in the device's group. Add the group ID to `group_add`. |
| Very long first request after a restart | The compile cache is empty, the image size changed, or `aig/npu_cache` is not writable by `UID` (check `ls -ld aig/npu_cache`). |
| `503` on every image request | Check the `aig-server` log for `Failed to load model on NPU`, fix the cause and restart `aig-server`. |

To confirm which device is in use, check the log for `EXECUTION_DEVICES: NPU` after
`Loading Text2Image model on device: NPU`:

```bash
docker logs aig-server 2>&1 | grep -E "Loading Text2Image|Model loaded|EXECUTION_DEVICES|NPU:"
```

## AIG Video (Text2VideoPipeline, used by `trigger_video_ad`)

The video model is configured independently of the image model above. Set the
`AIG_VIDEO_INFERENCE_DEVICE` variable in `.env`:

```text
AIG_VIDEO_INFERENCE_DEVICE=GPU
```

**Available options:** `CPU`, `GPU`. `NPU` is not supported for video: the LTX-Video model fails to
compile on the NPU, so an `NPU` value falls back to `GPU`. Keep this in sync between the `web-ui` and
`aig-server` containers (both read it from the same `.env` variable) — a mismatch
forces the AIG server to rebuild the video pipeline from disk on every request
instead of reusing the preloaded model.

### Video precision and preloading

On `GPU` the video model runs in `f16` by default, which is about 5-6x faster than `f32`
(roughly 30 s instead of 3 minutes per video on an Intel Core Ultra X7 358H iGPU) with
comparable output quality. Set `AIG_VIDEO_PRECISION=f32` to run in full precision instead.

By default the video model loads on the first video request. Set
`AIG_PRELOAD_VIDEO_MODEL=true` (together with `AIG_KEEP_MODEL_IN_MEMORY=true`) to load it
when `aig-server` starts.

## Apply Changes

After updating the device configuration, redeploy the application:

```bash
make down
make up
```
