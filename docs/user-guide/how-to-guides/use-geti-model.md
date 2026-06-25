# Use Intel® Geti™ Exported Model

You can replace the default YOLO11s model in the Product Identification (PID) service with a
custom object-detection model trained and exported from Intel® Geti™.

## Prerequisites

1. Refer to the [official Geti documentation for installation instructions](https://docs.geti.intel.com/docs/user-guide/getting-started/installation/installation-guide).
2. Follow the [Geti Tutorials](https://docs.geti.intel.com/docs/user-guide/quick-start/training-your-first-model) for creating projects, labeling data, training models, and exporting results.
3. Confirm your project uses a YOLO or other supported object detection architecture. See [Supported Models in Geti](https://docs.geti.intel.com/docs/user-guide/learn-geti/computer-vision-tasks/ai-fundamentals-tasks#supported-deep-learning-models).
4. Follow the [Geti Export Instructions](https://docs.geti.intel.com/docs/user-guide/quick-start/training-your-first-model?_highlight=export&_highlight=model#step-7-export-your-trained-model) to export your model as OpenVINO™ IR files (`.xml`/`.bin`).

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
   make down
   make up
   ```

4. **Verify** the model loads successfully:

   ```bash
   docker logs -f <pid_container_name>
   ```
