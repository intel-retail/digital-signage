from pathlib import Path

from PIL import Image

from database.utils import SharedUtils


def test_get_unique_filenames_returns_stems(tmp_path: Path):
    (tmp_path / "bread.jpg").write_bytes(b"x")
    (tmp_path / "bread.txt").write_text("description", encoding="utf-8")
    (tmp_path / "notes.md").write_text("n/a", encoding="utf-8")

    filenames = SharedUtils.get_unique_filenames(str(tmp_path))

    assert "bread" in filenames
    assert "notes" in filenames


def test_load_sampledata_returns_none_for_missing_directory(tmp_path: Path):
    missing = tmp_path / "does-not-exist"

    result = SharedUtils.load_sampledata(collection=object(), namedir=str(missing))

    assert result is None


def test_load_sampledata_builds_records_for_known_categories(tmp_path: Path):
    image_path = tmp_path / "bread.jpg"
    text_path = tmp_path / "bread.txt"
    Image.new("RGB", (12, 12), "white").save(image_path)
    text_path.write_text("Fresh bread ad", encoding="utf-8")

    records = SharedUtils.load_sampledata(collection=object(), namedir=str(tmp_path))

    assert records is not None
    assert len(records) == 1
    record = records[0]
    assert record["id"] == SharedUtils.categories["bread"]
    assert record["source"] == "marketing"
    assert record["description"] == "Fresh bread ad"
    assert isinstance(record["image"], Image.Image)


def test_shared_utils_categories_is_dict():
    """Test that categories is a dictionary with multiple entries."""
    assert isinstance(SharedUtils.categories, dict)
    assert len(SharedUtils.categories) > 10
    assert "bread" in SharedUtils.categories


def test_get_unique_filenames_with_various_extensions(tmp_path: Path):
    """Test handling of various file extensions."""
    (tmp_path / "item1.jpg").write_bytes(b"")
    (tmp_path / "item1.txt").write_bytes(b"")
    (tmp_path / "item2.png").write_bytes(b"")
    (tmp_path / "item2.txt").write_bytes(b"")

    filenames = SharedUtils.get_unique_filenames(str(tmp_path))

    assert "item1" in filenames
    assert "item2" in filenames
    assert len(filenames) == 2


def test_load_sampledata_with_multiple_products(tmp_path: Path):
    """Test loading multiple products."""
    Image.new("RGB", (10, 10), "white").save(tmp_path / "bread.jpg")
    (tmp_path / "bread.txt").write_text("Whole wheat bread", encoding="utf-8")

    Image.new("RGB", (10, 10), "white").save(tmp_path / "meat_beef.jpg")
    (tmp_path / "meat_beef.txt").write_text("Prime beef", encoding="utf-8")

    records = SharedUtils.load_sampledata(collection=object(), namedir=str(tmp_path))

    assert records is not None
    assert len(records) == 2
    record_ids = {r["id"] for r in records}
    assert SharedUtils.categories["bread"] in record_ids
    assert SharedUtils.categories["meat_beef"] in record_ids
