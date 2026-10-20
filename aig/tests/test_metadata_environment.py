"""Comprehensive metadata environment variable tests."""

from database.version import AigServerMetadata, AseServerMetadata, ServerEnvironment


class TestAigEnvironmentVariables:
    """Test AIG environment variable parsing."""

    def test_model_device_cpu(self, monkeypatch):
        monkeypatch.setenv("AIG_MODEL_DEVICE", "CPU")
        assert AigServerMetadata.get_t2i_model_device() == "CPU"

    def test_model_device_gpu(self, monkeypatch):
        monkeypatch.setenv("AIG_MODEL_DEVICE", "GPU")
        assert AigServerMetadata.get_t2i_model_device() == "GPU"

    def test_model_device_npu(self, monkeypatch):
        monkeypatch.setenv("AIG_MODEL_DEVICE", "NPU")
        assert AigServerMetadata.get_t2i_model_device() == "NPU"

    def test_model_device_invalid_defaults_to_cpu(self, monkeypatch):
        monkeypatch.setenv("AIG_MODEL_DEVICE", "INVALID_DEVICE")
        assert AigServerMetadata.get_t2i_model_device() == "CPU"

    def test_inference_steps_custom_value(self, monkeypatch):
        monkeypatch.setenv("AIG_MODEL_NUM_INFERENCE_STEPS", "10")
        assert AigServerMetadata.get_model_inference_steps() == 10

    def test_inference_steps_default(self, monkeypatch):
        monkeypatch.delenv("AIG_MODEL_NUM_INFERENCE_STEPS", raising=False)
        steps = AigServerMetadata.get_model_inference_steps()
        assert steps == 5

    def test_image_width_custom(self, monkeypatch):
        monkeypatch.setenv("AIG_IMG_WIDTH_DEFAULT", "1024")
        assert AigServerMetadata.get_img_width() == 1024

    def test_image_height_custom(self, monkeypatch):
        monkeypatch.setenv("AIG_IMG_HEIGHT_DEFAULT", "768")
        assert AigServerMetadata.get_img_height() == 768

    def test_keep_model_in_memory_true(self, monkeypatch):
        monkeypatch.setenv("AIG_KEEP_MODEL_IN_MEMORY", "true")
        assert AigServerMetadata.should_keep_model_in_memory() is True

    def test_keep_model_in_memory_false(self, monkeypatch):
        monkeypatch.setenv("AIG_KEEP_MODEL_IN_MEMORY", "false")
        assert AigServerMetadata.should_keep_model_in_memory() is False

    def test_keep_model_in_memory_default(self, monkeypatch):
        monkeypatch.delenv("AIG_KEEP_MODEL_IN_MEMORY", raising=False)
        assert AigServerMetadata.should_keep_model_in_memory() is False


class TestAseEnvironmentVariables:
    """Test ASE environment variable parsing."""

    def test_collection_name_default(self, monkeypatch):
        monkeypatch.delenv("ASE_COLLECTION_NAME", raising=False)
        assert AseServerMetadata.get_ase_collection_name() == "ase-collection"

    def test_collection_name_custom(self, monkeypatch):
        monkeypatch.setenv("ASE_COLLECTION_NAME", "custom-ads")
        assert AseServerMetadata.get_ase_collection_name() == "custom-ads"

    def test_chromadb_host_default(self, monkeypatch):
        monkeypatch.delenv("ASE_CHROMADB_HOST", raising=False)
        assert AseServerMetadata.get_ase_chromadb_host() == "ase-chromadb"

    def test_chromadb_host_custom(self, monkeypatch):
        monkeypatch.setenv("ASE_CHROMADB_HOST", "localhost")
        assert AseServerMetadata.get_ase_chromadb_host() == "localhost"

    def test_chromadb_port_default(self, monkeypatch):
        monkeypatch.delenv("ASE_CHROMADB_PORT", raising=False)
        assert AseServerMetadata.get_ase_chromadb_port() == 8000

    def test_chromadb_port_custom(self, monkeypatch):
        monkeypatch.setenv("ASE_CHROMADB_PORT", "9000")
        assert AseServerMetadata.get_ase_chromadb_port() == 9000

    def test_distance_threshold_default(self, monkeypatch):
        monkeypatch.delenv("ASE_DISTANCE_MAX_THRESHOLD", raising=False)
        assert AseServerMetadata.get_ase_distance_threshold() == 1.5

    def test_distance_threshold_custom(self, monkeypatch):
        monkeypatch.setenv("ASE_DISTANCE_MAX_THRESHOLD", "0.8")
        assert AseServerMetadata.get_ase_distance_threshold() == 0.8

    def test_enable_sampledata_default(self, monkeypatch):
        monkeypatch.delenv("ASE_ENABLE_SAMPLEDATA", raising=False)
        assert AseServerMetadata.get_ase_enable_sampledata() is False

    def test_enable_sampledata_1(self, monkeypatch):
        monkeypatch.setenv("ASE_ENABLE_SAMPLEDATA", "1")
        assert AseServerMetadata.get_ase_enable_sampledata() is True

    def test_enable_sampledata_false(self, monkeypatch):
        monkeypatch.setenv("ASE_ENABLE_SAMPLEDATA", "false")
        assert AseServerMetadata.get_ase_enable_sampledata() is False


class TestAigStaticProperties:
    """Test AIG static property getters."""

    def test_name_short(self):
        name = AigServerMetadata.name_short()
        assert name is not None
        assert isinstance(name, str)
        assert len(name) > 0

    def test_name_extended(self):
        name = AigServerMetadata.name_extended()
        assert name is not None
        assert isinstance(name, str)
        assert "Advertise" in name or "Image" in name

    def test_version(self):
        version = AigServerMetadata.version()
        assert version is not None
        assert version == "0.1.0"

    def test_description_short(self):
        desc = AigServerMetadata.description_short()
        assert desc is not None
        assert isinstance(desc, str)
        assert len(desc) > 0


class TestServerEnvironment:
    """Test ServerEnvironment static methods."""

    def test_get_dependencies_returns_list(self):
        deps = ServerEnvironment.get_dependencies()
        assert isinstance(deps, list)
        assert len(deps) > 0

    def test_dependency_schema_structure(self):
        """Test each dependency has required schema."""
        deps = ServerEnvironment.get_dependencies()
        for dep in deps:
            assert hasattr(dep, "component")
            assert hasattr(dep, "version")
            assert dep.component is not None
            assert dep.version is not None

    def test_get_aig_with_dependencies(self):
        """Test AIG with dependencies includes AIG in result."""
        result = ServerEnvironment.get_aig_with_dependencies()
        assert isinstance(result, list)
        assert len(result) > 0

        aig_found = any("AIG" in str(item.component) for item in result)
        assert aig_found


class TestAigVersionInfo:
    """Test AIG version info schema."""

    def test_version_info_structure(self):
        info = AigServerMetadata.get_aig_versioninfo()
        assert info is not None
        assert hasattr(info, "component")
        assert hasattr(info, "version")
        assert hasattr(info, "observation")
        assert hasattr(info, "lastverification")
