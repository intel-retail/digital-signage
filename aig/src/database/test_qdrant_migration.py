import os
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from qdrant_client import models

sys.modules.setdefault(
    "PIL",
    types.SimpleNamespace(Image=types.SimpleNamespace(Image=object, open=lambda *args, **kwargs: None))
)
sys.modules.setdefault("sentence_transformers", types.SimpleNamespace(SentenceTransformer=object))
sys.modules.setdefault("openvino_genai", types.SimpleNamespace(Text2ImagePipeline=object))
sys.modules.setdefault("openvino", types.SimpleNamespace(Core=lambda: SimpleNamespace(available_devices=[])))

from database.version import AseServerMetadata


class TestQdrantMigration(unittest.TestCase):
    def tearDown(self):
        if hasattr(AseServerMetadata, "instance"):
            delattr(AseServerMetadata, "instance")

    def test_distance_threshold_legacy_value_is_translated_to_similarity(self):
        with patch.dict(os.environ, {"ASE_DISTANCE_MAX_THRESHOLD": "0.2"}, clear=True):
            self.assertEqual(AseServerMetadata.get_ase_distance_threshold(), 0.8)

    def test_qdrant_match_keeps_boundary_scores(self):
        with patch.dict(os.environ, {"ASE_QDRANT_SCORE_MIN_THRESHOLD": "0.8"}, clear=True):
            self.assertFalse(AseServerMetadata.is_qdrant_match(0.79))
            self.assertTrue(AseServerMetadata.is_qdrant_match(0.8))
            self.assertTrue(AseServerMetadata.is_qdrant_match(0.81))

    def test_initialize_qdrant_creates_missing_collection(self):
        mock_client = Mock()
        mock_client.collection_exists.return_value = False
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 3

        with patch("database.version.QdrantClient", return_value=mock_client), \
             patch("database.version.SentenceTransformer", return_value=mock_model), \
             patch.object(AseServerMetadata, "process_sample_data", return_value=None):
            metadata = AseServerMetadata()

            self.assertEqual(metadata.collection, AseServerMetadata.get_ase_collection_name())
            mock_client.create_collection.assert_called_once()

    def test_initialize_qdrant_rejects_incompatible_existing_collection(self):
        mock_client = Mock()
        mock_client.collection_exists.return_value = True
        mock_client.get_collection.return_value = SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(
                    vectors=SimpleNamespace(size=4, distance=models.Distance.COSINE)
                )
            )
        )
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 3

        with patch("database.version.QdrantClient", return_value=mock_client), \
             patch("database.version.SentenceTransformer", return_value=mock_model), \
             patch.object(AseServerMetadata, "process_sample_data", return_value=None):
            metadata = AseServerMetadata()

            self.assertIsNone(metadata.collection)
            mock_client.get_collection.assert_called_once_with(collection_name=AseServerMetadata.get_ase_collection_name())


if __name__ == "__main__":
    unittest.main()
