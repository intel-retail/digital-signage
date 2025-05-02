# Product Identification (PID)

| [Project Readme.md](../../README.md) | [CAXSelling Readme.md](../README.md) |

It describes the functionalities and package organization of the Product Identification (PID). It implements the video pipelines to detect and classify the items under analysis. It communicates the detected items and involved sequences based on the provided classes in the model.

Content:

- [Intel Hardware Drivers](#intel-hardware-drivers)
- [Scripts](#initialization-scipt)
- [Conceptual Approach and Container Initialization](#conceptual-approach-and-container-initialization)
- [Testing EVAM](#testing-evam)
- [How to Download YOLOv11 and Export it to OpenVINO format](#how-to-download-yolov11-and-export-it-to-openvino-format)

## Intel Hardware Drivers

It is critical to set up and install proper drivers to ensure the full benefits of the hardware on top of which the containers run.

### iGPU/dGPU Drivers

You can check the driver version and related information using the clinfo utility. If not installed, you can install it by running the following command:

```bash
sudo apt install clinfo (if not installed)
clinfo | fgrep "Driver Version"
```

You can check the last available release and installation procedure from the [compute-runtime Github repository](https://github.com/intel/compute-runtime/releases/). Supported Operating Systems could change over versions. For example, the version [25.13.33276.16](https://github.com/intel/compute-runtime/releases/tag/25.13.33276.16) is available for Ubuntu 22.04/24.04.

### NPU Drivers

You can check the driver version and related information for NPU drivers from the [linux-npu-driver repository](https://github.com/intel/linux-npu-driver/). Before installing any new driver, you need to uninstall the older existing ones.

```bash
sudo dpkg --purge --force-remove-reinstreq intel-driver-compiler-npu intel-fw-npu intel-level-zero-npu
```

Different Operating Systems (OS) are supported over the driver versions. You can check the available versions [here](https://github.com/intel/linux-npu-driver/releases/) and decide on the best suited for your hardware and OS. For example, the [version 1.16.0](https://github.com/intel/linux-npu-driver/releases/tag/v1.16.0) for Linux is available for Ubuntu 22.04 and 24.04 and drivers were validated for [Meteor Lake](https://ark.intel.com/content/www/us/en/ark/products/codename/90353/products-formerly-meteor-lake.html), Arrow Lake [https://www.intel.com/content/www/us/en/ark/products/codename/225837/products-formerly-arrow-lake.html], and Lunar Lake [https://ark.intel.com/content/www/us/en/ark/products/codename/213792/products-formerly-lunar-lake.html].

**Important**: Read carefully [instructions](https://github.com/intel/linux-npu-driver/releases/tag/v1.16.0) for user access to the device when you need to use the accelerator in non-root users.

Check the installed version by dmesg as follows:

```bash
sudo dmesg | fgrep -i "vpu"
```

You will see an output with a format similar to "YYYYMMDD*MTL..." where YYYY is the year, MM the month (1-12) and DD the release day.

**Tip:** Remember to review the DETECTION_DEVICE and CLASSIFICATION_DEVICE properties in the [docker-compose.yaml](./docker-compose.yml) file, and update them accordingly based on the host hardware. A technical article for your reference of [Ultralytics YOLO and Intel AI PC](https://www.ultralytics.com/blog/running-ultralytics-yolo-models-on-intels-ai-pc-with-openvino) from Yolo Vision 2024 (YV2024).

## Initialization Scipt

B the following:
Detect installation [option to stop container and remove]
install / venv etc
run the container (MQTT and EVAM)
Ready to serve (Microservices)

Remotion /...

## Conceptual Approach and Container Initialization

The docker compose file starts a MQTT broker and the Deep Learning Streamer Pipeline Server [See Microservices at EdgeAI Libraries](https://github.com/open-edge-platform/edge-ai-libraries). DL Streamer Pipeline Servers is also known as Edge Video Analytics Microservoce (EVAM).

On the one hand, EVAM allows it to define a video analytics pipeline through an Application Programming Interface (API), providing the corresponding models and defining the output communication mode. On the other hand, in this scenario, it uses an MQTT broker to communicate the object detection and classification activities.

The folder organization is as follows:

```bash
├ certificates
│   └─ model_registry
│   └─ ssl_server
├ models # Downloaded Models 
│   └─ mr_models #(from Model Registry Microservice)
│   └─ yolov11 #Yolov11 (Ultralytics) exported in OpenVINO format
├ mosquitto 
│   └─ conf
```

1. Change your current directory to "./caxselling/pid/models/yolov11"
1. Initializes the containers in detached mode
    > docker compose up -d
1. Checks the container status
    > docker ps

    You should see two containers:
    1. intel/edge-video-analytics-microservice
    1. eclipse-mosquito

## Testing EVAM

1. Testing the API by submitting a new pipeline (It requires curl installed). You will see a pipeline ID as result of the following command.

    ```bash
    curl localhost:8080/pipelines/user_defined_pipelines/pallet_defect_detection -X POST -H 'Content-Type: application/json' -d '{
        "source": {
            "uri": "file:///home/pipeline-server/resources/videos/classroom.avi",
            "type": "uri"
        },
        "destination": {
            "metadata": {
                "type": "file",
                "path": "/tmp/results.jsonl",
                "format": "json-lines"
            },
            "frame": {
                "type": "rtsp",
                "path": "classroom-video-streaming"
            }
        },
        "parameters": {
            "detection-properties": {
                "model": "/home/pipeline-server/yolo_models/yolo11s/FP32/yolo11s.xml",
                "device": "CPU"
            }
        }
    }'
    ```

    - We feed the pipeline with the classroom.avi video
    - Results are incorporated in /tmp/results.jsonl (in the container)
    - It will use the FP32 model version and CPU for inferencing
    - The rtsp output is derived to classroom-video-streaming so consume it from *rtsp://localhost:8554/classroom-video-streaming*

1. You can check the pipeline status
    > curl --location -X GET http://localhost:8080/pipelines/status

    Cgeck the inference outputs from the file:
    > tail -f /tmp/results.jsonl

1. You can visualize the pipeline output using VLC Viewer
    - Open VLC Viewer
    - Go to "Media > Open Network Stream"
    - Indicate the value **rtsp://localhost:8554/classroom-video-streaming** for the *Network URL* field
    - Press "Play"

1. Testing the pipeline producing the output over MQTT

    ```bash
    curl localhost:8080/pipelines/user_defined_pipelines/pallet_defect_detection -X POST -H 'Content-Type: application/json' -d '{
        "source": {
            "uri": "file:///home/pipeline-server/resources/videos/classroom.avi",
            "type": "uri"
        },
        "destination": {
            "metadata": {
                "type": "mqtt",
                "host": "mqtt:1883",
                "publish_frame": false,
                "topic": "test_topic",
                "mqtt-client-id": "gva-meta-publish"
            },
            "frame": {
                "type": "rtsp",
                "path": "classroom-video-streaming"
            }
        },
        "parameters": {
            "detection-properties": {
                "model": "/home/pipeline-server/yolo_models/yolo11s/FP32/yolo11s.xml",
                "device": "CPU"
            }
        }
    }'
    ```

    Repeat previous steps for visualizing the output through VLC.

1. If you want to see the MQTT output (inference) using a mosquitto client.
    -Install a client locally
        > sudo apt install mosquitto-clients
    - Listen the broker for the indicated topic
        > mosquitto_sub --topic test_topic -p 1883 -h 127.0.0.1

Additional detail about how to configure sources and destinations are available [here](https://github.com/dlstreamer/pipeline-server/blob/main/docs/customizing_pipeline_requests.md#metadata-destination).

## How to Download YOLOv11 and Export it to OpenVINO format

The models to be used by EVAM should be available and informed to it when the video pipeline is specified. This section describes the general steps to download the [Ultralytics Yolo 11 model](https://docs.ultralytics.com/models/yolo11/#can-yolo11-be-deployed-on-edge-devices) as an example; however, the procedure could be reused for any similar model required.

Once you have the model doenloaded and converted, you will see a folder organization like the following one:

1. Change your current directory to "./caxselling/pid/models/yolov11"
1. Create a Python Virtual Environment (if neither)
    > python3 -m venv .env
1. Activate the virtual environment
    > source .env/bin/activate
1. Update pip
    > pip install --upgrade pip
1. Install Python requirements indicated in the corresponding file
    > pip install -r requirements.txt
1. Run the [download_yolov11.py](./models/yolov11/download_yolov11.py) file to download the model and convert it to the OpenVINO format.
    > python3 download_yolov11.py

You should see the following folders and files:

```bash
├ yolov11
│   └─ FP16 
│       └─> yolo11s.bin # Model Weights 
│       └─> yolo11s.xml # Model Metadata
│   └─ FP32
│       └─> yolo11s.bin # Model Weights 
│       └─> yolo11s.xml # Model Metadata
```

[Additional information](https://dlstreamer.github.io/dev_guide/yolo_models.html#yolov8-yolov9-yolov10-yolo11) for multiple Yolo Versions is available at the DLStreamer Github repository.
