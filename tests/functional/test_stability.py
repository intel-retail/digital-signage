#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import time
import logging
from datetime import datetime, timezone

import pytest

from utils.advertisement_utils import publish_detection, wait_for_advertisement, wait_for_http_ready
from utils.common_utils import CONTAINERS, assert_condition, exec_command
from utils.deployment_utils import (
    get_deployed_containers,
    wait_for_mqtt_subscription,
    wait_until_containers_ready,
)


pytestmark = [pytest.mark.live, pytest.mark.stability, pytest.mark.destructive]
logger = logging.getLogger(__name__)

ACTIVE_CONTAINERS = tuple(name for name in CONTAINERS if name != "dlstreamer-pipeline-server")


@pytest.mark.parametrize("name", ["mqtt-broker", "web-ui", "aig-server"])
def test_restart_recovery(controlled_advertisements, get_endpoint, name):
    logger.info("TC_STAB_001: Restart recovery for %s", name)
    logger.info("TC_STAB_001 Step 1/4: Recording current container start time")
    started = datetime.now(timezone.utc).isoformat()
    before = get_deployed_containers((name,))[name]["State"]["StartedAt"]
    logger.info("TC_STAB_001 Step 2/4: Restarting %s", name)
    result = exec_command(["docker", "restart", name], capture_output=True, timeout=120)
    logger.info("TC_STAB_001 Step 2/4: docker restart %s exit code=%s", name, result.returncode)
    assert_condition(result.returncode == 0, result.stdout + result.stderr)
    logger.info("TC_STAB_001 Step 3/4: Waiting for dependent containers to recover")
    wait_until_containers_ready(names=ACTIVE_CONTAINERS)
    after = get_deployed_containers((name,))[name]["State"]["StartedAt"]
    assert_condition(after != before, f"{name} was not restarted")
    logger.info("TC_STAB_001 Step 3/4: %s restarted; waiting for service readiness", name)
    if name in ("mqtt-broker", "web-ui"):
        wait_for_mqtt_subscription(since=started)
    wait_for_http_ready(get_endpoint)
    logger.info("TC_STAB_001 Step 4/4: Publishing a detection and checking ad recovery")
    publish_detection(controlled_advertisements["primary_product"])
    response = wait_for_advertisement(get_endpoint, require_ad_id=True)
    assert_condition(response.headers.get("X-Ad-Id") is not None, "Ad delivery did not recover")
    logger.info("TC_STAB_001: Ad delivery recovered after restarting %s (ad ID=%s)", name, response.headers.get("X-Ad-Id"))


def test_stability(controlled_advertisements, get_endpoint):
    logger.info("TC_STAB_002: Starting three-minute ad-delivery and container-stability check")
    logger.info("TC_STAB_002 Step 1/3: Recording initial container state")
    before = get_deployed_containers(ACTIVE_CONTAINERS)
    ad_ids = set()
    deadline = time.monotonic() + 180
    logger.info("TC_STAB_002 Step 2/3: Polling ad delivery and container health for 180 seconds")
    while time.monotonic() < deadline:
        logger.info("Publishing a controlled detection and checking the current ad")
        publish_detection(controlled_advertisements["primary_product"])
        response = wait_for_advertisement(get_endpoint, timeout=30, require_ad_id=True)
        ad_id = response.headers.get("X-Ad-Id")
        assert_condition(ad_id is not None, "Camera advertisement is missing its generation ID")
        ad_ids.add(ad_id)
        logger.info("Stability sample: ad ID=%s, total distinct ads=%s", ad_id, len(ad_ids))
        current = get_deployed_containers(ACTIVE_CONTAINERS)
        for name, container in current.items():
            state = container["State"]
            assert_condition(state["Status"] == "running" and not state["Restarting"], f"{name}: {state}")
            if name != "web-ui":
                assert_condition(state.get("Health", {}).get("Status", "healthy") == "healthy", f"{name}: {state}")
            assert_condition(container["RestartCount"] == before[name]["RestartCount"], f"{name} restarted")
            assert_condition(state["StartedAt"] == before[name]["State"]["StartedAt"], f"{name} was recreated")
        logger.info("Container health and restart counts remain unchanged")
        time.sleep(min(10, max(0, deadline - time.monotonic())))
    assert_condition(len(ad_ids) > 1, "Advertisements did not continue updating during the stability run")
    logger.info("TC_STAB_002 Step 3/3: Passed with %s distinct ad generations", len(ad_ids))