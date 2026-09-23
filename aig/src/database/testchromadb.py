import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

PROJECT_SRC = Path(__file__).resolve().parents[1]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from database.milvus_collection import (  # pylint: disable=wrong-import-position
    DuplicateIdError,
    MilvusAdvertisementCollection,
    MilvusConfigurationError,
)

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
            "ten-away": [6.0, 8.0],
            "query-origin": [0.0, 0.0],
        }
        return np.asarray([mapping[text] for text in texts], dtype=np.float32)


@unittest.skipUnless(MILVUS_LITE_AVAILABLE, "milvus-lite is required for Milvus integration tests")
class MilvusCollectionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="ase-milvus-test-")
        self.db_path = os.path.join(self.temp_dir, "milvus.db")
        self.contract_dir = os.path.join(self.temp_dir, "contracts")
        self.embedding_provider = FakeEmbeddingProvider()
        self.collection = MilvusAdvertisementCollection(
            uri=self.db_path,
            token=None,
            collection_name="ase_collection_test",
            embedding_provider=self.embedding_provider,
            contract_dir=self.contract_dir,
        )

    def tearDown(self):
        self.collection.close()
        shutil.rmtree(self.temp_dir)

    def test_add_get_query_and_delete_preserve_shapes(self):
        self.collection.add(
            ids=["10", "20"],
            documents=["origin", "five-away"],
            metadatas=[{"description": "origin", "img_path": "/tmp/10.jpg"}, {"description": "five-away", "img_path": "/tmp/20.jpg"}],
        )

        get_result = self.collection.get(ids=["20", "10"])
        self.assertEqual(get_result["ids"], ["20", "10"])
        self.assertEqual(get_result["documents"], ["five-away", "origin"])
        self.assertEqual(get_result["metadatas"][0]["img_path"], "/tmp/20.jpg")

        query_result = self.collection.query(query_texts=["query-origin"], n_results=2)
        self.assertEqual(query_result["ids"], [["10", "20"]])
        self.assertEqual(query_result["documents"], [["origin", "five-away"]])
        self.assertEqual(query_result["distances"], [[0.0, 25.0]])

        self.collection.delete(ids=["10"])
        self.assertEqual(self.collection.get(ids=["10"])["ids"], [])

    def test_duplicate_add_is_rejected(self):
        self.collection.add(
            ids=["10"],
            documents=["origin"],
            metadatas=[{"description": "origin", "img_path": "/tmp/10.jpg"}],
        )

        with self.assertRaises(DuplicateIdError):
            self.collection.add(
                ids=["10"],
                documents=["origin"],
                metadatas=[{"description": "origin", "img_path": "/tmp/10.jpg"}],
            )

    def test_embedding_validation_rejects_nan_and_dimension_mismatch(self):
        with self.assertRaises(ValueError):
            self.collection.add(
                ids=["10"],
                documents=["origin"],
                metadatas=[{"description": "origin", "img_path": "/tmp/10.jpg"}],
                embeddings=[[float("nan"), 0.0]],
            )

        with self.assertRaises(ValueError):
            self.collection.add(
                ids=["10"],
                documents=["origin"],
                metadatas=[{"description": "origin", "img_path": "/tmp/10.jpg"}],
                embeddings=[[0.0, 0.0, 1.0]],
            )

    def test_reopen_validates_persistence_and_contract(self):
        self.collection.add(
            ids=["10"],
            documents=["origin"],
            metadatas=[{"description": "origin", "img_path": "/tmp/10.jpg"}],
        )
        self.collection.close()

        reopened = MilvusAdvertisementCollection(
            uri=self.db_path,
            token=None,
            collection_name="ase_collection_test",
            embedding_provider=self.embedding_provider,
            contract_dir=self.contract_dir,
        )
        try:
            get_result = reopened.get(ids=["10"])
            self.assertEqual(get_result["ids"], ["10"])
            self.assertEqual(get_result["documents"], ["origin"])
        finally:
            reopened.close()

    def test_contract_dimension_mismatch_fails_cleanly(self):
        self.collection.close()

        class WrongDimensionEmbeddingProvider(FakeEmbeddingProvider):
            def __init__(self):
                super().__init__()
                self.dimension = 3

            def encode(self, texts):
                return np.asarray([[0.0, 0.0, 0.0] for _ in texts], dtype=np.float32)

        with self.assertRaises(MilvusConfigurationError):
            MilvusAdvertisementCollection(
                uri=self.db_path,
                token=None,
                collection_name="ase_collection_test",
                embedding_provider=WrongDimensionEmbeddingProvider(),
                contract_dir=self.contract_dir,
            )


if __name__ == "__main__":
    unittest.main()
