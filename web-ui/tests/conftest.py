"""Shared pytest fixtures for the Web UI functional/unit test suite.

`main.py` is a script module (not a package) that only starts network
services (Flask server thread, MQTT connect, model warm-up) inside its
``if __name__ == "__main__":`` guard, so importing it here is safe: we get
all the pure business logic (product mapping, selection strategies, ad
delivery bookkeeping) without any side effects.
"""
import os
import sys

WEB_UI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

if WEB_UI_DIR not in sys.path:
    sys.path.insert(0, WEB_UI_DIR)

import pytest

import main  # noqa: E402  (import after sys.path setup)


@pytest.fixture
def sample_csv_path():
    return os.path.join(FIXTURES_DIR, "ProductAssociations_sample.csv")


@pytest.fixture
def sample_context_rules_path():
    return os.path.join(FIXTURES_DIR, "context_rules_sample.json")


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset module-level globals mutated by tests so cases stay isolated."""
    original_associations = main.product_associations
    original_lookup = main.product_association_lookup
    original_context_rules = main.context_rules
    main.product_associations = {}
    main.product_association_lookup = {}
    main.context_rules = {}
    yield
    main.product_associations = original_associations
    main.product_association_lookup = original_lookup
    main.context_rules = original_context_rules


@pytest.fixture
def loaded_associations(monkeypatch, sample_csv_path):
    """Load the sample CSV without attempting to POST predefined ads to AIG."""
    monkeypatch.setattr(main.requests, "post", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("Unexpected network call during test")))
    main.load_product_associations(sample_csv_path)
    return main.product_associations


@pytest.fixture
def ad_generator():
    """A fresh Ad_Generator instance (not started as a thread)."""
    gen = main.Ad_Generator()
    yield gen
    try:
        gen.http_session.close()
    except Exception:
        pass
