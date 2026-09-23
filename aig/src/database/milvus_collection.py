import hashlib
import json
import logging
import math
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

import numpy as np
from pymilvus import DataType, MilvusClient

logger = logging.getLogger(__name__)

_COLLECTION_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class MilvusConfigurationError(ValueError):
    """Raised when the configured Milvus collection is incompatible with ASE."""


class DuplicateIdError(ValueError):
    """Raised when a caller attempts to add an existing identifier."""


@dataclass(frozen=True)
class EmbeddingContract:
    collection_name: str
    embedding_dimension: int
    embedding_field: str
    document_field: str
    metadata_field: str
    primary_field: str
    index_type: str
    metric_type: str
    consistency_level: str
    model_path: str
    model_id: str
    model_fingerprint: str
    normalize_embeddings: bool
    precision: str

    def to_dict(self) -> dict:
        return {
            "collection_name": self.collection_name,
            "embedding_dimension": self.embedding_dimension,
            "embedding_field": self.embedding_field,
            "document_field": self.document_field,
            "metadata_field": self.metadata_field,
            "primary_field": self.primary_field,
            "index_type": self.index_type,
            "metric_type": self.metric_type,
            "consistency_level": self.consistency_level,
            "model_path": self.model_path,
            "model_id": self.model_id,
            "model_fingerprint": self.model_fingerprint,
            "normalize_embeddings": self.normalize_embeddings,
            "precision": self.precision,
        }


class LocalSentenceTransformerEmbeddings:
    def __init__(self, model_path: str, model_id: Optional[str] = None):
        if not model_path:
            raise MilvusConfigurationError("ASE_MODEL_PATH must be configured for Milvus embeddings.")

        from sentence_transformers import SentenceTransformer

        self.model_path = model_path
        self.model_id = model_id or model_path
        self.normalize_embeddings = False
        self.precision = "float32"
        self._model = SentenceTransformer(model_path, device="cpu")
        probe = self.encode(["embedding probe"])
        if probe.ndim != 2 or probe.shape[0] != 1:
            raise MilvusConfigurationError("SentenceTransformer did not return a 2D embedding matrix.")
        self.dimension = int(probe.shape[1])
        self.fingerprint = self._fingerprint_model(model_path)

    @staticmethod
    def _fingerprint_model(model_path: str) -> str:
        path = Path(model_path)
        digest = hashlib.sha256()
        digest.update(str(path).encode("utf-8"))
        if path.exists() and path.is_dir():
            fingerprint_candidates = [
                "config_sentence_transformers.json",
                "modules.json",
                "config.json",
                "sentence_bert_config.json",
                "tokenizer_config.json",
                "special_tokens_map.json",
                "tokenizer.json",
                "vocab.txt",
                "vocab.json",
                "merges.txt",
            ]
            for relative_name in fingerprint_candidates:
                candidate = path / relative_name
                if candidate.exists() and candidate.is_file():
                    digest.update(relative_name.encode("utf-8"))
                    digest.update(candidate.read_bytes())
        return digest.hexdigest()

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        embeddings = self._model.encode(
            list(texts),
            batch_size=min(max(len(texts), 1), 32),
            convert_to_numpy=True,
            normalize_embeddings=False,
            precision=self.precision,
            show_progress_bar=False,
        )
        matrix = np.asarray(embeddings, dtype=np.float32)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        return matrix


