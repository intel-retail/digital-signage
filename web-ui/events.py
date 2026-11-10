"""
Named Digital Signage events.

Every event is written to the application log as one ordered `SIGNAGE_EVENT {json}` line (the
`seq` field increases by one per event within a process run) and, when QSR_EVENTS_URL is set, also
pushed to that endpoint in the QSR agent's event envelope. Delivery runs on a background thread, so
a slow or unreachable agent never delays ad rendering.
"""
import itertools
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from queue import Empty, Full, Queue

import requests

logger = logging.getLogger(__name__)

PRODUCT_DETECTED = 'product_detected'
AD_DISPLAYED = 'ad_displayed'

# Allowed `data` fields per event type; anything else is rejected so the contract stays fixed.
EVENT_FIELDS = {
    PRODUCT_DETECTED: {'label', 'confidence'},
    AD_DISPLAYED: {'product', 'variant', 'media', 'trigger'},
}

SERVICE_NAME = 'digital-signage'
EVENTS_URL = os.getenv('QSR_EVENTS_URL', '').strip()
STORE_ID = os.getenv('QSR_STORE_ID', 'qsr-001').strip()
SEND_ATTEMPTS = 3
SEND_TIMEOUT_SECONDS = 5.0
QUEUE_LIMIT = 1000

_sequence = itertools.count(1)
_sequence_lock = threading.Lock()
_outbox = Queue(maxsize=QUEUE_LIMIT)
_sender_started = False
_sender_lock = threading.Lock()


def build_event(event_type, **data):
    """Return the event envelope after checking the event type and its data fields."""
    allowed = EVENT_FIELDS.get(event_type)
    if allowed is None:
        raise ValueError(f"unknown event type: {event_type}")
    unexpected = set(data) - allowed
    if unexpected:
        raise ValueError(f"unexpected fields for {event_type}: {', '.join(sorted(unexpected))}")
    now = datetime.now(timezone.utc)
    return {
        'event_id': f"signage-{STORE_ID}-{now.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}",
        'event_type': event_type,
        'service': SERVICE_NAME,
        'store_id': STORE_ID,
        'occurred_at': now.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
        'data': data,
    }


def emit(event_type, **data):
    """Log the event and queue it for delivery. Never raises: events must not break ad rendering."""
    try:
        event = build_event(event_type, **data)
        with _sequence_lock:
            seq = next(_sequence)
            logger.info("SIGNAGE_EVENT %s", json.dumps({'seq': seq, **event}))
        if EVENTS_URL:
            _start_sender()
            try:
                _outbox.put_nowait(event)
            except Full:
                logger.warning("Event queue full; not delivering %s %s", event_type, event['event_id'])
    except Exception as e:
        logger.error(f"Failed to emit {event_type} event: {e}")


def _start_sender():
    global _sender_started
    with _sender_lock:
        if _sender_started:
            return
        threading.Thread(target=_send_loop, name='signage-event-sender', daemon=True).start()
        _sender_started = True


def _send_loop():
    session = requests.Session()
    while True:
        try:
            event = _outbox.get(timeout=1)
        except Empty:
            continue
        _deliver(session, event)


def _deliver(session, event):
    for attempt in range(SEND_ATTEMPTS):
        status = None
        try:
            status = session.post(EVENTS_URL, json=event, timeout=SEND_TIMEOUT_SECONDS).status_code
        except requests.RequestException as e:
            logger.warning(f"Event delivery failed (attempt {attempt + 1}): {e}")
        if status is not None and 200 <= status < 300:
            return True
        # A client error other than throttling will not succeed on retry.
        if status is not None and 400 <= status < 500 and status != 429:
            logger.error(f"Event {event['event_id']} rejected with HTTP {status}")
            return False
        if attempt + 1 < SEND_ATTEMPTS:
            time.sleep(0.5 * 2 ** attempt)
    logger.error(f"Event {event['event_id']} could not be delivered to {EVENTS_URL}")
    return False
