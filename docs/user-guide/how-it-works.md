# How It Works

The Web UI subscribes to object-detection events and selects which product should drive the next advertisement.

## Processing Flow

1. **Detection Ingestion:** Web UI receives labels from MQTT (PID output).
2. **Temporal Filtering:** Labels must pass recency and confidence thresholds.
3. **Product Mapping:** Eligible labels are mapped through `web-ui/ProductAssociations.csv`.
4. **Product Selection:** Prioritizes unseen/high-value products, then rotates for variety.
5. **Ad Selection:** Attempts predefined ad first; falls back to dynamic generation via AIG.
6. **Client Delivery:** Latest advertisement is served through `/get_current_advertisement`.

## Inputs Affecting Behavior

- `web-ui/ProductAssociations.csv`
- `web-ui/pre-defined-ads/`
- `.env` thresholds and timing values
