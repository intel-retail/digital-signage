"""Category F: ad delivery to clients tests."""
import time

import main


def test_normalize_display_seconds_valid_int():
    assert main.normalize_display_seconds("30") == 30


def test_normalize_display_seconds_non_numeric_falls_back_to_default():
    assert main.normalize_display_seconds("not-a-number", default=15) == 15


def test_normalize_display_seconds_non_positive_falls_back_to_default():
    assert main.normalize_display_seconds(0, default=15) == 15
    assert main.normalize_display_seconds(-5, default=15) == 15


def test_get_current_advertisement_returns_none_without_generated_ad(ad_generator):
    data, info = ad_generator.get_current_advertisement(client_id="client-1")
    assert data is None
    assert info == 0


def test_get_current_advertisement_new_client_receives_ad_once(ad_generator):
    ad_generator.last_generated_ad = b"fake-jpeg-bytes"
    ad_generator.time_taken_last_generated_ad = "generated in 1.0 seconds"

    data, info = ad_generator.get_current_advertisement(client_id="client-1")
    assert data == b"fake-jpeg-bytes"
    assert info == "generated in 1.0 seconds"

    # Same client asking again in the same cycle gets nothing new.
    data_again, info_again = ad_generator.get_current_advertisement(client_id="client-1")
    assert data_again is None
    assert info_again == 0


def test_get_current_advertisement_new_client_mid_cycle_gets_current_ad(ad_generator):
    ad_generator.last_generated_ad = b"fake-jpeg-bytes"
    ad_generator.get_current_advertisement(client_id="client-1")

    # A second, previously-unseen client should still receive the current ad.
    data, _ = ad_generator.get_current_advertisement(client_id="client-2")
    assert data == b"fake-jpeg-bytes"


def test_get_current_advertisement_updates_known_dimensions(ad_generator):
    ad_generator.get_current_advertisement(height=720, width=1280, client_id="client-1")
    assert ad_generator.last_known_height == 720
    assert ad_generator.last_known_width == 1280


def test_get_current_advertisement_agent_override_takes_priority(ad_generator):
    ad_generator.last_generated_ad = b"camera-driven-ad"
    ad_generator.agent_override_ad = b"agent-ad"
    ad_generator.agent_override_until = time.time() + 60
    ad_generator.agent_override_item = "coffee"

    data, info = ad_generator.get_current_advertisement(client_id="client-1")
    assert data == b"agent-ad"
    assert "coffee" in info


def test_get_current_advertisement_expired_agent_override_falls_back_to_camera(ad_generator):
    ad_generator.last_generated_ad = b"camera-driven-ad"
    ad_generator.agent_override_ad = b"agent-ad"
    ad_generator.agent_override_until = time.time() - 1  # already expired

    data, _ = ad_generator.get_current_advertisement(client_id="client-1")
    assert data == b"camera-driven-ad"
