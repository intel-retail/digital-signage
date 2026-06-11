# Change Inference Device (CPU/GPU/NPU)

## PID

Update `pid/config.json`:

```json
"device": "CPU"
```

Supported values: `CPU`, `GPU`, `NPU`.

## AIG

Update `.env`:

```env
AIG_MODEL_DEVICE=GPU
```

Supported values: `CPU`, `GPU`.

## Apply Changes

```bash
make down
make up
```
