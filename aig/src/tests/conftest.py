"""Shared pytest fixtures for the AIG server unit test suite.

`database/version.py` (and transitively `imgproc/img_frame.py`,
`server/apis/modelinf.py`, etc.) import heavyweight ML/DB packages
(openvino_genai, openvino, chromadb) that are not needed to exercise the
pure configuration/env-driven logic and image-decoration helpers under
test here. Those modules are stubbed out in ``sys.modules`` *before* any
AIG package is imported so the test suite stays fast and does not require
installing multi-gigabyte model runtimes.
"""
import os
import sys
import types

AIG_SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

if AIG_SRC_DIR not in sys.path:
    sys.path.insert(0, AIG_SRC_DIR)


def _stub_module(name):
    if name in sys.modules:
        return sys.modules[name]
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


def _install_heavy_stubs():
    openvino_genai_stub = _stub_module("openvino_genai")
    openvino_genai_stub.Text2ImagePipeline = object

    openvino_stub = _stub_module("openvino")

    class _FakeCore:
        available_devices = ["CPU"]

    openvino_stub.Core = _FakeCore

    chromadb_stub = _stub_module("chromadb")
    chromadb_stub.HttpClient = object

    chromadb_utils_stub = _stub_module("chromadb.utils")

    class _FakeEmbeddingFunction:
        def __init__(self, *args, **kwargs):
            pass

    chromadb_utils_stub.embedding_functions = types.SimpleNamespace(
        SentenceTransformerEmbeddingFunction=_FakeEmbeddingFunction,
        DefaultEmbeddingFunction=_FakeEmbeddingFunction,
    )
    chromadb_stub.utils = chromadb_utils_stub


_install_heavy_stubs()

import pytest  # noqa: E402


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR
