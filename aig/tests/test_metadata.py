from pathlib import Path

from PIL import Image

from database.version import AigServerMetadata, AseServerMetadata


def test_get_t2i_model_device_defaults_to_gpu(monkeypatch):
    monkeypatch.delenv("AIG_MODEL_DEVICE", raising=False)

    assert AigServerMetadata.get_t2i_model_device() == "GPU"


def test_get_t2i_model_device_invalid_value_falls_back_to_cpu(monkeypatch):
    monkeypatch.setenv("AIG_MODEL_DEVICE", "FOO")

    assert AigServerMetadata.get_t2i_model_device() == "CPU"


def test_get_ase_enable_sampledata_parses_invalid_and_valid_values(monkeypatch):
    monkeypatch.setenv("ASE_ENABLE_SAMPLEDATA", "abc")
    assert AseServerMetadata.get_ase_enable_sampledata() is False

    monkeypatch.setenv("ASE_ENABLE_SAMPLEDATA", "1")
    assert AseServerMetadata.get_ase_enable_sampledata() is True


def test_save_get_and_remove_image_file_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ASE_IMG_PATH", str(tmp_path))

    image = Image.new("RGB", (10, 10), "red")
    saved = AseServerMetadata.save_image_to_dir(image, 123)

    assert Path(saved).exists()

    loaded = AseServerMetadata.get_image_file(123)
    assert loaded is not None
    assert loaded.size == (10, 10)

    assert AseServerMetadata.remove_image_file(123) is True
    assert not Path(saved).exists()
