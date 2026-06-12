# Build from Source

This guide provides step-by-step instructions for cloning the Digital Signage repository, downloading required AI models, and building container images from source.

> **NOTE:** Run all commands as a regular (non-root) user, without using `sudo`. Ensure [Docker is configured](../get-started.md#configure-docker) and you have internet access before proceeding.

## Step 1: Clone the Repository

```bash
git clone https://github.com/intel-retail/digital-signage
cd digital-signage
```

## Step 2: Download AI Models

### Download YOLO11s Model (for PID)

> Please review the [YOLO11s license](https://github.com/ultralytics/ultralytics/blob/main/LICENSE) before downloading.

```bash
cd configs/pid && \
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
cd ../..
```

The quantized model is saved to `./configs/pid/models/object_detection/yolo11s`.

### Download SDXL-Turbo and MiniLM Models (for AIG)

> Please review the [SDXL-Turbo license](https://huggingface.co/stabilityai/sdxl-turbo/blob/main/LICENSE.md) before downloading.

```bash
cd aig && \
rm -rf .modelenv && \
python3 -m venv .modelenv && \
source ./.modelenv/bin/activate && \
pip3 install -r export-requirements.txt && \
export HF_HUB_ENABLE_HF_TRANSFER=1 && \
optimum-cli export openvino --model stabilityai/sdxl-turbo --task stable-diffusion-xl --weight-format int8 ./models/sdxl_turbo_ov/int8 && \
huggingface-cli download sentence-transformers/all-MiniLM-L12-v2 --local-dir ./models/all-MiniLM-L12-v2 && \
deactivate && \
cd ../
```

Models are downloaded to `./aig/models/`.

## Step 3: Build Docker Images

```bash
make build
```

Proceed to [Deploy with Docker Compose](./deploy-with-docker-compose.md) once the build completes.
