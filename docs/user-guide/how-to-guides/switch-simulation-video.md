# Switch Simulation Video

By default, the Product Identification (PID) service uses a bundled simulation video for
product detection. You can replace it with your own video file.

## Prerequisites

- The input video file must be in **`.avi` format**.

## Steps

1. **Copy your video** to the `configs/pid/videos/` directory:

   ```bash
   cp /path/to/your/video.avi configs/pid/videos/
   ```

2. **Update the pipeline configuration** in `configs/pid/config.json`. Locate the `pipeline` string and replace `<VIDEO_FILE_NAME>` with your file name (without the `.avi` extension):

   ```json
   "multifilesrc loop=TRUE location=/home/pipeline-server/resources/externalvideos/<VIDEO_FILE_NAME>.avi name=source ! h264parse ! decodebin ! videoconvert ! video/x-raw,format=BGR ! gvadetect name=detection ! queue ! gvawatermark displ-cfg=\"font-scale=1.5,thickness=3,color-idx=2,font-type=plain\" ! gvafpscounter ! appsink name=destination"
   ```

   > **Note:** To use different bounding box colors with `gvawatermark`, refer to the [GVA Watermark element documentation](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/dlstreamer/elements/gvawatermark.html).

3. **Redeploy** the application:

   ```bash
   make down
   make up
   ```
