"""Category H (AIG) support: unit tests for SharedUtils sample-data helpers."""
from PIL import Image

from database.utils import SharedUtils


def test_get_unique_filenames_deduplicates_extensions(tmp_path):
    (tmp_path / "banana.jpg").write_bytes(b"fake")
    (tmp_path / "banana.txt").write_text("desc")
    (tmp_path / "apple.jpg").write_bytes(b"fake")

    result = SharedUtils.get_unique_filenames(str(tmp_path))
    assert result == {"banana", "apple"}


def test_load_sampledata_returns_none_for_missing_args():
    assert SharedUtils.load_sampledata(None, "somedir") is None
    assert SharedUtils.load_sampledata("collection", None) is None


def test_load_sampledata_returns_none_for_nonexistent_directory():
    assert SharedUtils.load_sampledata("collection", "/nonexistent/dir/path") is None


def test_load_sampledata_loads_known_category(tmp_path):
    img = Image.new("RGB", (10, 10), color="red")
    img.save(tmp_path / "bread.jpg")
    (tmp_path / "bread.txt").write_text("Fresh baked bread")

    result = SharedUtils.load_sampledata("collection", str(tmp_path))
    assert len(result) == 1
    entry = result[0]
    assert entry["id"] == SharedUtils.categories["bread"]
    assert entry["source"] == "marketing"
    assert entry["description"] == "Fresh baked bread"


def test_load_sampledata_skips_unknown_category(tmp_path):
    img = Image.new("RGB", (10, 10), color="red")
    img.save(tmp_path / "unknown_item.jpg")
    (tmp_path / "unknown_item.txt").write_text("Some description")

    result = SharedUtils.load_sampledata("collection", str(tmp_path))
    assert result == []


def test_load_sampledata_empty_description_uses_placeholder(tmp_path):
    img = Image.new("RGB", (10, 10), color="red")
    img.save(tmp_path / "water.jpg")
    (tmp_path / "water.txt").write_text("")

    result = SharedUtils.load_sampledata("collection", str(tmp_path))
    assert result[0]["description"] == "No description available."
