import base64
import io
import sys
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

PROJECT_SRC = Path(__file__).resolve().parents[1]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

if "openvino_genai" not in sys.modules:
    stub = types.ModuleType("openvino_genai")
    stub.Text2ImagePipeline = object
    sys.modules["openvino_genai"] = stub

if "openvino" not in sys.modules:
    stub = types.ModuleType("openvino")

    class _Core:  # pylint: disable=too-few-public-methods
        available_devices = ["CPU"]

    stub.Core = _Core
    sys.modules["openvino"] = stub

from server.aig_server import AigServer  # pylint: disable=wrong-import-position
from server.apis import predefinedads  # pylint: disable=wrong-import-position
from database import version as version_module  # pylint: disable=wrong-import-position


class FakeAseServer:
    exists_value = False
    get_value = None
    query_value = None
    default_ad_image = Image.new("RGB", (4, 4), color="blue")
    add_calls = []
    update_calls = []
    remove_calls = []

    def __init__(self):
        self.default_ad_image = FakeAseServer.default_ad_image

    @staticmethod
    def reset():
        FakeAseServer.exists_value = False
        FakeAseServer.get_value = None
        FakeAseServer.query_value = None
        FakeAseServer.default_ad_image = Image.new("RGB", (4, 4), color="blue")
        FakeAseServer.add_calls = []
        FakeAseServer.update_calls = []
        FakeAseServer.remove_calls = []

    @staticmethod
    def get_ase_img_id():
        return 99

    @staticmethod
    def get_ase_distance_threshold():
        return 0.2

    def chromadb_exists(self, _id):
        return FakeAseServer.exists_value

    def chromadb_add(self, image_id, description, image, source):
        FakeAseServer.add_calls.append((image_id, description, image.size, source))
        return True

    def chromadb_update(self, image_id, description, image, source):
        FakeAseServer.update_calls.append((image_id, description, image.size, source))
        return True

    def chromadb_remove(self, image_id):
        FakeAseServer.remove_calls.append(image_id)
        return True

    def chromadb_get(self, _id):
        return FakeAseServer.get_value

    def chromadb_querytxt(self, _query, n_results=1):
        return FakeAseServer.query_value

    def get_image_file_from_path(self, _path):
        return Image.new("RGB", (4, 4), color="red")

    def get_logo(self):
        return None


class PredefinedAdsApiTests(unittest.TestCase):
    def setUp(self):
        FakeAseServer.reset()
        self.ase_patch = mock.patch.object(predefinedads, "AseServerMetadata", FakeAseServer)
        self.ase_patch.start()
        self.client = AigServer().app.test_client()

    def tearDown(self):
        self.ase_patch.stop()

    @staticmethod
    def _jpeg_base64(color="green"):
        image = Image.new("RGB", (4, 4), color=color)
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def test_post_creates_new_predefined_ad(self):
        payload = {
            "id": 12,
            "description": "fresh fruit",
            "imgb64": self._jpeg_base64(),
            "source": "marketing",
        }
        response = self.client.post("/ase/predef/", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(FakeAseServer.add_calls, [(12, "fresh fruit", (4, 4), "marketing")])
        self.assertEqual(FakeAseServer.update_calls, [])

    def test_get_handles_multi_digit_identifier(self):
        FakeAseServer.exists_value = True
        FakeAseServer.get_value = {
            "ids": ["12"],
            "metadatas": [{"description": "fruit ad", "img_path": "/tmp/12.jpg", "source": "marketing"}],
            "documents": ["fruit ad"],
        }

        response = self.client.get("/ase/predef/12")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["id"], 12)
        self.assertEqual(body["description"], "fruit ad")
        self.assertEqual(body["source"], "marketing")
        self.assertTrue(body["imgb64"])

    def test_query_returns_matching_records_below_threshold(self):
        FakeAseServer.query_value = {
            "ids": [["12"]],
            "metadatas": [[{"description": "fruit ad", "img_path": "/tmp/12.jpg", "source": "marketing"}]],
            "documents": [["fruit ad"]],
            "distances": [[0.1]],
        }

        response = self.client.post("/ase/predef/query", json={"query": "fruit", "n_results": 1})
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["id"], 12)
        self.assertEqual(body[0]["source"], "marketing")

    def test_firstad_falls_back_to_default_image(self):
        FakeAseServer.query_value = {
            "ids": [["12"]],
            "metadatas": [[{"description": "fruit ad", "img_path": "/tmp/12.jpg", "source": "marketing"}]],
            "documents": [["fruit ad"]],
            "distances": [[1.0]],
        }

        response = self.client.post(
            "/ase/predef/query/firstad",
            json={"query": "fruit", "n_results": 1, "use_default_ad_onempty": True},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/jpeg")
        image = Image.open(io.BytesIO(response.data))
        self.assertEqual(image.size, (4, 4))


class AseServerMetadataInitializationTests(unittest.TestCase):
    def setUp(self):
        if hasattr(version_module.AseServerMetadata, "instance"):
            delattr(version_module.AseServerMetadata, "instance")

    def tearDown(self):
        if hasattr(version_module.AseServerMetadata, "instance"):
            delattr(version_module.AseServerMetadata, "instance")

    def test_lazy_initialization_runs_once_under_concurrency(self):
        initialize_calls = []
        sample_calls = []

        def fake_initialize(self):
            initialize_calls.append("init")
            return object()

        def fake_sample(self):
            sample_calls.append("sample")

        with mock.patch.object(version_module.AseServerMetadata, "_initialize_chromadb", fake_initialize), mock.patch.object(
            version_module.AseServerMetadata, "process_sample_data", fake_sample
        ), mock.patch.object(version_module.AigServerMetadata, "get_logo_path", return_value=None), mock.patch.object(
            version_module.AseServerMetadata, "get_ase_default_ad_img", return_value="/does/not/exist.jpg"
        ):
            server = version_module.AseServerMetadata()
            threads = [threading.Thread(target=lambda: server.collection) for _ in range(5)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertEqual(len(initialize_calls), 1)
        self.assertEqual(len(sample_calls), 1)


if __name__ == "__main__":
    unittest.main()
