#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import json
import logging
import time

from utils.common_utils import CONTAINERS, assert_condition, exec_command

logger = logging.getLogger(__name__)


def get_deployed_containers(names=CONTAINERS):
    result = exec_command(["docker", "inspect", *names], capture_output=True)
    assert_condition(result.returncode == 0, result.stderr)
    return {container["Name"].lstrip("/"): container for container in json.loads(result.stdout)}


def get_container_logs(name, since=None, tail=None):
    container = get_deployed_containers((name,))[name]
    command = ["docker", "logs", "--since", since or container["State"]["StartedAt"]]
    if tail is not None:
        command.extend(["--tail", str(tail)])
    command.append(name)
    result = exec_command(
        command,
        capture_output=True,
    )
    assert_condition(result.returncode == 0, result.stderr)
    return result.stdout + result.stderr


def wait_for_mqtt_subscription(timeout=600, since=None):
    logger.info("Waiting for the web UI to subscribe to the detection MQTT topic")
    deadline = time.monotonic() + timeout
    last_report = time.monotonic()
    while True:
        logs = get_container_logs("web-ui", since=since)
        if "Subscribed to topic: yolo_od_results" in logs:
            logger.info("Web UI subscribed to yolo_od_results")
            return
        now = time.monotonic()
        if now >= deadline:
            assert_condition(False, f"Web UI did not subscribe to MQTT within {timeout} seconds")
        if now - last_report >= 30:
            logger.info("Still waiting for the web UI MQTT subscription")
            last_report = now
        time.sleep(2)


def wait_until_containers_ready(names=CONTAINERS, timeout=300, require_healthy=True):
    logger.info(
        "Waiting for %s containers to be running%s",
        len(names), " and healthy where applicable" if require_healthy else "",
    )
    deadline = time.monotonic() + timeout
    last_report = time.monotonic()
    details = ""
    while True:
        result = exec_command(["docker", "inspect", *names], capture_output=True)
        details = result.stdout + result.stderr
        if result.returncode == 0:
            containers = json.loads(result.stdout)
            if {container["Name"].lstrip("/") for container in containers} == set(names):
                def is_ready(container):
                    state = container["State"]
                    running = state["Status"] == "running" and not state["Restarting"]
                    healthy = state.get("Health", {}).get("Status", "healthy") == "healthy"
                    # The web-ui Docker healthcheck is a no-op with a five-minute
                    # interval; its real readiness is checked through HTTP and MQTT.
                    health_applies = require_healthy and container["Name"].lstrip("/") != "web-ui"
                    return running and (healthy or not health_applies)

                if all(is_ready(container) for container in containers):
                    logger.info("All requested containers are running and ready")
                    return
                pending = []
                for container in containers:
                    state = container["State"]
                    health = state.get("Health", {}).get("Status", "not configured")
                    if not is_ready(container):
                        pending.append(f"{container['Name'].lstrip('/')}: {state['Status']}, health={health}")
                details = "; ".join(pending)
        if time.monotonic() >= deadline:
            assert_condition(False, f"Containers did not become ready within {timeout} seconds: {details}")
        if time.monotonic() - last_report >= 15:
            logger.info("Still waiting for containers: %s", details)
            last_report = time.monotonic()
        time.sleep(5)