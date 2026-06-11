# Use Intel® Geti™ Exported Model

1. Export an OpenVINO™ IR object-detection model (`.xml`/`.bin`) from Intel® Geti™.
2. Place the exported model under:

```text
pid/models/object_detection/geti-sdk-deployment/deployment/Detection/model
```

3. Update `pid/config.json` model path to your exported `.xml` file.
4. Deploy and verify logs:

```bash
make up
docker logs -f <pid_container_name>
```
