import argparse
import json
import logging
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np

from database.milvus_collection import (
    DuplicateIdError,
    LocalSentenceTransformerEmbeddings,
    MilvusAdvertisementCollection,
    MilvusConfigurationError,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

MANIFEST_TYPE = "manifest"
RECORD_TYPE = "record"


def _load_chromadb_module():
    try:
        import chromadb  # pylint: disable=import-outside-toplevel
    except ImportError as exc:
        raise RuntimeError(
            "ChromaDB export requires the legacy Chroma-enabled environment. Re-run the export step with the pre-migration image or install chromadb==1.5.9."
        ) from exc
    return chromadb


def _atomic_create_text_file(path: Path):
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing backup file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False)
    return temp_file


def _read_manifest_and_validate(path: Path) -> dict:
    manifest = None
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            payload = json.loads(line)
            if line_number == 1:
                if payload.get("type") != MANIFEST_TYPE:
                    raise ValueError("The first line of the backup file must be the manifest.")
                manifest = payload
                break
    if manifest is None:
        raise ValueError("Backup file is empty.")
    if manifest.get("metric") != "l2":
        raise ValueError(f"Unsupported source metric {manifest.get('metric')!r}; only Chroma L2 collections can be migrated.")
    return manifest


def _iter_backup_records(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            payload = json.loads(line)
            if line_number == 1:
                continue
            if payload.get("type") != RECORD_TYPE:
                raise ValueError(f"Unexpected backup record type on line {line_number}: {payload.get('type')}")
            yield payload


def _extract_chroma_metric(configuration_json: dict) -> str:
    hnsw_config = configuration_json.get("hnsw")
    if not isinstance(hnsw_config, dict):
        raise ValueError(f"Unsupported Chroma configuration: {configuration_json}")
    metric = hnsw_config.get("space")
    if metric is None:
        raise ValueError(f"Unable to determine Chroma distance metric from configuration: {configuration_json}")
    return metric


def export_chroma(args) -> int:
    chromadb = _load_chromadb_module()
    client = chromadb.HttpClient(host=args.host, port=args.port)
    collection = client.get_collection(name=args.collection_name)
    configuration_json = getattr(collection, "configuration_json", None)
    if not isinstance(configuration_json, dict):
        raise ValueError(f"Unexpected Chroma configuration representation: {type(configuration_json)}")

    count = collection.count()
    metric = _extract_chroma_metric(configuration_json)
    if metric != "l2":
        raise ValueError(f"Unsupported source metric {metric!r}; only Chroma L2 collections can be migrated.")

    seen_ids = set()
    output_path = Path(args.output).resolve()
    temp_file = _atomic_create_text_file(output_path)
    exported_count = 0
    try:
        manifest = {
            "type": MANIFEST_TYPE,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "collection_name": args.collection_name,
            "count": count,
            "metric": metric,
            "configuration_json": configuration_json,
            "source": {
                "host": args.host,
                "port": args.port,
            },
        }
        temp_file.write(json.dumps(manifest, sort_keys=True) + "\n")

        for offset in range(0, count, args.batch_size):
            batch = collection.get(
                limit=args.batch_size,
                offset=offset,
                include=["documents", "embeddings", "metadatas"],
            )
            ids = batch.get("ids", [])
            documents = batch.get("documents", [])
            metadatas = batch.get("metadatas", [])
            embeddings = batch.get("embeddings", [])
            if not (len(ids) == len(documents) == len(metadatas) == len(embeddings)):
                raise ValueError(f"Partial export detected at offset {offset}: inconsistent batch lengths.")

            for row_id, document, metadata, embedding in zip(ids, documents, metadatas, embeddings):
                if row_id in seen_ids:
                    raise ValueError(f"Duplicate ID detected during export: {row_id}")
                seen_ids.add(row_id)
                if metadata is None or document is None or embedding is None:
                    raise ValueError(f"Incomplete exported row for ID {row_id}")
                embedding_array = np.asarray(embedding, dtype=np.float32)
                if embedding_array.ndim != 1 or not np.isfinite(embedding_array).all():
                    raise ValueError(f"Invalid embedding stored for ID {row_id}")
                temp_file.write(
                    json.dumps(
                        {
                            "type": RECORD_TYPE,
                            "id": str(row_id),
                            "document": document,
                            "metadata": metadata,
                            "embedding": embedding_array.tolist(),
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                exported_count += 1

        if exported_count != count:
            raise ValueError(f"Partial export detected: expected {count} records, exported {exported_count}.")

        temp_file.flush()
        os.fsync(temp_file.fileno())
        temp_file.close()
        os.replace(temp_file.name, output_path)
        logger.info("Exported %s Chroma records to %s", exported_count, output_path)
        return 0
    finally:
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)


def _validate_backup_against_embedding_model(path: Path, embedding_provider, batch_size: int) -> tuple[int, int]:
    seen_ids = set()
    pending_ids = []
    pending_documents = []
    pending_embeddings = []
    total_records = 0

    def _flush_pending() -> None:
        if not pending_documents:
            return
        encoded = embedding_provider.encode(pending_documents)
        for row_id, expected, actual in zip(pending_ids, pending_embeddings, encoded):
            expected_array = np.asarray(expected, dtype=np.float32)
            actual_array = np.asarray(actual, dtype=np.float32)
            if expected_array.shape != actual_array.shape:
                raise ValueError(
                    f"Embedding dimension mismatch for ID {row_id}: exported {expected_array.shape}, local model {actual_array.shape}."
                )
            if not np.allclose(expected_array, actual_array, rtol=1e-4, atol=1e-5):
                raise ValueError(
                    f"Embedding mismatch for ID {row_id}. The current local SentenceTransformer configuration does not reproduce the stored Chroma vectors."
                )
        pending_ids.clear()
        pending_documents.clear()
        pending_embeddings.clear()

    for record in _iter_backup_records(path):
        row_id = str(record["id"])
        if row_id in seen_ids:
            raise ValueError(f"Duplicate ID detected in backup file: {row_id}")
        seen_ids.add(row_id)
        embedding = np.asarray(record["embedding"], dtype=np.float32)
        if embedding.ndim != 1 or not np.isfinite(embedding).all():
            raise ValueError(f"Invalid exported embedding for ID {row_id}")
        pending_ids.append(row_id)
        pending_documents.append(record["document"])
        pending_embeddings.append(embedding)
        total_records += 1
        if len(pending_documents) >= batch_size:
            _flush_pending()

    _flush_pending()
    return total_records, len(seen_ids)


def import_milvus(args) -> int:
    input_path = Path(args.input).resolve()
    manifest = _read_manifest_and_validate(input_path)
    embedding_provider = LocalSentenceTransformerEmbeddings(args.model_path, model_id=args.model_id)
    validated_records, unique_ids = _validate_backup_against_embedding_model(input_path, embedding_provider, args.batch_size)
    if validated_records != manifest.get("count") or validated_records != unique_ids:
        raise ValueError(
            f"Backup validation failed: manifest count={manifest.get('count')}, validated records={validated_records}, unique ids={unique_ids}."
        )

    collection = MilvusAdvertisementCollection(
        uri=args.uri,
        token=args.token,
        collection_name=args.collection_name,
        embedding_provider=embedding_provider,
    )
    try:
        if collection.count() > 0 and not args.resume:
            raise DuplicateIdError(
                f"Target Milvus collection '{args.collection_name}' is not empty. Use --resume only for a previously interrupted import into the same dedicated target."
            )

        batch = []
        imported = 0
        skipped = 0
        for record in _iter_backup_records(input_path):
            batch.append(
                {
                    collection.PRIMARY_FIELD: str(record["id"]),
                    collection.DOCUMENT_FIELD: record["document"],
                    collection.METADATA_FIELD: record["metadata"],
                    collection.EMBEDDING_FIELD: record["embedding"],
                }
            )
            if len(batch) >= args.batch_size:
                batch_imported, batch_skipped = collection.import_records(batch, resume=args.resume)
                imported += batch_imported
                skipped += batch_skipped
                batch.clear()

        if batch:
            batch_imported, batch_skipped = collection.import_records(batch, resume=args.resume)
            imported += batch_imported
            skipped += batch_skipped

        final_count = collection.count()
        expected_count = manifest.get("count")
        if final_count != expected_count:
            raise ValueError(
                f"Post-import verification failed for '{args.collection_name}': expected {expected_count} rows, found {final_count}."
            )

        logger.info(
            "Imported %s records into Milvus collection %s (%s reused from resume)",
            imported,
            args.collection_name,
            skipped,
        )
        return 0
    finally:
        collection.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export a Chroma advertisement catalog and import it into Milvus.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="Export the existing Chroma collection to an NDJSON backup file.")
    export_parser.add_argument("--host", default=os.getenv("ASE_CHROMADB_HOST", "ase-chromadb"))
    export_parser.add_argument("--port", type=int, default=int(os.getenv("ASE_CHROMADB_PORT", "8000")))
    export_parser.add_argument("--collection-name", default=os.getenv("ASE_COLLECTION_NAME", "ase_collection"))
    export_parser.add_argument("--output", required=True)
    export_parser.add_argument("--batch-size", type=int, default=128)
    export_parser.set_defaults(func=export_chroma)

    import_parser = subparsers.add_parser("import", help="Import an NDJSON backup file into the configured Milvus collection.")
    import_parser.add_argument("--input", required=True)
    import_parser.add_argument("--uri", default=os.getenv("ASE_MILVUS_URI", "http://ase-milvus:19530"))
    import_parser.add_argument("--token", default=os.getenv("ASE_MILVUS_TOKEN"))
    import_parser.add_argument("--collection-name", default=os.getenv("ASE_COLLECTION_NAME", "ase_collection"))
    import_parser.add_argument("--model-path", default=os.getenv("ASE_MODEL_PATH", "/opt/models/all-MiniLM-L12-v2"))
    import_parser.add_argument("--model-id", default=os.getenv("ASE_EMBEDDING_MODEL_ID", "sentence-transformers/all-MiniLM-L12-v2"))
    import_parser.add_argument("--batch-size", type=int, default=128)
    import_parser.add_argument("--resume", action="store_true", help="Allow a safe resume into the same dedicated target after a partial import.")
    import_parser.set_defaults(func=import_milvus)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
