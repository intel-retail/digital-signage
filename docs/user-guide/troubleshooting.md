# Troubleshooting

## Build Fails During `make build`

- Verify Docker Engine and Docker Compose are installed and running.
- Verify host network and certificate trust for dependency downloads.

## Containers Restarting

```bash
docker ps
docker logs -f <container_name>
```

## No Ads Displayed

- Verify detections are arriving from PID via MQTT.
- Validate `web-ui/ProductAssociations.csv` mappings.
- Check AIG and ASe service health in container logs.

## WebRTC/Browser Display Issues

- Use Google Chrome.
- Disable GPU acceleration on low-resource systems if rendering is unstable.
