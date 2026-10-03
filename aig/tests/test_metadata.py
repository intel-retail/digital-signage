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


def test_aig_metadata_image_size_validation():
    """Test image dimension getters return positive integers."""
    width = AigServerMetadata.get_img_width()
    height = AigServerMetadata.get_img_height()

    assert isinstance(width, int)
    assert isinstance(height, int)
    assert width > 0
    assert height > 0
    assert width == 512
    assert height == 512


def test_ase_metadata_collection_name_default():
    """Test default collection name."""
    name = AseServerMetadata.get_ase_collection_name()
    assert isinstance(name, str)
    assert len(name) > 0


def test_aig_metadata_inference_steps_default():
    """Test inference steps configuration."""
    steps = AigServerMetadata.get_model_inference_steps()
    assert isinstance(steps, int)
    assert steps > 0
    assert steps == 5


def test_aig_metadata_static_properties():
    """Test static metadata properties."""
    assert AigServerMetadata.name_short() is not None
    assert AigServerMetadata.name_extended() is not None
    assert AigServerMetadata.version() == "0.1.0"
    assert len(AigServerMetadata.description_short()) > 0


def test_aig_get_model_inference_steps_is_positive():
    """Test inference steps is positive."""
    steps = AigServerMetadata.get_model_inference_steps()
    assert isinstance(steps, int)
    assert steps > 0


def test_ase_metadata_get_ase_collection_name():
    """Test collection name getter."""
    name = AseServerMetadata.get_ase_collection_name()
    assert isinstance(name, str)
    assert len(name) > 0


def test_aig_metadata_keep_model_in_memory_default():
    """Test model persistence flag defaults to false."""
    keep = AigServerMetadata.should_keep_model_in_memory()
    assert isinstance(keep, bool)
    assert keep is False


def test_ase_metadata_distance_threshold_default():
    """Test distance threshold has valid default."""
    threshold = AseServerMetadata.get_ase_distance_threshold()
    assert isinstance(threshold, float)
    assert threshold > 0
    assert threshold <= 2.0
