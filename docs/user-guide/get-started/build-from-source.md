# Build from Source

## Clone Repository

```bash
git clone https://github.com/intel-retail/digital-signage
cd digital-signage
```

## Download Models

### PID model (YOLO11s)

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

### AIG models (SDXL-Turbo + MiniLM)

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

## Build Images

```bash
make build
```
