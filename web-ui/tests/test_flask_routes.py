"""Flask route tests: portrait/landscape rendering and ad delivery endpoint (Categories F)."""
import main


def client():
    main.app.testing = True
    return main.app.test_client()


def test_index_route_renders_landscape_page():
    resp = client().get("/")
    assert resp.status_code == 200


def test_portrait_route_renders_portrait_page():
    resp = client().get("/portrait")
    assert resp.status_code == 200


def test_get_current_advertisement_no_ad_returns_204(monkeypatch, ad_generator):
    monkeypatch.setattr(main, "ad_generator_Obj", ad_generator)
    resp = client().get("/get_current_advertisement", query_string={"client_id": "c1"})
    assert resp.status_code == 204


def test_get_current_advertisement_returns_image_with_headers(monkeypatch, ad_generator):
    ad_generator.last_generated_ad = b"fake-jpeg-bytes"
    ad_generator.time_taken_last_generated_ad = "generated in 1.0 seconds"
    monkeypatch.setattr(main, "ad_generator_Obj", ad_generator)

    resp = client().get("/get_current_advertisement", query_string={"client_id": "c1", "width": 480, "height": 600})
    assert resp.status_code == 200
    assert resp.mimetype == "image/jpeg"
    assert resp.data == b"fake-jpeg-bytes"
    assert resp.headers.get("X-Generation-Time") == "generated in 1.0 seconds"
