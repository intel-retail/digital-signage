# Configure RTSP Camera Input

1. Obtain your RTSP URI.
2. Update `pid/config.json` pipeline to use `rtspsrc` with your camera URI.
3. Set `RTSP_CAMERA_IP` and related values in `.env`.
4. Redeploy:

```bash
make down
make up
```
