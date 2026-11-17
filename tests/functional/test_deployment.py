#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import logging
import pytest

from utils.common_utils import CONTAINERS, assert_condition, exec_command
from utils.advertisement_utils import wait_for_http_ready
from utils.deployment_utils import get_deployed_containers, wait_for_mqtt_subscription, wait_until_containers_ready


pytestmark = pytest.mark.live
logger = logging.getLogger(__name__)


def test_make_up(deployed_containers):
    logger.info("TC_DEPLOY_001: Verifying all Digital Signage containers after make up")
    for name in CONTAINERS:
        logger.info("TC_DEPLOY_001: Checking container %s", name)
        container = deployed_containers[name]
        state = container["State"]
        logger.info("%s status=%s restarting=%s health=%s", name, state["Status"], state["Restarting"], state.get("Health", {}).get("Status", "not configured"))
        assert_condition(state["Status"] == "running", f"{name}: {state}")
        assert_condition(not state["Restarting"], f"{name} is restarting")
        if "Health" in state and name != "web-ui":
            assert_condition(state["Health"]["Status"] == "healthy", f"{name}: {state['Health']}")
        elif name == "web-ui":
            logger.info("web-ui readiness is checked through HTTP and MQTT, not its five-minute no-op healthcheck")
        logger.info("TC_DEPLOY_001: Container %s passed state checks", name)


@pytest.mark.destructive
def test_multiple_runs(setup_environment, get_endpoint):
    previous_ids = {}
    logger.info("TC_DEPLOY_002: Checking three make up deployment cycles")
    for cycle in range(3):
        logger.info("TC_DEPLOY_002 Cycle %s/3 Step 1: Starting or reusing deployment", cycle + 1)
        if cycle:
            logger.info("Recreating deployment for cycle %s", cycle + 1)
            result = exec_command(["make", "up"], timeout=900)
            assert_condition(result.returncode == 0, f"make up failed with exit status {result.returncode}")
        wait_until_containers_ready(require_healthy=False)
        logger.info("TC_DEPLOY_002 Cycle %s/3 Step 2: Waiting for MQTT and HTTP readiness", cycle + 1)
        wait_for_mqtt_subscription()
        wait_for_http_ready(get_endpoint)
        logger.info("TC_DEPLOY_002 Cycle %s/3 Step 2: MQTT and HTTP readiness passed", cycle + 1)
        current = get_deployed_containers()
        for name, container in current.items():
            if cycle:
                assert_condition(container["Id"] != previous_ids[name], f"{name} was not recreated on cycle {cycle + 1}")
        logger.info("TC_DEPLOY_002 Cycle %s/3 Step 3: Verified %s containers", cycle + 1, len(current))
        previous_ids = {name: container["Id"] for name, container in current.items()}