# Troubleshooting

This article contains troubleshooting steps for known issues. If you encounter a problem not listed here, check the [GitHub Issues](https://github.com/intel-retail/digital-signage/issues) board or file a new ticket after reviewing the [Contributing guidelines](https://github.com/intel-retail/digital-signage/blob/main/CONTRIBUTING.md).

---

## 1. Build Fails During `make build`

**Issue**

`make build` exits with an error during Docker image construction.

**Reason**

Docker Engine or Docker Compose is not installed, not running, or the host cannot reach the internet to download dependencies.

**Solution**

- Verify Docker Engine and Docker Compose are installed and running:

  ```bash
  docker version
  docker compose version
  ```

- Confirm your host has internet access and that any proxy settings are correctly configured. See [Configure Docker](./get-started.md#configure-docker).

---

## 2. Containers Keep Restarting

**Issue**

One or more containers enter a restart loop after `make up`.

**Solution**

Check which container is restarting and review its logs:

```bash
docker ps
docker logs -f <container_name>
```

Common causes:

- Missing or incorrectly downloaded AI models. Re-run the model download steps in [Build from Source](./get-started/build-from-source.md).
- Invalid `.env` values (for example, `HOST_IP` not set, or ICE server credentials not meeting length requirements).

---

## 3. No Advertisements Displayed in the Browser

**Issue**

The Web UI loads but no advertisements appear.

**Reason**

Detections are not reaching the Web UI via MQTT, or detected labels are not mapped in `ProductAssociations.csv`.

**Solution**

1. Confirm that PID is publishing detections to MQTT by checking PID container logs:

   ```bash
   docker logs -f <pid_container_name>
   ```

2. Verify that the labels detected by PID match entries in `web-ui/ProductAssociations.csv` (case-insensitive match).
3. Check AIG and ASe container logs for errors:

   ```bash
   docker logs -f <aig_container_name>
   docker logs -f <ase_container_name>
   ```

4. Confirm confidence and recency thresholds in `.env` are not set too restrictively (`OBJECT_CONFIDENCE_THRESHOLD`, `OBJECT_RECENCY_FRAME_COUNT`).

---

## 4. Slow Ad Generation on Low-Resource Systems

**Issue**

Ad generation is slow on low-resource systems.

**Reason**

Ad generation (AIG) runs on the GPU. When Chrome also uses GPU acceleration, the two compete for GPU resources, leaving insufficient capacity for AIG and causing slow ad generation rendering instability.

**Solution**

- Use Google Chrome.
- On low-resource systems, launch Chrome with GPU acceleration disabled:

  ```bash
  google-chrome --process-per-site --disable-plugins --disable-gpu https://localhost:5000
  ```

- Alternatively, in Chrome go to **Settings → System** and disable:
  - **Continue running background apps when Google Chrome is closed**
  - **Use graphics acceleration when available**

  Then relaunch Chrome.

- Verify that `HOST_IP`, `MTX_WEBRTCICESERVERS2_0_USERNAME`, and `MTX_WEBRTCICESERVERS2_0_PASSWORD` are correctly set in `.env`.

---

## 5. Model Download Fails

**Issue**

The YOLO11s or AIG model download step exits with an error.

**Solution**

- Confirm internet access and proxy settings.
- Ensure Python virtual environment creation succeeds (`python3 -m venv`).
- For Hugging Face downloads, set the `HF_HUB_ENABLE_HF_TRANSFER=1` environment variable as documented in [Build from Source](./get-started/build-from-source.md).
- Ensure sufficient disk space (500 GB free recommended).
