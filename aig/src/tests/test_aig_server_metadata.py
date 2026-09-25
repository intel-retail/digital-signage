"""Category H (AIG): unit tests for AigServerMetadata env-driven configuration."""
import os

from database.version import AigServerMetadata


def test_get_rest_server_port_defaults(monkeypatch):
    monkeypatch.delenv("AIG_PORT", raising=False)
    assert AigServerMetadata.get_rest_server_port() == 5003


def test_get_rest_server_port_from_env(monkeypatch):
    monkeypatch.setenv("AIG_PORT", "9000")
    assert AigServerMetadata.get_rest_server_port() == 9000


def test_get_model_inference_steps_default(monkeypatch):
    monkeypatch.delenv("AIG_MODEL_NUM_INFERENCE_STEPS", raising=False)
    assert AigServerMetadata.get_model_inference_steps() == 5


def test_get_img_width_and_height_defaults(monkeypatch):
    monkeypatch.delenv("AIG_IMG_WIDTH_DEFAULT", raising=False)
    monkeypatch.delenv("AIG_IMG_HEIGHT_DEFAULT", raising=False)
    assert AigServerMetadata.get_img_width() == 512
    assert AigServerMetadata.get_img_height() == 512


def test_get_t2i_model_device_defaults_to_gpu(monkeypatch):
    monkeypatch.delenv("AIG_MODEL_DEVICE", raising=False)
    assert AigServerMetadata.get_t2i_model_device() == "GPU"


def test_get_t2i_model_device_accepts_valid_values(monkeypatch):
    for device in ("GPU", "CPU", "NPU"):
        monkeypatch.setenv("AIG_MODEL_DEVICE", device)
        assert AigServerMetadata.get_t2i_model_device() == device


def test_get_t2i_model_device_invalid_falls_back_to_cpu(monkeypatch):
    monkeypatch.setenv("AIG_MODEL_DEVICE", "TPU")
    assert AigServerMetadata.get_t2i_model_device() == "CPU"


def test_should_keep_model_in_memory_default_false(monkeypatch):
    monkeypatch.delenv("AIG_KEEP_MODEL_IN_MEMORY", raising=False)
    assert AigServerMetadata.should_keep_model_in_memory() is False


def test_should_keep_model_in_memory_true_case_insensitive(monkeypatch):
    monkeypatch.setenv("AIG_KEEP_MODEL_IN_MEMORY", "TRUE")
    assert AigServerMetadata.should_keep_model_in_memory() is True


def test_is_device_available_cpu_always_true():
    assert AigServerMetadata.is_device_available("CPU") is True
    assert AigServerMetadata.is_device_available("cpu") is True


def test_is_device_available_uses_openvino_core_for_non_cpu(monkeypatch):
    # openvino is stubbed in conftest.py so Core().available_devices == ["CPU"]
    assert AigServerMetadata.is_device_available("GPU") is False


def test_name_and_description_helpers():
    assert AigServerMetadata.name_short() == "AIG Server"
    assert "Advertise Image Generator" in AigServerMetadata.name_extended()
    assert isinstance(AigServerMetadata.description_short(), str)


def test_get_aig_versioninfo_populates_expected_fields():
    info = AigServerMetadata.get_aig_versioninfo()
    assert info.component == "AIG Server"
    assert info.observation == AigServerMetadata.description_short()
    assert info.lastverification is not None
