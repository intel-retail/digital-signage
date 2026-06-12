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

Set the `AIG_MODEL_DEVICE` variable in `.env`:

```env
AIG_MODEL_DEVICE=GPU
```

**Available options:** `CPU`, `GPU`

## Apply Changes

After updating the device configuration, redeploy the application:

```bash
make down
make up
```
