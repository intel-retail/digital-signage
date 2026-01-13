# Context-Aware, Cross-Selling (CAXSelling) Approach

It describes functionalities and package organization for the Context-Aware, Cross-Selling (CAXSelling) Approach. It shows how the involved components are articulated and their business logic.

It is composed of the following components:

1. Product Identification (PID)
2. Web UI
3. Advertise Image Generator (AIG)
4. Advertise Searcher (ASe)


## Clone source code

```bash
git clone https://github.com/intel-sandbox/CACS_SignageApproach.git digital-signage
cd digital-signage
```

## Steps to Build

> **NOTE:** Execute all commands as a regular user. Do not use `root` or `sudo` privileges.

### Install Product Identification (PID)

```bash
cd pid && ./installPID.sh && cd ..
```

### Download the YOLO11s Model

> **NOTE:** Please review the [license terms](https://github.com/ultralytics/ultralytics/blob/main/LICENSE) of the `YOLO11s` model.

From the `digital-signage` repo directory:

```bash
cd pid && \
wget https://raw.githubusercontent.com/intel-retail/automated-self-checkout/v3.6.3/download_models/downloadAndQuantizeModel.sh && \
sed -i 's|MODELS_PATH="${MODELS_DIR:-/workspace/models}"|MODELS_PATH="${MODELS_DIR:-$PWD/models}"|g' downloadAndQuantizeModel.sh && \
sed -i 's/MODEL_NAME="yolo11n"/MODEL_NAME="yolo11s"/g' downloadAndQuantizeModel.sh && \
rm -rf .modelenv && \
python3 -m venv .modelenv && \
source .modelenv/bin/activate && \
pip3 install -r model_download_requirements.txt && \
rm -rf models && \
chmod +x downloadAndQuantizeModel.sh && \
./downloadAndQuantizeModel.sh && \
rm ./downloadAndQuantizeModel.sh && \
deactivate && \
cd ..
```

The quantized model will be saved to `./pid/models/yolo11s` directory.



### Download the Stability AI SDXL-Turbo and all-MiniLM-L6-v2 models

> **NOTE:** Please review the [license terms](https://huggingface.co/stabilityai/sdxl-turbo/blob/main/LICENSE.md) of the `Stability AI SDXL-Turbo` model.

From the `digital-signage` repo directory:

```bash
cd aig && \
rm -rf .modelenv && \
python3 -m venv .modelenv && \
source ./.modelenv/bin/activate && \
pip3 install -r export-requirements.txt && \
optimum-cli export openvino --model stabilityai/sdxl-turbo --task stable-diffusion-xl --weight-format fp16 ./models/sdxl_turbo_ov/fp16 && \
huggingface-cli download sentence-transformers/all-MiniLM-L6-v2 --local-dir ./models/all-MiniLM-L6-v2 && \
deactivate && \
cd ../
```

The models will be downloaded in the `./aig/models/` directory.


### Build Docker Images

From the `digital-signage` repo directory:

```bash
make build
```

## Steps to deploy

> **NOTE:** Execute all commands as a regular user. Do not use `root` or `sudo` privileges.

### Configuration

Update the following fields in `.env`:
   - `HOST_IP`
   - `MTX_WEBRTCICESERVERS2_0_USERNAME`
   - `MTX_WEBRTCICESERVERS2_0_PASSWORD`

### Deploy the app

From the `digital-signage` repo directory:

```bash
make up
```

### Verify Deployment

Check the health of all containers if they are running as expected.
If any container is restarting, please check the logs of the container by running command: `docker logs -f <container_name>`

```bash
docker ps
```

### Access the Web Interface

To view the input video stream and the displayed advertisements, open the following URL in Google Chrome:

```bash
http://<HOST_IP>:5000
```

### Undeploy the app

From the `digital-signage` repo directory:

```bash
make down
```