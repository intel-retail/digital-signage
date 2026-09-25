"""Category A: detection ingestion & MQTT message processing tests."""
import json
from types import SimpleNamespace

import main


def make_detection_payload(detections):
    """detections: list of (label, confidence) tuples for a single frame."""
    tensors = [{"label": label, "confidence": confidence} for label, confidence in detections]
    return json.dumps({
        "metadata": {
            "gva_meta": [
                {"tensor": tensors}
            ]
        }
    })


def make_msg(payload: str, topic: str = main.MQTT_TOPIC):
    return SimpleNamespace(topic=topic, payload=payload.encode("utf-8"))


def drain_queue():
    items = []
    while not main.message_queue.empty():
        items.append(main.message_queue.get_nowait())
    return items


def test_on_message_normalizes_labels_to_lowercase(monkeypatch):
    subscriber = main.MQTTSubscriber("broker", 1883, "topic")
    subscriber.object_recency_count = 1
    subscriber.object_threshold_confidence = 0.5
    subscriber.max_message_history = 2
    drain_queue()

    subscriber.on_message(None, None, make_msg(make_detection_payload([("BANANA", 0.9)])))

    queued = drain_queue()
    assert queued == [["banana"]]


def test_on_message_discards_labels_below_confidence_threshold():
    subscriber = main.MQTTSubscriber("broker", 1883, "topic")
    subscriber.object_recency_count = 1
    subscriber.object_threshold_confidence = 0.8
    subscriber.max_message_history = 2
    drain_queue()

    subscriber.on_message(None, None, make_msg(make_detection_payload([("banana", 0.5)])))

    assert drain_queue() == []


def test_on_message_requires_recency_across_frames():
    subscriber = main.MQTTSubscriber("broker", 1883, "topic")
    subscriber.object_recency_count = 3
    subscriber.object_threshold_confidence = 0.5
    subscriber.max_message_history = 6
    drain_queue()

    # Only 2 of the required 3 recent frames contain "banana" -> not eligible yet.
    subscriber.on_message(None, None, make_msg(make_detection_payload([("banana", 0.9)])))
    subscriber.on_message(None, None, make_msg(make_detection_payload([("banana", 0.9)])))
    assert drain_queue() == []

    # Third consecutive frame satisfies the recency requirement.
    subscriber.on_message(None, None, make_msg(make_detection_payload([("banana", 0.9)])))
    assert drain_queue() == [["banana"]]


def test_on_message_malformed_json_does_not_raise():
    subscriber = main.MQTTSubscriber("broker", 1883, "topic")
    drain_queue()
    # Should not raise even though payload is not valid JSON.
    subscriber.on_message(None, None, make_msg("not-json-at-all"))
    assert drain_queue() == []


def test_on_message_missing_gva_meta_clears_history():
    subscriber = main.MQTTSubscriber("broker", 1883, "topic")
    subscriber.last_n_messages_labels = [{"banana": [0.9]}]
    subscriber.list_of_processed_products = ["banana"]
    subscriber.last_processed_item = "banana"

    subscriber.on_message(None, None, make_msg(json.dumps({"metadata": {}})))

    assert subscriber.last_n_messages_labels == []
    assert subscriber.list_of_processed_products == []
    assert subscriber.last_processed_item == ""


def test_on_message_history_capped_at_max_message_history():
    subscriber = main.MQTTSubscriber("broker", 1883, "topic")
    subscriber.object_recency_count = 1
    subscriber.max_message_history = 2
    drain_queue()

    for _ in range(5):
        subscriber.on_message(None, None, make_msg(make_detection_payload([("banana", 0.9)])))

    assert len(subscriber.last_n_messages_labels) == 2
