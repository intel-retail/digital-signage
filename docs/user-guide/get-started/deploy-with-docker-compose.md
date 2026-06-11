# Deploy with Docker Compose

## Configure Environment

Update `.env`:

- `HOST_IP`
- `MTX_WEBRTCICESERVERS2_0_USERNAME` (minimum 5 alphabetic characters)
- `MTX_WEBRTCICESERVERS2_0_PASSWORD` (minimum 8 alphanumeric characters including at least one digit)

Optional:

- RTSP variables (`RTSP_CAMERA_IP`, related camera values)
- AIG and ASe tuning variables

To use predefined ads, update:

- `web-ui/ProductAssociations.csv`
- `web-ui/pre-defined-ads/` (JPEG/JPG files only)

## Deploy

```bash
make up
```

## Access Web UI

```text
http://<HOST_IP>:5000
```

## Verify

```bash
docker ps
docker logs -f <container_name>
```

## Undeploy

```bash
make down
```