class MilvusAdvertisementCollection:
    PRIMARY_FIELD = "id"
    DOCUMENT_FIELD = "document"
    METADATA_FIELD = "metadata"
    EMBEDDING_FIELD = "embedding"
    ID_MAX_LENGTH = 128
    DOCUMENT_MAX_LENGTH = 65535
    INDEX_TYPE = "FLAT"
    METRIC_TYPE = "L2"
    CONSISTENCY_LEVEL = "Strong"

    def __init__(
        self,
        *,
        uri: str,
        token: Optional[str],
        collection_name: str,
        embedding_provider,
        contract_dir: Optional[str] = None,
    ):
        self._uri = uri
        self._token = token or None
        self._collection_name = self._validate_collection_name(collection_name)
        self._embedding_provider = embedding_provider
        self._embedding_dimension = int(getattr(embedding_provider, "dimension", 0))
        if self._embedding_dimension <= 0:
            raise MilvusConfigurationError("Embedding provider returned an invalid dimension.")
        self._client = MilvusClient(uri=uri, token=self._token)
        self._contract_dir = Path(contract_dir or os.getenv("ASE_MILVUS_CONTRACT_DIR", "/opt/sharedata/milvus_contracts"))
        self._contract = EmbeddingContract(
            collection_name=self._collection_name,
            embedding_dimension=self._embedding_dimension,
            embedding_field=self.EMBEDDING_FIELD,
            document_field=self.DOCUMENT_FIELD,
            metadata_field=self.METADATA_FIELD,
            primary_field=self.PRIMARY_FIELD,
            index_type=self.INDEX_TYPE,
            metric_type=self.METRIC_TYPE,
            consistency_level=self.CONSISTENCY_LEVEL,
            model_path=getattr(embedding_provider, "model_path", ""),
            model_id=getattr(embedding_provider, "model_id", ""),
            model_fingerprint=getattr(embedding_provider, "fingerprint", ""),
            normalize_embeddings=bool(getattr(embedding_provider, "normalize_embeddings", False)),
            precision=str(getattr(embedding_provider, "precision", "float32")),
        )
        self._ensure_collection()

    @property
    def collection_name(self) -> str:
        return self._collection_name

    @property
    def contract(self) -> EmbeddingContract:
        return self._contract

    def close(self) -> None:
        self._client.close()

    def heartbeat(self):
        return self._client.get_server_version()

    def count(self) -> int:
        stats = self._client.get_collection_stats(self._collection_name)
        return int(stats.get("row_count", 0))

    def add(self, *, documents: Sequence[str], metadatas: Sequence[dict], ids: Sequence[str], embeddings: Optional[Sequence[Sequence[float]]] = None) -> dict:
        clean_ids = self._normalize_ids(ids)
        clean_documents = self._normalize_documents(documents)
        clean_metadatas = self._normalize_metadatas(metadatas)
        self._validate_parallel_lengths(clean_ids, clean_documents, clean_metadatas)

        existing_ids = set(self.get(ids=clean_ids).get("ids", []))
        if existing_ids:
            raise DuplicateIdError(f"Duplicate identifier(s) already exist: {sorted(existing_ids)}")

        embedding_matrix = self._coerce_embeddings(
            embeddings if embeddings is not None else self._embedding_provider.encode(clean_documents),
            expected_rows=len(clean_ids),
        )

        payload = []
        for row_id, document, metadata, embedding in zip(clean_ids, clean_documents, clean_metadatas, embedding_matrix):
            payload.append(
                {
                    self.PRIMARY_FIELD: row_id,
                    self.DOCUMENT_FIELD: document,
                    self.METADATA_FIELD: metadata,
                    self.EMBEDDING_FIELD: embedding.tolist(),
                }
            )

        result = self._client.insert(self._collection_name, payload)
        self._client.flush(self._collection_name)
        return result

    def get(self, *, ids: Sequence[str], include_embeddings: bool = False) -> dict:
        clean_ids = self._normalize_ids(ids)
        output_fields = [self.DOCUMENT_FIELD, self.METADATA_FIELD]
        if include_embeddings:
            output_fields.append(self.EMBEDDING_FIELD)

        rows = list(self._client.get(self._collection_name, clean_ids, output_fields=output_fields))
        by_id = {str(row[self.PRIMARY_FIELD]): row for row in rows}
        ordered_rows = [by_id[row_id] for row_id in clean_ids if row_id in by_id]
        result = {
            "ids": [str(row[self.PRIMARY_FIELD]) for row in ordered_rows],
            "documents": [row.get(self.DOCUMENT_FIELD) for row in ordered_rows],
            "metadatas": [row.get(self.METADATA_FIELD) for row in ordered_rows],
            "included": ["documents", "metadatas"],
        }
        if include_embeddings:
            result["embeddings"] = [row.get(self.EMBEDDING_FIELD) for row in ordered_rows]
            result["included"].append("embeddings")
        return result

    def get_rows(self, *, ids: Sequence[str], include_embeddings: bool = False) -> list[dict]:
        result = self.get(ids=ids, include_embeddings=include_embeddings)
        rows = []
        for index, row_id in enumerate(result.get("ids", [])):
            row = {
                self.PRIMARY_FIELD: row_id,
                self.DOCUMENT_FIELD: result["documents"][index],
                self.METADATA_FIELD: result["metadatas"][index],
            }
            if include_embeddings:
                row[self.EMBEDDING_FIELD] = result["embeddings"][index]
            rows.append(row)
        return rows

    def delete(self, *, ids: Sequence[str]):
        clean_ids = self._normalize_ids(ids)
        result = self._client.delete(self._collection_name, ids=clean_ids)
        self._client.flush(self._collection_name)
        return result

    def query(self, *, query_texts: Sequence[str], n_results: int = 3) -> dict:
        if not isinstance(query_texts, Sequence) or isinstance(query_texts, (str, bytes)) or len(query_texts) == 0:
            raise ValueError("query_texts must be a non-empty list.")
        if n_results < 1:
            raise ValueError("n_results must be at least 1.")

        embeddings = self._coerce_embeddings(self._embedding_provider.encode(list(query_texts)), expected_rows=len(query_texts))
        raw_results = self._client.search(
            self._collection_name,
            data=embeddings.tolist(),
            limit=n_results,
            output_fields=[self.DOCUMENT_FIELD, self.METADATA_FIELD],
            search_params={"metric_type": self.METRIC_TYPE, "params": {}},
            anns_field=self.EMBEDDING_FIELD,
        )

        ids = []
        documents = []
        metadatas = []
        distances = []
        for hit_list in raw_results:
            query_ids = []
            query_documents = []
            query_metadatas = []
            query_distances = []
            for hit in hit_list:
                entity = hit.get("entity", {})
                query_ids.append(str(hit.get("id")))
                query_documents.append(entity.get(self.DOCUMENT_FIELD))
                query_metadatas.append(entity.get(self.METADATA_FIELD))
                query_distances.append(hit.get("distance"))
            ids.append(query_ids)
            documents.append(query_documents)
            metadatas.append(query_metadatas)
            distances.append(query_distances)

        return {
            "ids": ids,
            "documents": documents,
            "metadatas": metadatas,
            "distances": distances,
            "included": ["documents", "metadatas", "distances"],
        }

    def import_records(self, records: Sequence[dict], *, resume: bool = False) -> tuple[int, int]:
        if not records:
            return 0, 0

        ids = [str(record[self.PRIMARY_FIELD]) for record in records]
        existing_rows = {row[self.PRIMARY_FIELD]: row for row in self.get_rows(ids=ids, include_embeddings=True)}
        rows_to_insert = []
        skipped = 0
        for record in records:
            row_id = str(record[self.PRIMARY_FIELD])
            current = existing_rows.get(row_id)
            if current is None:
                rows_to_insert.append(record)
                continue
            if not resume:
                raise DuplicateIdError(f"Target Milvus collection already contains ID {row_id}.")
            if not self._rows_match(current, record):
                raise MilvusConfigurationError(f"Existing Milvus row for ID {row_id} conflicts with the import payload.")
            skipped += 1

        if rows_to_insert:
            self.add(
                ids=[record[self.PRIMARY_FIELD] for record in rows_to_insert],
                documents=[record[self.DOCUMENT_FIELD] for record in rows_to_insert],
                metadatas=[record[self.METADATA_FIELD] for record in rows_to_insert],
                embeddings=[record[self.EMBEDDING_FIELD] for record in rows_to_insert],
            )
        return len(rows_to_insert), skipped

    def _rows_match(self, existing: dict, incoming: dict) -> bool:
        if existing.get(self.DOCUMENT_FIELD) != incoming.get(self.DOCUMENT_FIELD):
            return False
        if existing.get(self.METADATA_FIELD) != incoming.get(self.METADATA_FIELD):
            return False
        existing_embedding = np.asarray(existing.get(self.EMBEDDING_FIELD), dtype=np.float32)
        incoming_embedding = np.asarray(incoming.get(self.EMBEDDING_FIELD), dtype=np.float32)
        return existing_embedding.shape == incoming_embedding.shape and np.allclose(existing_embedding, incoming_embedding, rtol=1e-5, atol=1e-6)

    def _ensure_collection(self) -> None:
        if not self._client.has_collection(self._collection_name):
            schema = self._client.create_schema(auto_id=False, enable_dynamic_field=False)
            schema.add_field(field_name=self.PRIMARY_FIELD, datatype=DataType.VARCHAR, is_primary=True, max_length=self.ID_MAX_LENGTH)
            schema.add_field(field_name=self.DOCUMENT_FIELD, datatype=DataType.VARCHAR, max_length=self.DOCUMENT_MAX_LENGTH)
            schema.add_field(field_name=self.METADATA_FIELD, datatype=DataType.JSON)
            schema.add_field(field_name=self.EMBEDDING_FIELD, datatype=DataType.FLOAT_VECTOR, dim=self._embedding_dimension)
            index_params = self._client.prepare_index_params()
            index_params.add_index(field_name=self.EMBEDDING_FIELD, index_type=self.INDEX_TYPE, metric_type=self.METRIC_TYPE)
            self._client.create_collection(
                collection_name=self._collection_name,
                schema=schema,
                index_params=index_params,
                consistency_level=self.CONSISTENCY_LEVEL,
            )
        self._client.load_collection(self._collection_name)
        self._validate_collection_schema()
        self._validate_contract_file()

    def _validate_collection_schema(self) -> None:
        description = self._client.describe_collection(self._collection_name)
        fields = {field["name"]: field for field in description.get("fields", [])}
        expected_types = {
            self.PRIMARY_FIELD: DataType.VARCHAR,
            self.DOCUMENT_FIELD: DataType.VARCHAR,
            self.METADATA_FIELD: DataType.JSON,
            self.EMBEDDING_FIELD: DataType.FLOAT_VECTOR,
        }
        for field_name, expected_type in expected_types.items():
            field = fields.get(field_name)
            if field is None:
                raise MilvusConfigurationError(f"Milvus collection '{self._collection_name}' is missing field '{field_name}'.")
            if field.get("type") != expected_type:
                raise MilvusConfigurationError(
                    f"Milvus collection '{self._collection_name}' field '{field_name}' has type {field.get('type')} instead of {expected_type}."
                )

        if fields[self.PRIMARY_FIELD].get("params", {}).get("max_length") != self.ID_MAX_LENGTH:
            raise MilvusConfigurationError(f"Milvus collection '{self._collection_name}' uses an unexpected ID max_length.")
        if fields[self.EMBEDDING_FIELD].get("params", {}).get("dim") != self._embedding_dimension:
            raise MilvusConfigurationError(
                f"Milvus collection '{self._collection_name}' has embedding dimension {fields[self.EMBEDDING_FIELD].get('params', {}).get('dim')} but ASE requires {self._embedding_dimension}."
            )

        if description.get("consistency_level_name") != self.CONSISTENCY_LEVEL:
            raise MilvusConfigurationError(
                f"Milvus collection '{self._collection_name}' uses consistency level {description.get('consistency_level_name')} instead of {self.CONSISTENCY_LEVEL}."
            )

        index_description = self._client.describe_index(self._collection_name, self.EMBEDDING_FIELD)
        if index_description.get("index_type") != self.INDEX_TYPE:
            raise MilvusConfigurationError(
                f"Milvus collection '{self._collection_name}' uses index {index_description.get('index_type')} instead of {self.INDEX_TYPE}."
            )
        if index_description.get("metric_type") != self.METRIC_TYPE:
            raise MilvusConfigurationError(
                f"Milvus collection '{self._collection_name}' uses metric {index_description.get('metric_type')} instead of {self.METRIC_TYPE}."
            )

    def _validate_contract_file(self) -> None:
        self._contract_dir.mkdir(parents=True, exist_ok=True)
        contract_path = self._contract_dir / f"{self._collection_name}.json"
        contract_payload = self._contract.to_dict()

        if contract_path.exists():
            existing_payload = json.loads(contract_path.read_text(encoding="utf-8"))
            if existing_payload != contract_payload:
                raise MilvusConfigurationError(
                    f"Milvus contract mismatch for '{self._collection_name}'. Existing contract does not match the configured embedding model or schema."
                )
            return

        if self.count() > 0:
            raise MilvusConfigurationError(
                f"Milvus collection '{self._collection_name}' already contains data but {contract_path} is missing. Re-import or restore the matching contract file before starting ASE."
            )

        temp_file = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self._contract_dir, delete=False)
        try:
            json.dump(contract_payload, temp_file, indent=2, sort_keys=True)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_file.close()
            os.replace(temp_file.name, contract_path)
        finally:
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)

    @classmethod
    def _validate_collection_name(cls, collection_name: str) -> str:
        if not collection_name:
            raise MilvusConfigurationError("ASE_COLLECTION_NAME must not be empty.")
        if len(collection_name) > 255 or not _COLLECTION_NAME_RE.match(collection_name):
            raise MilvusConfigurationError(
                "ASE_COLLECTION_NAME must start with a letter or underscore and contain only letters, digits, and underscores."
            )
        return collection_name

    def _normalize_ids(self, ids: Sequence[str]) -> list[str]:
        if not isinstance(ids, Sequence) or isinstance(ids, (str, bytes)) or len(ids) == 0:
            raise ValueError("ids must be a non-empty list.")
        clean_ids = []
        for row_id in ids:
            if row_id is None:
                raise ValueError("ids must not contain null values.")
            clean_id = str(row_id)
            if not clean_id:
                raise ValueError("ids must not contain empty strings.")
            if len(clean_id) > self.ID_MAX_LENGTH:
                raise ValueError(f"id '{clean_id}' exceeds the maximum supported length of {self.ID_MAX_LENGTH}.")
            clean_ids.append(clean_id)
        if len(set(clean_ids)) != len(clean_ids):
            raise ValueError("ids must be unique within a single request.")
        return clean_ids

    def _normalize_documents(self, documents: Sequence[str]) -> list[str]:
        if not isinstance(documents, Sequence) or isinstance(documents, (str, bytes)) or len(documents) == 0:
            raise ValueError("documents must be a non-empty list.")
        clean_documents = []
        for document in documents:
            if document is None:
                raise ValueError("documents must not contain null values.")
            clean_document = str(document)
            if len(clean_document) > self.DOCUMENT_MAX_LENGTH:
                raise ValueError(f"document length exceeds the maximum supported length of {self.DOCUMENT_MAX_LENGTH} characters.")
            clean_documents.append(clean_document)
        return clean_documents

    @staticmethod
    def _normalize_metadatas(metadatas: Sequence[dict]) -> list[dict]:
        if not isinstance(metadatas, Sequence) or isinstance(metadatas, (str, bytes)) or len(metadatas) == 0:
            raise ValueError("metadatas must be a non-empty list.")
        clean_metadatas = []
        for metadata in metadatas:
            if not isinstance(metadata, dict):
                raise ValueError("Each metadata item must be a dictionary.")
            clean_metadatas.append(metadata)
        return clean_metadatas

    @staticmethod
    def _validate_parallel_lengths(ids: Sequence[str], documents: Sequence[str], metadatas: Sequence[dict]) -> None:
        if not (len(ids) == len(documents) == len(metadatas)):
            raise ValueError("ids, documents, and metadatas must contain the same number of items.")

    def _coerce_embeddings(self, embeddings: Sequence[Sequence[float]], *, expected_rows: int) -> np.ndarray:
        matrix = np.asarray(embeddings, dtype=np.float32)
        if matrix.ndim != 2:
            raise ValueError("Embeddings must be a 2D matrix.")
        if matrix.shape[0] != expected_rows:
            raise ValueError(f"Expected {expected_rows} embeddings but received {matrix.shape[0]}.")
        if matrix.shape[1] != self._embedding_dimension:
            raise ValueError(
                f"Embedding dimension mismatch. Expected {self._embedding_dimension}, received {matrix.shape[1]}."
            )
        if not np.isfinite(matrix).all():
            raise ValueError("Embeddings must contain only finite values.")
        return matrix
