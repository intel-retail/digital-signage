# Troubleshooting

This article contains troubleshooting steps for known issues. If you encounter a problem not listed here, check the [GitHub Issues](https://github.com/intel-retail/digital-signage/issues) board or file a new ticket after reviewing the [Contributing guidelines](https://github.com/intel-retail/digital-signage/blob/main/CONTRIBUTING.md).

---

## 1. Build Fails During `make build`

**Issue**:

`make build` exits with an error during Docker image construction.

**Reason**:

Docker Engine or Docker Compose is not installed, not running, or the host cannot reach the internet to download dependencies.

**Solution**:

- Verify Docker Engine and Docker Compose are installed and running:

  ```bash
  docker version
  docker compose version
  ```

- Confirm your host has internet access and that any proxy settings are correctly configured. See [Configure Docker](./get-started.md#configure-docker).

---

## 2. Containers Keep Restarting

**Issue**:

One or more containers enter a restart loop after `make up`.

**Solution**:

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

**Issue**:

The Web UI loads but no advertisements appear.

**Reason**:

Detections are not reaching the Web UI via MQTT, or detected labels are not mapped in `ProductAssociations.csv`.

**Solution**:

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

**Issue**:

Ad generation is slow on low-resource systems.

**Reason**:

Ad generation (AIG) runs on the GPU. When Chrome also uses GPU acceleration, the two compete for GPU resources, leaving insufficient capacity for AIG and causing slow ad generation rendering instability.

**Solution**:

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

**Issue**:

`make download_models` exits with an error.

**Solution**:

- Confirm Docker Engine is running and that standard Docker commands succeed:

  ```bash
  docker version
  docker pull intel/model-download:latest@sha256:5d7607a8d8c184602eae5bfc5a9bd1783e204da65a6adee8e467677e7f668849
  ```
- Confirm internet access and proxy settings. See [Configure Docker](./get-started.md#configure-docker).
- Re-run `make download_models`; the command prints the model-download container logs when a startup job fails.
- Verify that `configs/model-download/startup-models.yaml` has not been modified to point outside the repository model directories.
- Ensure sufficient free disk space for the downloaded models and the temporary Docker image layers (500 GB free recommended).

---

## 6. Video Not Rendering in Browser (MediaMTX `no space left on device`)

**Issue**:

The browser page loads, but video does not render. MediaMTX logs show `no space left on device` (`ENOSPC`).

**Reason**:

In this scenario, `ENOSPC` is usually not caused by hard drive capacity. It is commonly caused by exhausting Linux host resources such as inotify watches, inotify instances, open file descriptor limits, or filesystem inodes.

**Solution**:

1. Confirm current inotify limits on the host:

   ```bash
   cat /proc/sys/fs/inotify/max_user_watches
   cat /proc/sys/fs/inotify/max_user_instances
   ```

2. Increase the limits by editing sysctl configuration:

   ```bash
   sudo nano /etc/sysctl.conf
   ```

3. Append the following values at the end of the file:

   ```text
   fs.inotify.max_user_watches=1048576
   fs.inotify.max_user_instances=10000
   ```

4. Apply the updated kernel parameters immediately:

   ```bash
   sudo sysctl -p
   ```

5. Redeploy the Digital Signage stack and verify MediaMTX is healthy:

   ```bash
   make up
   docker logs -f mediamtx
   ```

If needed, also verify inode availability (`df -i`) and open file limits (`ulimit -n`) on the host.

## 7. SDXL-Turbo and MiniLM Models (for AIG) Download Failed

**Issue**

The AIG startup job inside `make download_models` fails while preparing SDXL-Turbo or all-MiniLM-L12-v2.

**Reason**

The model-download container writes directly into `./aig/models`, so failures are usually caused by insufficient free disk space, interrupted network access, or a partial previous download left in the staging directory.

**Solution**

1. Ensure the filesystem that contains the repository has enough free space for `./aig/models`.
2. Remove any incomplete staged AIG download and retry:

   ```bash
   rm -rf ./aig/models/.model-download/sdxl_turbo_ov ./aig/models/.model-download/all-MiniLM-L12-v2
   make download_models
   ```

3. If the failure persists, review the model-download logs emitted by `make download_models` and verify host network/proxy access to Hugging Face.
