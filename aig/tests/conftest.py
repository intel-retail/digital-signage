import sys
import types
from pathlib import Path


def _install_openvino_stubs() -> None:
    if "openvino_genai" not in sys.modules:
        module = types.ModuleType("openvino_genai")

        class Text2ImagePipeline:  # pragma: no cover - test import shim only
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

            def generate(self, *args, **kwargs):
                return None

        module.Text2ImagePipeline = Text2ImagePipeline
        sys.modules["openvino_genai"] = module

    if "openvino" not in sys.modules:
        module = types.ModuleType("openvino")

        class Core:  # pragma: no cover - test import shim only
            def __init__(self):
                self.available_devices = ["CPU"]

        module.Core = Core
        sys.modules["openvino"] = module


def _install_chromadb_stubs() -> None:
    if "chromadb" in sys.modules:
        return

    chromadb_module = types.ModuleType("chromadb")

    class HttpClient:  # pragma: no cover - test import shim only
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def get_or_create_collection(self, *args, **kwargs):
            return None

        def heartbeat(self):
            return 1

    chromadb_module.HttpClient = HttpClient

    utils_module = types.ModuleType("chromadb.utils")
    embedding_module = types.ModuleType("chromadb.utils.embedding_functions")

    class SentenceTransformerEmbeddingFunction:  # pragma: no cover
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    class DefaultEmbeddingFunction:  # pragma: no cover
        def __call__(self, *args, **kwargs):
            return []

    embedding_module.SentenceTransformerEmbeddingFunction = SentenceTransformerEmbeddingFunction
    embedding_module.DefaultEmbeddingFunction = DefaultEmbeddingFunction

    utils_module.embedding_functions = embedding_module

    sys.modules["chromadb"] = chromadb_module
    sys.modules["chromadb.utils"] = utils_module
    sys.modules["chromadb.utils.embedding_functions"] = embedding_module


def _configure_python_path() -> None:
    aig_root = Path(__file__).resolve().parents[1]
    src_path = aig_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


_configure_python_path()
_install_openvino_stubs()
_install_chromadb_stubs()
