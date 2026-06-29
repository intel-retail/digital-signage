# Configure RTSP Camera Input

Instead of a simulation video, the Product Identification (PID) service can ingest a live RTSP
camera stream for real-time product detection.

## Prerequisites

- Obtain the RTSP URI from your camera software. You can test the URI with, for example, the VLC media player before configuring it here.
- For more on the RTSP protocol, see [RTSP — Wikipedia](https://en.wikipedia.org/wiki/Real_Time_Streaming_Protocol).

## Steps

1. **Update the pipeline** in `configs/pid/config.json`. Replace the existing `multifilesrc` pipeline string with an `rtspsrc` pipeline:

   ```json
   "pipeline": "rtspsrc location=\"rtsp://<USERNAME>:<PASSWORD>@<RTSP_CAMERA_IP>:<PORT>/<FEED>\" latency=0 drop-on-latency=true protocols=udp ! application/x-rtp,media=video ! rtph264depay ! video/x-h264,stream-format=byte-stream ! decodebin3 ! gvadetect name=detection ! gvawatermark displ-cfg=\"font-scale=1.5,thickness=3,color-idx=2,font-type=plain\" ! gvafpscounter ! appsink name=destination"
   ```

   Replace `<USERNAME>`, `<PASSWORD>`, `<RTSP_CAMERA_IP>`, `<PORT>`, and `<FEED>` with your camera’s values.

   > **Note:** To use different bounding box colors with `gvawatermark`, refer to the [GVA Watermark element documentation](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-libraries/dlstreamer/elements/gvawatermark.html).

2. **Set the camera IP** in `.env`:

   ```text
   RTSP_CAMERA_IP=<RTSP_CAMERA_IP>
   ```

3. **Redeploy** the application:

   ```bash
   make down
   make up
   ```

For further guidance on RTSP with DL Streamer Pipeline Server, see the [DL Streamer RTSP guide](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-libraries/dlstreamer-pipeline-server/advanced-guide/detailed_usage/camera/rtsp.html).
