"""Categories C & D: product selection strategy and ad-variant selection tests."""
import main


def test_get_product_max_price_returns_highest_price(loaded_associations, ad_generator):
    assert ad_generator.get_product_max_price("banana") == 0.59
    assert ad_generator.get_product_max_price("apple") == 1.99


def test_get_product_max_price_unknown_product_returns_negative(ad_generator):
    assert ad_generator.get_product_max_price("unknown") == -1.0


def test_find_high_priced_candidate_picks_most_expensive(loaded_associations, ad_generator):
    selected = ad_generator.find_high_priced_candidate(["banana", "apple", "coffee"])
    assert selected == "coffee"  # 4.50 is the highest price in the fixture


def test_find_high_priced_candidate_empty_list_returns_none(ad_generator):
    assert ad_generator.find_high_priced_candidate([]) is None


def test_find_high_priced_candidate_ties_pick_one_of_the_best(loaded_associations, ad_generator, monkeypatch):
    monkeypatch.setattr(main.random, "choice", lambda seq: seq[0])
    # Force a tie by monkeypatching price lookup
    monkeypatch.setattr(ad_generator, "get_product_max_price", lambda item: 1.0)
    selected = ad_generator.find_high_priced_candidate(["banana", "apple"])
    assert selected in ("banana", "apple")


def test_find_rotating_candidate_prefers_least_shown(loaded_associations, ad_generator):
    ad_generator.product_generation_count = {"banana": 3, "apple": 0, "coffee": 1}
    selected = ad_generator.find_rotating_candidate(["banana", "apple", "coffee"])
    assert selected == "apple"


def test_find_rotating_candidate_avoids_immediate_repeat_when_alternatives_exist(loaded_associations, ad_generator):
    ad_generator.last_selected_item = "banana"
    ad_generator.product_generation_count = {"banana": 1, "apple": 1}
    selected = ad_generator.find_rotating_candidate(["banana", "apple"])
    assert selected == "apple"


def test_find_rotating_candidate_allows_repeat_when_no_alternative(loaded_associations, ad_generator):
    ad_generator.last_selected_item = "banana"
    selected = ad_generator.find_rotating_candidate(["banana"])
    assert selected == "banana"


def test_find_rotating_candidate_empty_list_returns_none(ad_generator):
    assert ad_generator.find_rotating_candidate([]) is None


def test_choose_association_index_single_variant_always_zero(loaded_associations, ad_generator):
    apple_assocs = main.product_associations["apple"]
    assert ad_generator.choose_association_index("apple", apple_assocs) == 0
    assert ad_generator.choose_association_index("apple", apple_assocs) == 0


def test_choose_association_index_avoids_immediate_repeat(loaded_associations, ad_generator):
    banana_assocs = main.product_associations["banana"]
    first = ad_generator.choose_association_index("banana", banana_assocs)
    second = ad_generator.choose_association_index("banana", banana_assocs)
    assert first != second


def test_choose_association_index_no_associations_returns_zero(ad_generator):
    assert ad_generator.choose_association_index("banana", None) == 0
    assert ad_generator.choose_association_index("banana", []) == 0


def test_find_product_for_ad_generation_discards_unknown_labels(loaded_associations, ad_generator):
    selected = ad_generator.find_product_for_ad_generation(["spaceship", "ufo"])
    assert selected is None


def test_find_product_for_ad_generation_first_time_prioritizes_highest_price(loaded_associations, ad_generator):
    selected = ad_generator.find_product_for_ad_generation(["banana", "coffee"])
    assert selected == "coffee"
    assert ad_generator.product_generation_count["coffee"] == 1


def test_find_product_for_ad_generation_duplicate_labels_collapse(loaded_associations, ad_generator):
    selected = ad_generator.find_product_for_ad_generation(["banana", "Banana", "BANANA"])
    assert selected == "banana"
    assert ad_generator.product_generation_count["banana"] == 1


def test_find_product_for_ad_generation_rotation_mode_after_all_shown(loaded_associations, ad_generator):
    ad_generator.find_product_for_ad_generation(["banana"])
    ad_generator.find_product_for_ad_generation(["apple"])
    ad_generator.find_product_for_ad_generation(["coffee"])
    # All three products have now been generated at least once; next round is rotation mode.
    ad_generator.last_processed_item = []
    selected = ad_generator.find_product_for_ad_generation(["banana", "apple", "coffee"])
    assert selected in ("banana", "apple", "coffee")
