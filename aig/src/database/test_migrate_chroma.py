import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

PROJECT_SRC = Path(__file__).resolve().parents[1]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from database import migrate_chroma  # pylint: disable=wrong-import-position
from database.milvus_collection import MilvusAdvertisementCollection, MilvusConfigurationError  # pylint: disable=wrong-import-position

MILVUS_LITE_AVAILABLE = True
try:
    import milvus_lite  # noqa: F401 pylint: disable=unused-import
except ImportError:  # pragma: no cover - exercised through skipIf
    MILVUS_LITE_AVAILABLE = False


class FakeEmbeddingProvider:
    def __init__(self):
        self.dimension = 2
        self.model_path = "/tmp/fake-model"
        self.model_id = "fake-model"
        self.fingerprint = "fake-fingerprint"
        self.normalize_embeddings = False
        self.precision = "float32"

    def encode(self, texts):
        mapping = {
            "origin": [0.0, 0.0],
            "five-away": [3.0, 4.0],
        }
        return np.asarray([mapping[text] for text in texts], dtype=np.float32)


class MigrationUtilityUnitTests(unittest.TestCase):
    def test_extract_metric_reads_chroma_configuration(self):
        self.assertEqual(migrate_chroma._extract_chroma_metric({"hnsw": {"space": "l2"}}), "l2")
        self.assertEqual(migrate_chroma._extract_chroma_metric({"hnsw": {"space": "cosine"}}), "cosine")

    def test_embedding_validation_detects_mismatch(self):
        temp_dir = tempfile.mkdtemp(prefix="ase-migrate-test-")
        try:
            backup_path = Path(temp_dir) / "backup.ndjson"
            backup_path.write_text(
                "\n".join(
                    [
                        json.dumps({"type": "manifest", "metric": "l2", "count": 1}),
                        json.dumps(
                            {
                                "type": "record",
                                "id": "10",
                                "document": "origin",
                                "metadata": {"description": "origin"},
                                "embedding": [9.0, 9.0],
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                migrate_chroma._validate_backup_against_embedding_model(backup_path, FakeEmbeddingProvider(), 16)
        finally:
            shutil.rmtree(temp_dir)


@unittest.skipUnless(MILVUS_LITE_AVAILABLE, "milvus-lite is required for Milvus migration integration tests")
class MigrationUtilityIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="ase-migrate-milvus-")
        self.db_path = os.path.join(self.temp_dir, "milvus.db")
        self.contract_dir = os.path.join(self.temp_dir, "contracts")
        self.backup_path = os.path.join(self.temp_dir, "backup.ndjson")
        self.original_contract_dir = os.environ.get("ASE_MILVUS_CONTRACT_DIR")
        os.environ["ASE_MILVUS_CONTRACT_DIR"] = self.contract_dir

    def tearDown(self):
        if self.original_contract_dir is None:
            os.environ.pop("ASE_MILVUS_CONTRACT_DIR", None)
        else:
            os.environ["ASE_MILVUS_CONTRACT_DIR"] = self.original_contract_dir
        shutil.rmtree(self.temp_dir)

    def _write_backup(self, *, count=1, records=None, metric="l2"):
        records = records or [
            {
                "id": "10",
                "document": "origin",
                "metadata": {"description": "origin", "img_path": "/tmp/10.jpg"},
                "embedding": [0.0, 0.0],
            }
        ]
        lines = [json.dumps({"type": "manifest", "metric": metric, "count": count})]
        lines.extend(json.dumps({"type": "record", **record}) for record in records)
        Path(self.backup_path).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _build_args(self, resume=False):
        return SimpleNamespace(
            input=self.backup_path,
            uri=self.db_path,
            token=None,
            collection_name="ase_collection_test",
            model_path="/tmp/fake-model",
            model_id="fake-model",
            batch_size=8,
            resume=resume,
        )

    def test_import_rejects_partial_backup(self):
        self._write_backup(count=2)
        with mock.patch.object(migrate_chroma, "LocalSentenceTransformerEmbeddings", return_value=FakeEmbeddingProvider()):
            with self.assertRaises(ValueError):
                migrate_chroma.import_milvus(self._build_args())

    def test_resume_import_rejects_conflicting_existing_rows(self):
        self._write_backup()
        collection = MilvusAdvertisementCollection(
            uri=self.db_path,
            token=None,
            collection_name="ase_collection_test",
            embedding_provider=FakeEmbeddingProvider(),
            contract_dir=self.contract_dir,
        )
        collection.add(
            ids=["10"],
            documents=["origin"],
            metadatas=[{"description": "different", "img_path": "/tmp/10.jpg"}],
        )
        collection.close()

        with mock.patch.object(migrate_chroma, "LocalSentenceTransformerEmbeddings", return_value=FakeEmbeddingProvider()):
            with self.assertRaises(MilvusConfigurationError):
                migrate_chroma.import_milvus(self._build_args(resume=True))

    def test_resume_import_allows_identical_existing_rows(self):
        self._write_backup()
        collection = MilvusAdvertisementCollection(
            uri=self.db_path,
            token=None,
            collection_name="ase_collection_test",
            embedding_provider=FakeEmbeddingProvider(),
            contract_dir=self.contract_dir,
        )
        collection.add(
            ids=["10"],
            documents=["origin"],
            metadatas=[{"description": "origin", "img_path": "/tmp/10.jpg"}],
        )
        collection.close()

        with mock.patch.object(migrate_chroma, "LocalSentenceTransformerEmbeddings", return_value=FakeEmbeddingProvider()):
            exit_code = migrate_chroma.import_milvus(self._build_args(resume=True))
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
