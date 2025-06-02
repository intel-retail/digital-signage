# Advertise Image Generator (AIG)

| [Project Readme.md](../../README.md) | [CAXSelling Readme.md](../README.md) |

It describes functionalities and package organization for the Advertise Image Generator (AIG). It aims to create images based on descriptive text, incorporating an API to customize the image generation based on logos, slogans, price, and promotional text.

Content:

- [Conceptual Approach and Container Initialization](#conceptual-approach-and-container-initialization)
  - [Configuration](#configuration)
- [Intel Hardware Drivers](#intel-hardware-drivers)
- [Management Scripts](#management-scripts)
- [Model Download](#model-download)
- [AIG Server Test](#aig-server-test)

## Conceptual Approach and Container Initialization

The [docker compose file](./docker/docker-compose.yml) starts a AIG Server container including GPU drivers required to run the text2image model.

The folder organization is as follows:

```bash
├ docker
│   └─ model # Folder containing the text2image model to be used for image generation
│   └─ sharedata # Shared folder between the host and AIG Server for data exchange (for example, company logo to be included in images)
├ src # AIG Server (Source Code)
├ Dockerfile #It defines how to build and start the AIG Server
├ installAIG.sh # The installation Script
├ runAIG.sh # The initialization and check Script
├ removeAIG.sh # The removal Script
```

### Configuration

The [sample.env](./docker/sample.env) file is a sample configuration file. If you want to reuse it, update the corresponding values (See Table below) and rename it to .env before starting the containers.

|Group | Variable|Objective|Observation|
|---|---|---|---|
|aig-server|AIG_SERVER_USER|AIG Server admin user| Example: intelmicroserviceuser|
|aig-server|AIG_PORT|AIG Server port| Default: 5003|
|aig-server|UID|AIG Admin user uid| Default: 1000. Example: id -u "user"|
|aig-server|AIG_LOGO_PATH| Path in the container to the company logo file (with transparent background, RGBA) | For example: '/opt/sharedata/sample_logo.png'|
|aig-server|AIG_FONT_PATH| Path in the container to the font to be used in slogans, promotional text, and price| For example: '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'|
|aig-server|AIG_MODEL_PATH| Path in the container to the text2image model| Example: '/opt/models/dreamlike_anime_1_0_ov/FP16'|
|aig-server|AIG_MODEL_DEVICE| Default Device to run the text2image model [CPU, GPU, NPU]| Default: 'GPU'|
|aig-server|AIG_MODEL_NUM_INFERENCE_STEPS|Number of inference steps for the text2image model|Default: =20|
|aig-server|AIG_IMG_WIDTH_DEFAULT|Image width for the image to be generated|Default: 512|
|aig-server|AIG_IMG_HEIGHT_DEFAULT|Image Height for the image to be generated| Default: 512|
|proxy|http_proxy|environment variable with http proxy information| Default: ${http_proxy}|
|proxy|https_proxy|environment variable with https proxy information| Default: ${https_proxy}|
|proxy|no_proxy|environment variable for the address that the proxy is not required| Example: localhost,eii-nightly-devops.iind.intel.com,127.0.0.1|

[&uarr; Top](#advertise-image-generator-aig)

## Intel Hardware Drivers

It is critical to set up and install proper drivers to ensure the full benefits of the hardware on top of which the containers run. Scripts will take care of it for you. Details on [the drivers](../pid/README.md#intel-hardware-drivers) are available following the link.

[&uarr; Top](#advertise-image-generator-aig)

## Management Scripts

It proposes three scripts focused on the AIG installation, delete, and running management (See Table 1).

**Table 1:** Management Scripts

|Script|Objective|Observation|
|---|---|---|
|[installAIG](./installAIG.sh)|It verifies OS compatibility and installs dGPU/iGPU and NPU drivers.|Preferred: Ubuntu 22.04/24.04|
|[removeAIG](./removeAIG.sh)|It stops containers and removes associated images.|It keeps dependencies|
|[runAIG](./runAIG.sh)|It starts, stops, and checks the AIG Server.|Version 0.1.0|

### Installing AIG

1. Go to the "~/.../caxselling/aig" folder
1. Run the installation script. It requires administrative permissions.

```bash
./installAIG.sh
```

The installation script will install virtual environments, download and convert the default text2image model, and create the AIG server. It could take a while (5-10 minutes, depending on the hardware). Expected outcome:

![aig_figure01_installation.png](../../imgs/aig_figure01_installation.png)

[&uarr; Top](#advertise-image-generator-aig) | [&uarr; Management Scripts](#management-scripts)

### Running AIG

The [runAIG.sh](./runAIG.sh) script allows it to start, check, and stop AIG server and the associated containers.

1. Go to the "~/.../caxselling/aig" folder
1. Run the runAIG script with the pertinent option (See the figure).

![aig_figure02_runAIG.png](../../imgs/aig_figure02_runAIG.png)

The API is initiated on port 5003 (Default), so you can reach it through your browser at localhost:5003.

[&uarr; Top](#advertise-image-generator-aig) | [&uarr; Management Scripts](#management-scripts)

### Removing AIG

This script stops the containers (when running) and removes the associated images from Docker.

1. Go to the "~/.../caxselling/aig" folder
1. Run the removeAIG script

```bash
./removeAIG.sh
```

Expected outcome:

![aig_figure03_removeAIG](../../imgs/aig_figure03_removeAIG.png)

[&uarr; Top](#advertise-image-generator-aig) | [&uarr; Management Scripts](#management-scripts)

## Model Download

Models to be used with the AIG Server must be converted to OpenVINO format and installed under the [models folder](./docker/models/). The models folder is mounted in the [docker-compose.yaml](./docker/docker-compose.yml) file at "/opt/models".

To download and convert a model in OpenVino format follow the following steps:

1. Create a virtual environment. It is created by the [installAIG.sh](./installAIG.sh) script under the docker folder. You can reuse it and jump to the next step.

    ```bash
        python -m venv .modelenv
    ```

1. Activate the virtual environment and install the required libraries.

    ```bash
    source .modelenv/bin/activate
    pip install --upgrade-strategy eager -r export-requirements.txt
    ```

1. Use the following command to download and convert models from Hugging face:

    ```bash
    optimum-cli export openvino --model dreamlike-art/dreamlike-anime-1.0 --task stable-diffusion --weight-format fp16 dreamlike_anime_1_0_ov/FP16    
    ```

    For example, the above command download and convert the dreamlike-anime-1.0 model in the ./dreamlike_anime_1_0_ov/FP16.

    You can repeat this step as often as you wish to download other models similarly. Just replace the model to be downloaded and converted, and specify the target folder:

    ```bash
    optimum-cli export openvino --model "user/model" --task stable-diffusion --weight-format fp16 "target_folder"
    ```

1. Set up the model to be used in the AIG server
    1. Move the model folder under CACS_SignageApproach/caxselling/aig/docker/models. For example:

        ```bash
        mv ./dreamlike_anime_1_0_ov/FP16 /CACS_SignageApproach/caxselling/aig/docker/models
        cd /CACS_SignageApproach/caxselling/aig/docker/models
        ls
        (.modelenv) ~/CACS_SignageApproach/caxselling/aig/docker/models$ ls
        README.txt  dreamlike_anime_1_0_ov
        ls dreamlike_anime_1_0_ov
        FP16
        ```

    1. Update the "AIG_MODEL_PATH" variable in the .env file (See [sample.env](./docker/sample.env))

        > AIG_MODEL_PATH='/opt/models/dreamlike_anime_1_0_ov/FP16'

        Remember that the models directory under docker folder is mounted at /opt/models in the container. Thus, you could refer to your model as indicated in the example.

    1. Start (or restart) the AIG Server to load the new model in memory.

## AIG Server Test

1. Go to localhost:5003 once started the server
2. Go to "AIG - Inference with Added-Value Services" section and try it with the following JSON doc:

```json
{
  "description": "A 35mm photo with strawberry, 8k",
  "device": "GPU",
  "framed": true,
  "price_details": {
    "price": "0.57 $/lb",
    "align": "right",
    "valign": "bottom",
    "marperc_from_border": 10,
    "font_size": 24,
    "line_width": 5,
    "price_color": "white",
    "price_in_circle": true,
    "price_circle_color": "black"
  },
  "promo_details": {
    "promo_text": "Get one pound and get 50% in the second!",
    "text_color": "white",
    "rect_color": "black",
    "rect_padding": 10,
    "rect_radius": 20,
    "align": "left",
    "valign": "bottom",
    "marperc_from_border": 10,
    "font_size": 20,
    "line_width": 10
  },
  "logo_details": {
    "align": "left",
    "valign": "top",
    "logo_percentage": 15,
    "margin_px": 10
  },
  "slogan_details": {
    "slogan_text": "The best price in town",
    "text_color": "white",
    "align": "right",
    "valign": "top",
    "marperc_from_border": 5,
    "font_size": 18,
    "line_width": 20
  },
  "framed_details": {
    "activate": true,
    "marperc_from_border": 2
  }
}
```

You should see an output similar to the following one:

![aig_figure04_test](../../imgs/aig_figure04_test.png)

[&uarr; Top](#advertise-image-generator-aig) | [&uarr; Management Scripts](#management-scripts)
