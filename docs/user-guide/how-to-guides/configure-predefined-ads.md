# Configure Predefined Advertisements

Predefined advertisements are static JPEG/JPG images that the Advertise Searcher (ASe) service
stores in ChromaDB and returns when a matching product is detected. This guide explains how
to provision products with predefined ads.

## Prerequisites

- Ensure the application is deployed. See the [Get Started](../get-started.md) guide.

## Steps

1. **Prepare image assets**: Create JPEG or JPG advertisement images and place them in `web-ui/pre-defined-ads/`.

   > **Note:** Only JPEG/JPG image formats are supported.

2. **Update the product associations**: Edit `web-ui/ProductAssociations.csv` and add or update rows for your products. Each row defines:

   | Column            | Description                                                                                                 |
   | ----------------- | ----------------------------------------------------------------------------------------------------------- |
   | Product label     | Detection label as it appears from PID (normalized to lowercase).                                           |
   | Price             | Displayed price string.                                                                                     |
   | Promo text        | Short promotional description.                                                                              |
   | Slogan            | Brand or campaign slogan.                                                                                   |
   | Cross-sell target | Label of a related product to promote alongside.                                                            |
   | Dynamic prompt    | Text prompt used for AIG if no predefined ad is found.                                                      |
   | Image filename    | Filename (in `pre-defined-ads/`) to use as the predefined ad. Leave blank to always use dynamic generation. |

3. **Verify filenames match**: Ensure image filenames in the CSV exactly match the files present in `web-ui/pre-defined-ads/`.

4. **Redeploy the application**:

   ```bash
   make down
   make up
   ```
