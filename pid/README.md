# Product Identification (PID)

| [Project Readme.md](../../README.md) | [CAXSelling Readme.md](../README.md) |

It describes the functionalities and package organization of the Product Identification (PID). It implements the video pipelines to detect and classify the items under analysis. It communicates the detected items and involved sequences based on the provided classes in the model.

Content:

- [Conceptual Approach and Container Initialization](#conceptual-approach-and-container-initialization)
- [Intel Hardware Drivers](#intel-hardware-drivers)
- [Management Scripts](#management-scripts)
- [Testing DLStreamer Pipeline Server](#testing-dlstreamer-pipeline-server)
- [How to Download YOLOv11 and Export it to OpenVINO format](#how-to-download-yolov11-and-export-it-to-openvino-format)

## Conceptual Approach and Container Initialization

The docker compose file starts a MQTT broker and the Deep Learning Streamer Pipeline Server [See Microservices at EdgeAI Libraries](https://github.com/open-edge-platform/edge-ai-libraries). DL Streamer Pipeline Servers is also known as Edge Video Analytics Microservoce (EVAM).

On the one hand, EVAM allows it to define a video analytics pipeline through an Application Programming Interface (API), providing the corresponding models and defining the output communication mode. On the other hand, in this scenario, it uses an MQTT broker to communicate the object detection and classification activities.

The folder organization is as follows:

```bash
├ certificates
│   └─ model_registry
│   └─ ssl_server
├ models # Downloaded Models 
│   └─ mr_models # (from Model Registry Microservice)
│   └─ yolov11 # Yolov11 (Ultralytics) exported in OpenVINO format
├ mosquitto 
│   └─ conf # MQTT Broker Configuration
├ resources 
│   └─ videos # The directory is mounted in the container to incorporate external videos or multimedia files
├ scripts # A set of scripts to support the PID management.
```

1. Change your current directory to "./caxselling/pid/"
1. Initializes the containers in detached mode

    ```bash
    docker compose up -d
    ```

1. Checks the container status

    ```bash
    docker ps
    ```

    Expected output:

    ```bash
    CONTAINER ID   IMAGE                                    COMMAND                  CREATED             STATUS             PORTS                                                                                      NAMES
    612df0ed074f   intel/dlstreamer-pipeline-server:3.0.0   "./run.sh"               About an hour ago   Up About an hour   0.0.0.0:8080->8080/tcp, [::]:8080->8080/tcp, 0.0.0.0:8554->8554/tcp, [::]:8554->8554/tcp   dlstreamer-pipeline-server
    94c6537bc9bf   eclipse-mosquitto                        "/docker-entrypoint.…"   About an hour ago   Up About an hour   0.0.0.0:1883->1883/tcp, [::]:1883->1883/tcp                                                mqtt_broker
    ```

The [management scripts](#management-scripts) make the microservice management easier to use as described below.

## Intel Hardware Drivers

It is critical to set up and install proper drivers to ensure the full benefits of the hardware on top of which the containers run.

### iGPU/dGPU Drivers

You can check the driver version and related information using the clinfo utility. If not installed, you can install it by running the following command:

```bash
sudo apt install clinfo (if not installed)
clinfo | fgrep "Driver Version"
```

Expected Outcome:

```bash
  Driver Version                                  25.13.33276.16
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

You will see an output similar to the following:

```bash
   [   93.255911] intel_vpu 0000:00:0b.0: [drm] Firmware: intel/vpu/vpu_37xx_v0.0.bin, version: 20250306*MTL_CLIENT_SILICON-release*1130*ci_tag_ud202512_vpu_rc_20250306_1130*5064b5debc3
```

The output will have a format similar to "YYYYMMDD*MTL..." where YYYY is the year, MM is the month (1-12), and DD is the release day. If the previous command does not show result, it is possible that the driver was not installed successfully or the current Kernel is not supported.

> **Tip:** Ubuntu 22.04/24.04 running on WSL2 does not have NPU support (v1.16.0); however, this could change with new versions.

Please check the accelarator availability under the /dev folder before using NPU in the docker-compose file for accessibility.

```bash
ls -lah /dev/accel/accel0

# Expected Outcome on Ubuntu 22.04/24.04 on WSL2
ls: cannot access '/dev/accel/accel0': No such file or directory

# Expected Outcome on Ubuntu without WSL2
crw-rw---- 1 root render 261, 0 May  8 11:19 /dev/accel/accel0
```

**Tip:** Remember to review the DETECTION_DEVICE and CLASSIFICATION_DEVICE properties in the [docker-compose.yaml](./docker-compose.yml) file, and update them accordingly based on the host hardware. A technical article for your reference of [Ultralytics YOLO and Intel AI PC](https://www.ultralytics.com/blog/running-ultralytics-yolo-models-on-intels-ai-pc-with-openvino) from Yolo Vision 2024 (YV2024).

## Management Scripts

It proposes three scripts focused on the PID installation, delete, and running management (See Table 1).

**Table 1:** Management Scripts

|Script|Objective|Observation|
|---|---|---|
|[installPID](./installPID.sh)|It verifies OS compatibility and installs dGPU/iGPU and NPU drivers.|Preferred: Ubuntu 22.04/24.04|
|[removePID](./removePID.sh)|It stops containers, removes associated images, and uninstalls dGPU/iGPU and NPU drivers.|It keeps dependencies|
|[runPID](./runPID.sh.sh)|It starts, stops, checks, and runs E2E verification of the DLStreamer Pipeline Server.|Version 3.0|

### Installing PID

1. Go to the "~/.../caxselling/pid" folder
1. Run the installation script. It requires administrative permissions.

```bash
./installPID.sh
```

Expected outcome:

![pid_figure01_installation](../../imgs/pid_figure01_installation.png)

### Running PID

The [runPID.sh](./runPID.sh) script allows it to start, check, stop, and emulates End-to-End predefined video-analytics pipelines verifying from the detection to MQTT communication.

![pid_figure02_runPID](../../imgs/pid_figure02_runPID.png)

The *e2e* option incorporates two alternatives to run and End-to-End simulation. Details about the submitted pipeline, organization, and status checking are provided [below](#testing-dlstreamer-pipeline-server):

1. **classroom:** It uses a classroom.avi as a pipeline input to detect people, tables, and other elements in a classroom. The output provides the video and bounding boxes for visualization (for example, it is possible to visualize it using [VLC Player](https://www.videolan.org/vlc/)). At the same time, the detections are communicated using MQTT and stored in a JSON file for testing and verification.
1. **items:** It is similar to the previous one, using the items.mp4 video from the [automated self-checkout](https://github.com/openvinotoolkit/openvino_build_deploy/tree/master/ai_ref_kits/automated_self_checkout) reference implementation of the OpenVINO build and deploy repository.

### Removing PID

This script stops the containers (when running), removes the associated images from Docker, and uninstalls the NPU and dGPU/iGPU drivers, keeping the dependencies in the system. It requires administrative permissions.

1. Go to the "~/.../caxselling/pid" folder
1. Run the removePID script

```bash
./removePID.sh
```

Expected outcome:

![pid_figure03_removePID](../../imgs/pid_figure03_removePID.png)

It removes the NPU driver even when running on Ubuntu 22.04/24.04 on WSL2.

## Testing DLStreamer Pipeline Server

It synthesizes how to submit your pipeline definition ([Additional details can be found in the DLStreamer Pipeline Server Documentation](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/dlstreamer-pipeline-server/docs/user-guide/how-to-launch-configurable-pipelines.md)). The [resources/videos](../pid/resources/videos/) directory is mounted in the home/pipeline-server/resources/externalvideos folder in the DLStreamer Pipeline Server container. Additionally, [here](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/dlstreamer-pipeline-server/docs/user-guide/how-to-use-rtsp-camera-as-video-source.md) explains how to submit the pipeline request through the API, indicating RTSP as a pipeline input.

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

    It will provide a pipeline ID in the output similar to the following:

    ```bash
    "6eefb2642c4e11f080ec162667ee0038"
    ```

    - We feed the pipeline with the classroom.avi video
    - Results are incorporated in /tmp/results.jsonl (in the container)
    - It will use the FP32 model version and CPU for inferencing
    - The rtsp output is derived to classroom-video-streaming so consume it from *rtsp://localhost:8554/classroom-video-streaming*

1. You can check the pipeline status through the API. You will see a similar output to the following:

    ```bash
    $ curl --location -X GET http://localhost:8080/pipelines/status
    [
    {
        "avg_fps": 10.921394098734208,
        "elapsed_time": 82.95642757415771,
        "id": "6eefb2642c4e11f080ec162667ee0038",
        "message": "",
        "start_time": 1746737583.5048995,
        "state": "RUNNING"
    }
    ]
    ```

1. Check the inference outputs from the file:

    ```bash
    $ cat /tmp/e2e_detection.jsonl
    ...
    {"objects":[{"detection":{"bounding_box":{"x_max":0.24375608330601573,"x_min":0.10223741683717691,"y_max":0.8322660570184297,"y_min":0.525094803051573},"confidence":0.9076035618782043,"label":"person","label_id":0},"h":332,"region_id":12220,"roi_type":"person","w":272,"x":196,"y":567},{"detection":{"bounding_box":{"x_max":0.7328277935509053,"x_min":0.6067636341864411,"y_max":0.8286560182073117,"y_min":0.5306058962733431},"confidence":0.8911811709403992,"label":"person","label_id":0},"h":322,"region_id":12221,"roi_type":"person","w":242,"x":1165,"y":573},{"detection":{"bounding_box":{"x_max":0.32658983955666177,"x_min":0.23575138204919366,"y_max":0.6618866065425664,"y_min":0.4556094237507793},"confidence":0.8672786951065063,"label":"person","label_id":0},"h":223,"region_id":12222,"roi_type":"person","w":174,"x":453,"y":492},{"detection":{"bounding_box":{"x_max":0.5705837096360877,"x_min":0.4581737825002339,"y_max":0.8081294180174083,"y_min":0.6780255418721666},"confidence":0.8366917967796326,"label":"chair","label_id":56},"h":141,"region_id":12223,"roi_type":"chair","w":216,"x":880,"y":732},{"detection":{"bounding_box":{"x_max":0.5369132360356037,"x_min":0.4424189395072897,"y_max":0.6528424360281591,"y_min":0.45090084747822345},"confidence":0.8357992172241211,"label":"person","label_id":0},"h":218,"region_id":12224,"roi_type":"person","w":181,"x":849,"y":487},{"detection":{"bounding_box":{"x_max":0.6168787571322731,"x_min":0.540585096785204,"y_max":0.6222236726019332,"y_min":0.553587349557688},"confidence":0.7880458831787109,"label":"chair","label_id":56},"h":74,"region_id":12225,"roi_type":"chair","w":146,"x":1038,"y":598},{"detection":{"bounding_box":{"x_max":0.3672461564428531,"x_min":0.25459084890173145,"y_max":0.8158249022934569,"y_min":0.6809658152008922},"confidence":0.7705533504486084,"label":"chair","label_id":56},"h":146,"region_id":12226,"roi_type":"chair","w":216,"x":489,"y":735},{"detection":{"bounding_box":{"x_max":0.06517725684012854,"x_min":0.0003032267138842748,"y_max":0.8605476507626122,"y_min":0.6504070378900622},"confidence":0.7493807077407837,"label":"chair","label_id":56},"h":227,"region_id":12227,"roi_type":"chair","w":125,"x":1,"y":702},{"detection":{"bounding_box":{"x_max":0.037057072476403,"x_min":6.870329482411286e-05,"y_max":0.6517852641908117,"y_min":0.578815683406825},"confidence":0.7043436765670776,"label":"chair","label_id":56},"h":79,"region_id":12228,"roi_type":"chair","w":71,"x":0,"y":625},{"detection":{"bounding_box":{"x_max":0.08696997295275288,"x_min":0.007467734924968106,"y_max":0.6043780655321189,"y_min":0.4690619300166059},"confidence":0.6256722211837769,"label":"chair","label_id":56},"h":146,"region_id":12229,"roi_type":"chair","w":153,"x":14,"y":507},{"detection":{"bounding_box":{"x_max":0.11705866034416346,"x_min":0.035127819107887426,"y_max":0.8332929973794965,"y_min":0.5746579971113501},"confidence":0.546989381313324,"label":"chair","label_id":56},"h":279,"region_id":12230,"roi_type":"chair","w":157,"x":67,"y":621},{"detection":{"bounding_box":{"x_max":0.6526755191784428,"x_min":0.41319325585951283,"y_max":0.715077577756011,"y_min":0.611669382626852},"confidence":0.5215749740600586,"label":"dining_table","label_id":60},"h":112,"region_id":12231,"roi_type":"dining_table","w":460,"x":793,"y":661}],"resolution":{"height":1080,"width":1920},"tags":{},"timestamp":32766666666}
    ```

1. You can visualize the pipeline output using VLC Viewer while running as follows:
    - Open VLC Viewer
    - Go to "Media > Open Network Stream"
    - Indicate the value **rtsp://localhost:8554/classroom-video-streaming** for the *Network URL* field
    - Press "Play"

1. Testing the pipeline producing the output over MQTT.

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

    ```bash
    sudo apt install mosquitto-clients
    ```

    - Listen the broker for the indicated topic

    ```bash
    $ mosquitto_sub --topic test_topic -p 1883 -h 127.0.0.1
    {"objects":[{"detection":{"bounding_box":{"x_max":0.24494552977301964,"x_min":0.09941523223243998,"y_max":0.8322235231432842,"y_min":0.5261960108011365},"confidence":0.9063267111778259,"label":"person","label_id":0},"h":331,"region_id":14183,"roi_type":"person","w":279,"x":191,"y":568},{"detection":{"bounding_box":{"x_max":0.7683899993954597,"x_min":0.6116099448741963,"y_max":0.827401650360251,"y_min":0.38802080732614996},"confidence":0.8893787860870361,"label":"person","label_id":0},"h":475,"region_id":14184,"roi_type":"person","w":301,"x":1174,"y":419},{"detection":{"bounding_box":{"x_max":0.3278634716252009,"x_min":0.23216308701281374,"y_max":0.6520186044576555,"y_min":0.45959077566252304},"confidence":0.8783731460571289,"label":"person","label_id":0},"h":208,"region_id":14185,"roi_type":"person","w":184,"x":446,"y":496},{"detection":{"bounding_box":{"x_max":0.5698606576004721,"x_min":0.460232836905611,"y_max":0.8073431373736728,"y_min":0.6776740890394759},"confidence":0.8678084015846252,"label":"chair","label_id":56},"h":140,"region_id":14186,"roi_type":"chair","w":210,"x":884,"y":732},{"detection":{"bounding_box":{"x_max":0.5469818435159599,"x_min":0.45002840235871666,"y_max":0.6525650121653825,"y_min":0.4533038206890794},"confidence":0.8606906533241272,"label":"person","label_id":0},"h":215,"region_id":14187,"roi_type":"person","w":186,"x":864,"y":490},{"detection":{"bounding_box":{"x_max":0.6159890266655239,"x_min":0.5429923138468311,"y_max":0.621880969731226,"y_min":0.5534903131945477},"confidence":0.8184857368469238,"label":"chair","label_id":56},"h":74,"region_id":14188,"roi_type":"chair","w":140,"x":1043,"y":598},{"detection":{"bounding_box":{"x_max":0.3660526449390149,"x_min":0.256128779890072,"y_max":0.8159874083993941,"y_min":0.680528174050572},"confidence":0.7893079519271851,"label":"chair","label_id":56},"h":146,"region_id":14189,"roi_type":"chair","w":211,"x":492,"y":735},{"detection":{"bounding_box":{"x_max":0.06482995249077605,"x_min":9.734630729774096e-05,"y_max":0.8666492591299004,"y_min":0.64985657706643},"confidence":0.7125223875045776,"label":"chair","label_id":56},"h":234,"region_id":14190,"roi_type":"chair","w":124,"x":0,"y":702},{"detection":{"bounding_box":{"x_max":0.03734917100294188,"x_min":7.993877053169562e-05,"y_max":0.6519366123070807,"y_min":0.5790255871269938},"confidence":0.7033666372299194,"label":"chair","label_id":56},"h":79,"region_id":14191,"roi_type":"chair","w":72,"x":0,"y":625},{"detection":{"bounding_box":{"x_max":0.087182058202953,"x_min":0.007281267751474196,"y_max":0.5941941588251911,"y_min":0.46865757210042425},"confidence":0.6402807235717773,"label":"chair","label_id":56},"h":136,"region_id":14192,"roi_type":"chair","w":153,"x":14,"y":506},{"detection":{"bounding_box":{"x_max":0.6179812285003248,"x_min":0.41308434625095636,"y_max":0.7154310094629377,"y_min":0.6153473230503099},"confidence":0.5931907892227173,"label":"dining_table","label_id":60},"h":108,"region_id":14193,"roi_type":"dining_table","w":393,"x":793,"y":665}],"resolution":{"height":1080,"width":1920},"tags":{},"timestamp":4766666666}    
    ...
    ```

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

---

## Thorough Analysis of the PID Module

### Purpose

The `pid` (Product Identification) module is responsible for real-time video analytics to detect and classify products/items in a retail environment. It uses Intel's Deep Learning Streamer Pipeline Server (DL Streamer/EVAM) to process video streams, perform inference using models like YOLOv11 (converted to OpenVINO format), and communicates detection results via MQTT and other outputs.

### Main Components

- **DL Streamer Pipeline Server (EVAM):** Containerized microservice for video analytics pipelines.
- **MQTT Broker (Eclipse Mosquitto):** For publishing detection/classification results.
- **Models:** OpenVINO-optimized models (e.g., YOLOv11) for object detection.
- **Management Scripts:** For install, run, and removal of the service and drivers.
- **Resources:** Video files for testing and demo pipelines.

### Key Inputs

#### 1. Video Source
- Can be a file (e.g., classroom.avi, items.mp4) or a live RTSP stream.
- Specified in the pipeline request as a URI.

#### 2. Model
- Path to OpenVINO-optimized model (e.g., yolov11s.xml/bin).
- Model and device (CPU/GPU/NPU) are specified in the pipeline request.

#### 3. Pipeline Definition
- JSON payload sent to the DL Streamer Pipeline Server API.
- Specifies source, destination, and parameters (model, device, etc.).

Example:
```json
{
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
}
```

### Key Outputs

#### 1. Detection Metadata
- **MQTT:** Publishes detection/classification results as JSON to a specified topic.
- **File:** Can output results to a file in JSON-lines format.
- **RTSP:** Streams processed video with overlays for visualization.

#### 2. API Responses
- **Pipeline ID:** When a pipeline is started, the server returns a pipeline ID.
- **Status:** API can be queried for pipeline status and statistics.

### Internal Flow

1. **Startup:** Brings up MQTT broker and DL Streamer Pipeline Server containers.
2. **Pipeline Submission:** User submits a pipeline definition via REST API.
3. **Inference:** Server processes video, runs detection/classification using specified model and device.
4. **Output:** Results are published to MQTT, saved to file, and/or streamed via RTSP.
5. **Monitoring:** User can check pipeline status and view results using MQTT clients, file inspection, or RTSP viewers (e.g., VLC).

### Example Usage

- **Start containers:**  
  `docker compose up -d`
- **Submit pipeline:**  
  Use `curl` to POST a pipeline definition to the server.
- **Monitor results:**  
  - Use `mosquitto_sub` to listen for MQTT messages.
  - Use VLC to view RTSP stream.
  - Inspect output files for detection metadata.

### Summary Table

| Input Type      | How Provided                | Output Type         | Description                                  |
|-----------------|----------------------------|---------------------|----------------------------------------------|
| Video (file/RTSP)| Pipeline JSON (API)        | MQTT, file, RTSP    | Real-time detection/classification results   |
| Model (OpenVINO)| Pipeline JSON (API)         | -                   | Used for inference                          |
| Pipeline config | REST API (JSON)             | Pipeline ID, status | Controls analytics pipeline                  |

---

If you need a deeper dive into the API, pipeline configuration, or output formats, see the code or contact the maintainers.
