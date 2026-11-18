#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import json
import logging
import time
from uuid import uuid4

import requests

from utils.common_utils import assert_condition, exec_command
from utils.deployment_utils import get_container_logs

logger = logging.getLogger(__name__)


def publish_detection(label, confidence=0.9, count=3):
    logger.info("Publishing %s controlled MQTT detections for label %r at confidence %.2f", count, label, confidence)
    for frame in range(count):
        payload = {
            "metadata": {
                "frame_id": f"functional-{uuid4().hex}-{frame}",
                "gva_meta": [{"tensor": [{"label": label, "confidence": confidence}]}],
            }
        }
        result = exec_command(
            ["docker", "exec", "-i", "mqtt-broker", "mosquitto_pub",
             "-h", "127.0.0.1", "-t", "yolo_od_results", "-q", "1", "-s"],
            input=json.dumps(payload),
            capture_output=True,
        )
        assert_condition(result.returncode == 0, result.stderr)


def wait_for_advertisement(get_endpoint, timeout=120):
    logger.info("Waiting up to %s seconds for an advertisement", timeout)
    deadline = time.monotonic() + timeout
    last_report = time.monotonic()
    client_id = f"functional-{uuid4().hex}"
    while True:
        response = get_endpoint("/get_current_advertisement", params={"client_id": client_id})
        assert_condition(response.status_code in (200, 204), f"Current ad: HTTP {response.status_code}")
        if response.status_code == 200:
            assert_condition(response.content, "Advertisement response is empty")
            logger.info("Advertisement delivered as %s", response.headers.get("Content-Type", "unknown media"))
            return response
        if time.monotonic() >= deadline:
            assert_condition(False, f"No advertisement was delivered within {timeout} seconds")
        if time.monotonic() - last_report >= 15:
            logger.info("Advertisement is not ready yet; polling again")
            last_report = time.monotonic()
        time.sleep(0.5)


def assert_no_advertisement(get_endpoint, duration=5):
    logger.info("Checking that no advertisement appears for %s seconds", duration)
    deadline = time.monotonic() + duration
    while True:
        response = get_endpoint(
            "/get_current_advertisement", params={"client_id": f"functional-{uuid4().hex}"}
        )
        assert_condition(response.status_code == 204, "Ineligible detections produced an advertisement")
        if time.monotonic() >= deadline:
            logger.info("No advertisement appeared during the negative check")
            return
        time.sleep(0.5)


def get_signage_events():
    events = []
    for line in get_container_logs("web-ui").splitlines():
        if "SIGNAGE_EVENT " in line:
            events.append(json.loads(line.split("SIGNAGE_EVENT ", 1)[1]))
    return events


def wait_for_http_ready(get_endpoint, timeout=300):
    logger.info("Waiting up to %s seconds for the web UI and AIG health endpoint", timeout)
    deadline = time.monotonic() + timeout
    last_report = time.monotonic()
    detail = ""
    while True:
        try:
            ui = get_endpoint("/")
            aig = get_endpoint("/aig-api/aig/hstatus/1")
            if ui.status_code == aig.status_code == 200 and aig.json() == {"status": "ok", "id": 1}:
                logger.info("Web UI and AIG health endpoint are ready")
                return
            detail = f"UI HTTP {ui.status_code}, AIG HTTP {aig.status_code}"
        except (requests.RequestException, ValueError) as error:
            detail = str(error)
        if time.monotonic() >= deadline:
            assert_condition(False, f"UI and AIG did not become ready: {detail}")
        if time.monotonic() - last_report >= 30:
            logger.info("UI/AIG readiness pending: %s", detail)
            last_report = time.monotonic()
        time.sleep(2)