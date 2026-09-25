"""Category G: MCP tool interface / context resolution core-logic tests."""
import main


def test_load_context_rules_valid_file(sample_context_rules_path):
    main.load_context_rules(sample_context_rules_path)
    assert main.context_rules.get("default_product") == "banana"
    assert len(main.context_rules.get("rules", [])) == 4


def test_load_context_rules_missing_file_disables_feature():
    main.load_context_rules("/nonexistent/context_rules.json")
    assert main.context_rules == {}


def test_resolve_context_to_product_matches_weather_rule(sample_context_rules_path):
    main.load_context_rules(sample_context_rules_path)
    product, rule = main.resolve_context_to_product({"weather": "Rain"})
    assert product == "coffee"
    assert rule["weather"] == "rain"


def test_resolve_context_to_product_case_and_whitespace_insensitive(sample_context_rules_path):
    main.load_context_rules(sample_context_rules_path)
    product, _ = main.resolve_context_to_product({"weather": "  HOT  "})
    assert product == "apple"


def test_resolve_context_to_product_no_match_uses_default(sample_context_rules_path):
    main.load_context_rules(sample_context_rules_path)
    product, rule = main.resolve_context_to_product({"weather": "tornado"})
    assert product == "banana"
    assert rule == {"default": True}


def test_resolve_context_to_product_no_default_returns_none():
    main.context_rules = {"rules": [{"weather": "rain", "product": "coffee"}]}
    product, rule = main.resolve_context_to_product({"weather": "tornado"})
    assert product is None
    assert rule is None


def test_resolve_context_to_product_prefers_most_specific_match(sample_context_rules_path):
    main.load_context_rules(sample_context_rules_path)
    # "demand: high" matches one rule (score 1); adding a non-matching field must not change the winner.
    product, rule = main.resolve_context_to_product({"demand": "high", "weather": "unknown"})
    assert product == "banana"
    assert rule["demand"] == "high"


def test_get_catalog_summary_lists_products_with_cross_sells(loaded_associations):
    summary = main.get_catalog_summary()
    products = {entry["product"] for entry in summary}
    assert products == {"banana", "apple", "coffee"}
    banana_entry = next(e for e in summary if e["product"] == "banana")
    assert set(banana_entry["cross_sells"]) == {"peanut butter", "bread"}
    assert "variants" not in banana_entry


def test_get_catalog_summary_full_includes_variants(loaded_associations):
    summary = main.get_catalog_summary(full=True)
    banana_entry = next(e for e in summary if e["product"] == "banana")
    assert "variants" in banana_entry
    assert len(banana_entry["variants"]) == 2


def test_get_catalog_summary_empty_catalog_returns_empty_list():
    assert main.get_catalog_summary() == []


def test_get_active_ad_info_defaults_to_camera_mode(ad_generator, monkeypatch):
    monkeypatch.setattr(main, "ad_generator_Obj", ad_generator)
    ad_generator.last_selected_item = "banana"
    info = main.get_active_ad_info()
    assert info == {"mode": "camera", "item": "banana", "seconds_remaining": None}


def test_get_active_ad_info_reports_generating(ad_generator, monkeypatch):
    monkeypatch.setattr(main, "ad_generator_Obj", ad_generator)
    ad_generator.agent_override_generating = True
    ad_generator.agent_override_item = "coffee"
    info = main.get_active_ad_info()
    assert info["mode"] == "generating"
    assert info["item"] == "coffee"


def test_clear_agent_override_resets_state(ad_generator, monkeypatch):
    monkeypatch.setattr(main, "ad_generator_Obj", ad_generator)
    ad_generator.agent_override_ad = b"some-ad"
    ad_generator.agent_override_item = "coffee"
    ad_generator.agent_override_until = 99999999999.0

    result = main.clear_agent_override()
    assert result == {"status": "ok", "cleared_item": "coffee"}
    assert ad_generator.agent_override_ad is None
    assert ad_generator.agent_override_item is None
    assert ad_generator.agent_override_until == 0.0


def test_trigger_ad_core_unknown_item_returns_error(loaded_associations, ad_generator, monkeypatch):
    monkeypatch.setattr(main, "ad_generator_Obj", ad_generator)
    result = main.trigger_ad_core("spaceship")
    assert "error" in result
    assert "Unknown item" in result["error"]


def test_select_dynamic_ad_core_no_matching_rule_or_default_returns_error(loaded_associations, ad_generator, monkeypatch):
    monkeypatch.setattr(main, "ad_generator_Obj", ad_generator)
    main.context_rules = {"rules": []}
    result = main.select_dynamic_ad_core({"weather": "tornado"})
    assert "error" in result


def test_select_dynamic_ad_core_resolved_product_not_in_catalog_returns_error(ad_generator, monkeypatch):
    monkeypatch.setattr(main, "ad_generator_Obj", ad_generator)
    main.context_rules = {"rules": [], "default_product": "unknown_product"}
    main.product_associations = {}
    result = main.select_dynamic_ad_core({"weather": "rain"})
    assert "error" in result
    assert "not in the catalog" in result["error"]
