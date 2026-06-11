# Configure Predefined Advertisements

1. Add or update product rows in `web-ui/ProductAssociations.csv`.
2. Add corresponding JPEG/JPG image files in `web-ui/pre-defined-ads/`.
3. Ensure CSV image names exactly match files.
4. Redeploy:

```bash
make down
make up
```
