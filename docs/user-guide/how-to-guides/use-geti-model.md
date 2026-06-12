# Use Intel® Geti™ Exported Model

You can replace the default YOLO11s model in PID with a custom object-detection model trained and exported from Intel® Geti™.

## Prerequisites

1. Refer to the [official Geti documentation for offline installation instructions](https://docs.geti.intel.com/docs/user-guide/getting-started/installation/using-geti-installer). DL Streamer Pipeline Server uses Geti SDK version 2.13.1; install the same or a compatible version as per the [compatibility matrix](https://docs.geti.intel.com/docs/user-guide/geti-fundamentals/deployments/?_highlight=compatible#compatibility).
2. Follow the [Geti Tutorials](https://docs.geti.intel.com/docs/user-guide/getting-started/use-geti/tutorials) for creating projects, labeling data, training models, and exporting results.
3. Confirm your project uses a YOLO or other supported object detection architecture. See [Supported Models in Geti](https://docs.geti.intel.com/docs/user-guide/getting-started/use-geti/supported-models).
4. Follow the [Model Download Instructions](https://docs.geti.intel.com/docs/user-guide/geti-fundamentals/deployments/#lets-download-the-model) to export your model as OpenVINO™ IR files (`.xml`/`.bin`).

## Steps

1. **Export and place the model**: Extract the downloaded Geti deployment `.zip` package and place the extracted folder at:

   ```text
   ./configs/pid/models/object_detection/geti-sdk-deployment/deployment/Detection/model
   ```

2. **Update the model path** in `configs/pid/config.json`:

   ```json
   "parameters": {
      "detection-properties": {
         "model": "/home/pipeline-server/object_detection/geti-sdk-deployment/deployment/Detection/model/<YOUR_MODEL_NAME>.xml",
         "device": "CPU"
      }
   }
   ```

   Replace `<YOUR_MODEL_NAME>` with the actual filename (without extension) of your exported model.

3. **Deploy** the application:

   ```bash
   make up
   ```

4. **Verify** the model loads successfully:

   ```bash
   docker logs -f <pid_container_name>
   ```
