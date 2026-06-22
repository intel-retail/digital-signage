import base64
import io
from types import SimpleNamespace

from PIL import Image
import pytest

flask = pytest.importorskip("flask")
pytest.importorskip("flask_restx")
Flask = flask.Flask

from server.apis import api
from server.apis import predefinedads
from server.apis import version


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["TESTING"] = True
    api.init_app(app)
    return app.test_client()


def _jpeg_b64() -> str:
    img = Image.new("RGB", (16, 16), "white")
    buff = io.BytesIO()
    img.save(buff, format="JPEG")
    return base64.b64encode(buff.getvalue()).decode("utf-8")


def _png_b64() -> str:
    img = Image.new("RGBA", (16, 16), (0, 255, 0, 255))
    buff = io.BytesIO()
    img.save(buff, format="PNG")
    return base64.b64encode(buff.getvalue()).decode("utf-8")


def test_status_endpoint_returns_ok(client):
    resp = client.get("/aig/hstatus/7")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["status"] == "ok"
    assert payload["id"] == 7


def test_versions_endpoint_returns_marshaled_items(client, monkeypatch):
    fake_versions = [
        SimpleNamespace(
            component="AIG Server",
            version="0.1.0",
            observation="test",
            lastverification="2026-06-22 10:00",
        )
    ]
    monkeypatch.setattr(version.ServerEnvironment, "get_aig_with_dependencies", lambda: fake_versions)

    resp = client.get("/aig/versions")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert isinstance(payload, list)
    assert payload[0]["component"] == "AIG Server"


def test_predef_post_rejects_invalid_base64(client):
    resp = client.post(
        "/ase/predef/",
        json={"id": 1, "description": "bad", "imgb64": "not-b64", "source": "test"},
    )

    assert resp.status_code == 400
    assert "Invalid base64 image" in resp.get_json()["error"]


def test_predef_post_adds_new_record_with_valid_jpeg(client, monkeypatch):
    class FakeAseServer:
        def __init__(self):
            self.add_called = False
            self.add_args = None

        def chromadb_exists(self, image_id):
            return False

        def chromadb_add(self, image_id, description, image, source):
            self.add_called = True
            self.add_args = (image_id, description, image, source)

    fake_server = FakeAseServer()
    monkeypatch.setattr(predefinedads, "AseServerMetadata", lambda: fake_server)

    resp = client.post(
        "/ase/predef/",
        json={
            "id": 42,
            "description": "fresh fruit",
            "imgb64": _jpeg_b64(),
            "source": "marketing",
        },
    )

    assert resp.status_code == 200
    assert resp.get_json()["message"] == "Success"
    assert fake_server.add_called is True
    assert fake_server.add_args[0] == 42
    assert fake_server.add_args[1] == "fresh fruit"
    assert isinstance(fake_server.add_args[2], Image.Image)
    assert fake_server.add_args[3] == "marketing"


def test_predef_query_ad_returns_empty_when_no_results_and_no_default(client, monkeypatch):
    class FakeAseServer:
        default_ad_image = None

        def chromadb_querytxt(self, query, n_results=1):
            return []

    monkeypatch.setattr(predefinedads, "AseServerMetadata", lambda: FakeAseServer())

    resp = client.post(
        "/ase/predef/query/ad",
        json={"query": "oranges", "n_results": 1, "use_default_ad_onempty": False},
    )

    assert resp.status_code == 200
    assert resp.get_json() == []


def test_minf_requires_description_in_payload(client):
    resp = client.post("/aig/minf/", json={"device": "CPU"})

    assert resp.status_code == 400


def test_security_disallows_unsupported_http_methods(client):
    assert client.get("/ase/predef/").status_code == 405
    assert client.delete("/aig/versions").status_code == 405
    assert client.put("/aig/hstatus/7", json={"id": 7}).status_code == 405


def test_security_rejects_non_jpeg_payload_for_predef_upload(client):
    resp = client.post(
        "/ase/predef/",
        json={
            "id": 77,
            "description": "png payload",
            "imgb64": _png_b64(),
            "source": "security-test",
        },
    )

    assert resp.status_code == 400
    assert "Unsupported image format" in resp.get_json()["error"]


def test_security_rejects_hstatus_non_numeric_path_input(client):
    # Route-level integer constraint should block non-numeric/injection-like path values.
    resp = client.get("/aig/hstatus/1%20OR%201=1")

    assert resp.status_code == 404


def test_security_predef_query_ad_rejects_empty_query_before_backend_init(client, monkeypatch):
    def _backend_should_not_be_called():
        raise AssertionError("AseServerMetadata should not be instantiated for empty query")

    monkeypatch.setattr(predefinedads, "AseServerMetadata", _backend_should_not_be_called)

    resp = client.post(
        "/ase/predef/query/ad",
        json={"query": "", "n_results": 1, "use_default_ad_onempty": True},
    )

    assert resp.status_code == 500
