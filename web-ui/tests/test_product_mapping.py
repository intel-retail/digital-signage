"""Category B: Product mapping & CSV association tests."""
import main


def test_normalize_product_key_lowercases_and_strips():
    assert main.normalize_product_key("  Banana  ") == "banana"


def test_normalize_product_key_replaces_separators():
    assert main.normalize_product_key("Peanut-Butter_Jar") == "peanut butter jar"


def test_normalize_product_key_handles_empty_and_none():
    assert main.normalize_product_key("") == ""
    assert main.normalize_product_key(None) == ""


def test_resolve_product_label_case_insensitive(loaded_associations):
    # CSV has 'banana'; MQTT/agent labels may arrive in different case/format.
    assert main.resolve_product_label("Banana") == "banana"
    assert main.resolve_product_label("BANANA") == "banana"
    assert main.resolve_product_label(" banana ") == "banana"


def test_resolve_product_label_unknown_returns_none(loaded_associations):
    assert main.resolve_product_label("spaceship") is None


def test_load_product_associations_populates_all_rows(sample_csv_path):
    ok = main.load_product_associations(sample_csv_path)
    assert ok is True
    # banana has two rows (two ad variants) in the fixture CSV
    assert len(main.product_associations["banana"]) == 2
    assert len(main.product_associations["apple"]) == 1
    assert main.product_association_lookup["banana"] == "banana"


def test_load_product_associations_duplicate_labels_collapse_to_one_candidate(loaded_associations):
    # Resolving the same label twice must produce the same canonical primary product key
    resolved_1 = main.resolve_product_label("banana")
    resolved_2 = main.resolve_product_label("BANANA")
    assert resolved_1 == resolved_2 == "banana"


def test_load_product_associations_missing_file_returns_false():
    ok = main.load_product_associations("/nonexistent/path/ProductAssociations.csv")
    assert ok is False


def test_load_product_associations_malformed_csv_returns_false(tmp_path):
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("not,the,right,header\n1,2,3,4\n")
    ok = main.load_product_associations(str(bad_csv))
    assert ok is False


def test_load_product_associations_parses_association_fields(sample_csv_path):
    main.load_product_associations(sample_csv_path)
    banana_variants = main.product_associations["banana"]
    assert banana_variants[0]["price"] == "0.59"
    assert banana_variants[0]["associated_cross_sell"] == "peanut butter"
    assert banana_variants[1]["associated_cross_sell"] == "bread"
