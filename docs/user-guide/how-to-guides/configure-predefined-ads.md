# Configure Predefined Advertisements

Predefined advertisements are static JPEG/JPG images that the Advertise Searcher (ASe) service
stores in Milvus and returns when a matching product is detected. This guide explains how
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

## Milvus Catalog Migration and Rollback

Use this cutover only while advertisement writes are stopped. Do **not** run `docker compose down -v`; the legacy Chroma volume is intentionally retained for rollback.

1. **Back up the existing catalog assets**:

   ```bash
   cp -a ./aig/sharedata ./aig/sharedata.backup.$(date +%Y%m%d%H%M%S)
   docker volume inspect digitalsignage_chroma_data
   ```

2. **Save the old source tree and old AIG image reference** before rebuilding.

3. **From the saved pre-migration checkout/image, export the existing Chroma catalog with the legacy profile**:

   ```bash
   docker compose --profile legacy-chroma up -d ase-chromadb
   docker compose run --rm \
     -e ASE_CHROMADB_HOST=ase-chromadb \
     aig-server \
     python3 -m src.database.migrate_chroma export \
       --collection-name "${ASE_COLLECTION_NAME}" \
       --output /opt/sharedata/ase-chroma-backup.ndjson
   ```

4. **Build and validate the Milvus-based stack**:

   ```bash
   docker compose config -q
   make build
   docker compose up -d ase-etcd ase-milvus
   docker compose ps
   ```

5. **Import into a fresh Milvus target**:

   ```bash
   docker compose run --rm aig-server \
     python3 -m src.database.migrate_chroma import \
       --input /opt/sharedata/ase-chroma-backup.ndjson \
       --collection-name "${ASE_COLLECTION_NAME}"
   ```

6. **Start AIG and validate representative CRUD/search flows**, then restart once to confirm persistence:

   ```bash
   docker compose up -d aig-server web-ui nginx
   docker compose restart ase-milvus aig-server
   ```

7. **Rollback** if needed by restoring the old source/config/image, keeping `chroma_data` untouched, and bringing the legacy profile back up:

   ```bash
   docker compose down
   docker compose --profile legacy-chroma up -d ase-chromadb aig-server web-ui nginx
   ```

Notes:

- `./aig/sharedata:/opt/sharedata`, `./aig/src:/home/aigserver/src`, and `./aig/models:/opt/models` are bind-mounted into `aig-server`; the migration utility reads and writes through those paths.
- The local Compose deployment keeps Milvus unauthenticated on the internal Docker network by default. Use `ASE_MILVUS_TOKEN` only when pointing ASe at an external secured Milvus endpoint.
- Post-cutover writes are **not** mirrored back into Chroma automatically.
