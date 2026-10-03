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


def test_predef_delete_not_found(client, monkeypatch):
    class FakeAseServer:
        def chromadb_exists(self, image_id):
            return False

    monkeypatch.setattr(predefinedads, "AseServerMetadata", lambda: FakeAseServer())

    resp = client.delete("/ase/predef/999")

    assert resp.status_code == 404
    assert "not found" in resp.get_json()["error"]


def test_predef_delete_with_valid_id(client, monkeypatch):
    class FakeAseServer:
        def chromadb_exists(self, image_id):
            return True

        def chromadb_remove(self, image_id):
            pass

    monkeypatch.setattr(predefinedads, "AseServerMetadata", lambda: FakeAseServer())

    resp = client.delete("/ase/predef/99")

    assert resp.status_code == 200
    assert resp.get_json()["message"] == "Success"


def test_predef_post_updates_existing_record(client, monkeypatch):
    class FakeAseServer:
        def __init__(self):
            self.update_called = False

        def chromadb_exists(self, image_id):
            return True

        def chromadb_update(self, image_id, description, image, source):
            self.update_called = True

    fake_server = FakeAseServer()
    monkeypatch.setattr(predefinedads, "AseServerMetadata", lambda: fake_server)

    resp = client.post(
        "/ase/predef/",
        json={
            "id": 50,
            "description": "updated ad",
            "imgb64": _jpeg_b64(),
            "source": "update-test",
        },
    )

    assert resp.status_code == 200
    assert fake_server.update_called is True


def test_status_endpoint_with_various_ids(client):
    """Test status endpoint accepts various numeric IDs."""
    for id_val in [1, 10, 999, 0]:
        resp = client.get(f"/aig/hstatus/{id_val}")
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["status"] == "ok"
        assert payload["id"] == id_val


def test_predef_post_with_missing_required_fields(client):
    """Test that missing required fields are rejected."""
    resp = client.post(
        "/ase/predef/",
        json={"id": 1, "imgb64": _jpeg_b64(), "source": "test"},
    )
    assert resp.status_code == 400

    resp = client.post(
        "/ase/predef/",
        json={"id": 1, "description": "test", "source": "test"},
    )
    assert resp.status_code == 400


def test_predef_post_with_empty_imgb64(client):
    """Test that empty base64 is rejected."""
    resp = client.post(
        "/ase/predef/",
        json={
            "id": 1,
            "description": "test",
            "imgb64": "",
            "source": "test",
        },
    )
    assert resp.status_code == 400


def test_predef_post_with_malformed_json(client):
    """Test that malformed JSON is rejected."""
    resp = client.post(
        "/ase/predef/",
        data="not valid json",
        content_type="application/json",
    )
    assert resp.status_code >= 400


def test_endpoint_security_methods_not_allowed(client):
    """Test that unsupported HTTP methods are rejected."""
    assert client.patch("/aig/hstatus/1").status_code == 405
    assert client.put("/aig/hstatus/1", json={}).status_code == 405
    assert client.post("/aig/hstatus/1", json={}).status_code == 405


def test_predef_query_requires_query_field(client):
    resp = client.post("/ase/predef/query", json={"n_results": 1})
    assert resp.status_code == 400


def test_predef_query_handles_incomplete_backend_response(client, monkeypatch):
    class FakeAseServer:
        def chromadb_querytxt(self, query, n_results=1):
            return {"ids": [["1"]], "metadatas": [[{"description": "x"}]]}

    monkeypatch.setattr(predefinedads, "AseServerMetadata", lambda: FakeAseServer())

    resp = client.post("/ase/predef/query", json={"query": "apple", "n_results": 1})
    assert resp.status_code == 500


def test_predef_query_returns_records_when_distance_matches(client, monkeypatch):
    class FakeAseServer:
        def chromadb_querytxt(self, query, n_results=1):
            return {
                "ids": [["101"]],
                "metadatas": [[{"description": "fresh ad", "img_path": "img_101.jpg", "source": "qa"}]],
                "distances": [[0.1]],
            }

        def get_image_file_from_path(self, path):
            return Image.new("RGB", (20, 20), "white")

    class FakeAseServerType(FakeAseServer):
        @staticmethod
        def get_ase_distance_threshold():
            return 1.5

    monkeypatch.setattr(predefinedads, "AseServerMetadata", FakeAseServerType)

    resp = client.post("/ase/predef/query", json={"query": "apple", "n_results": 1})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["id"] == 101
    assert payload[0]["description"] == "fresh ad"
    assert payload[0]["source"] == "qa"
    assert payload[0]["imgb64"]


