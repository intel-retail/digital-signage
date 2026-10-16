# Change Inference Device (CPU/GPU/NPU)

By default, PID performs inference on `CPU` and AIG uses `GPU`. You can customize the target device for each component independently.

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

**Available options:** `CPU`, `GPU`

## AIG Video (Text2VideoPipeline, used by `trigger_video_ad`)

The video model is configured independently of the image model above. Set the
`AIG_VIDEO_INFERENCE_DEVICE` variable in `.env`:

```text
AIG_VIDEO_INFERENCE_DEVICE=GPU
```

**Available options:** `CPU`, `GPU`. Keep this in sync between the `web-ui` and
`aig-server` containers (both read it from the same `.env` variable) — a mismatch
forces the AIG server to rebuild the video pipeline from disk on every request
instead of reusing the preloaded model.

## Apply Changes

After updating the device configuration, redeploy the application:

```bash
make down
make up
```