def test_predef_query_ad_uses_default_image_when_backend_empty(client, monkeypatch):
    class FakeAseServer:
        default_ad_image = Image.new("RGB", (24, 24), "white")

        def chromadb_querytxt(self, query, n_results=1):
            return []

        def get_logo(self):
            return None

    class FakeAseServerType(FakeAseServer):
        @staticmethod
        def get_ase_distance_threshold():
            return 1.5

    monkeypatch.setattr(predefinedads, "AseServerMetadata", FakeAseServerType)

    resp = client.post(
        "/ase/predef/query/ad",
        json={"query": "orange", "n_results": 1, "use_default_ad_onempty": True},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["imgb64"]


def test_predef_query_ad_full_pipeline_with_addons(client, monkeypatch):
    class FakeAseServer:
        default_ad_image = None

        def chromadb_querytxt(self, query, n_results=1):
            return {
                "ids": [["11"]],
                "metadatas": [[{"img_path": "x.jpg"}]],
                "distances": [[0.2]],
            }

        def get_image_file_from_path(self, path):
            return Image.new("RGB", (32, 24), "white")

        def get_logo(self):
            return Image.new("RGBA", (8, 8), (0, 0, 0, 255))

    class FakeAseServerType(FakeAseServer):
        @staticmethod
        def get_ase_distance_threshold():
            return 1.5

    monkeypatch.setattr(predefinedads, "AseServerMetadata", FakeAseServerType)
    monkeypatch.setattr(predefinedads.ImgDecorator, "is_color_valid", staticmethod(lambda c: False))
    monkeypatch.setattr(predefinedads.ImgDecorator, "draw_price_circle", staticmethod(lambda img, *a, **k: img))
    monkeypatch.setattr(predefinedads.ImgDecorator, "draw_promo_rounded_rect", staticmethod(lambda img, *a, **k: img))
    monkeypatch.setattr(predefinedads.ImgDecorator, "draw_frame_double_border", staticmethod(lambda img, *a, **k: img))
    monkeypatch.setattr(predefinedads.ImgDecorator, "draw_logo", staticmethod(lambda img, *a, **k: img))
    monkeypatch.setattr(predefinedads.ImgDecorator, "draw_slogan", staticmethod(lambda img, *a, **k: img))

    resp = client.post(
        "/ase/predef/query/ad",
        json={
            "query": "milk",
            "n_results": 1,
            "use_default_ad_onempty": True,
            "price_details": {
                "price": "$1.99",
                "align": "center",
                "valign": "bottom",
                "marperc_from_border": 2,
                "font_size": 20,
                "line_width": 20,
                "price_color": "not-a-color",
                "price_in_circle": True,
                "price_circle_color": "bad",
            },
            "promo_details": {
                "promo_text": "Buy 1 Get 1",
                "text_color": "bad",
                "rect_color": "bad",
                "rect_padding": 10,
                "rect_radius": 20,
                "align": "center",
                "valign": "bottom",
                "marperc_from_border": 2,
                "font_size": 20,
                "line_width": 20,
            },
            "framed_details": {"activate": True, "marperc_from_border": 2},
            "logo_details": {"align": "left", "valign": "top", "logo_percentage": 10, "margin_px": 2},
            "slogan_details": {
                "slogan_text": "great deal",
                "text_color": "bad",
                "align": "center",
                "valign": "bottom",
                "marperc_from_border": 2,
                "font_size": 20,
                "line_width": 20,
            },
        },
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["imgb64"]


def test_predef_query_firstad_returns_jpeg(client, monkeypatch):
    class FakeAseServer:
        default_ad_image = Image.new("RGB", (30, 20), "white")

        def chromadb_querytxt(self, query, n_results=1):
            return []

        def get_logo(self):
            return None

    class FakeAseServerType(FakeAseServer):
        @staticmethod
        def get_ase_distance_threshold():
            return 1.5

    monkeypatch.setattr(predefinedads, "AseServerMetadata", FakeAseServerType)

    resp = client.post(
        "/ase/predef/query/firstad",
        json={"query": "banana", "n_results": 1, "use_default_ad_onempty": True},
    )
    assert resp.status_code == 200
    assert resp.mimetype == "image/jpeg"
