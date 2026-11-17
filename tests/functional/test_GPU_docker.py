#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import logging
import pytest

from utils.common_utils import CONTAINERS, assert_condition, exec_command
from utils.deployment_utils import wait_until_containers_ready
from utils.device_utils import (
    assert_aig_image_inference,
    assert_device_visible,
    assert_dlstreamer_device_configured,
    configure_dlstreamer,
    device_available,
    wait_for_device_detection,
    wait_for_pipeline,
)


pytestmark = [pytest.mark.live, pytest.mark.gpu]
logger = logging.getLogger(__name__)


@pytest.mark.skipif(not device_available("GPU"), reason="No GPU render device found")
def test_pid_gpu(setup_environment, tmp_path, api_request):
    logger.info("TC_GPU_001: DL Streamer PID inference on GPU")
    logger.info("TC_GPU_001 Step 1/5: Reading existing pipeline state")
    previous = api_request("GET", "/dsps-api/pipelines/status")
    logger.info("Initial DL Streamer status returned HTTP %s", previous.status_code)
    assert_condition(previous.status_code == 200, "Could not read initial DL Streamer status")
    previous_ids = {instance.get("id") for instance in previous.json()}
    override = configure_dlstreamer("GPU", tmp_path)
    logger.info("TC_GPU_001 Step 2/5: Prepared temporary GPU PID pipeline configuration")
    try:
        result = exec_command(
            ["docker", "compose", "-f", "docker-compose.yml", "-f", str(override),
             "up", "-d", "--no-deps", "--force-recreate", "dlstreamer-pipeline-server"],
            capture_output=True, timeout=300,
        )
        logger.info("TC_GPU_001 Step 3/5: Recreated pipeline (exit code=%s)", result.returncode)
        assert_condition(result.returncode == 0, result.stdout + result.stderr)
        assert_device_visible("dlstreamer-pipeline-server", "GPU")
        logger.info("TC_GPU_001 Step 4/5: GPU device node is visible inside DL Streamer")
        assert_dlstreamer_device_configured("GPU")
        logger.info("TC_GPU_001 Step 4/5: DL Streamer loaded GPU configuration")
        instance_id = wait_for_pipeline(api_request, previous_ids, timeout=180)
        logger.info("TC_GPU_001 Step 5/5: Pipeline is running (instance ID=%s); waiting for detection", instance_id)
        detection = wait_for_device_detection(instance_id)
        assert_condition(detection["label"], "GPU pipeline returned a detection without a label")
        assert_condition(detection["confidence"] > 0, "GPU pipeline returned an invalid confidence score")
        logger.info("TC_GPU_001: Detected %s at confidence %.3f", detection["label"], detection["confidence"])
    finally:
        logger.info("TC_GPU_001 Cleanup: Restoring the default DL Streamer pipeline configuration")
        result = exec_command(
            ["docker", "compose", "up", "-d", "--no-deps", "--force-recreate", "dlstreamer-pipeline-server"],
            capture_output=True, timeout=300,
        )
        assert_condition(result.returncode == 0, result.stdout + result.stderr)
        wait_until_containers_ready(names=CONTAINERS)


@pytest.mark.skipif(not device_available("GPU"), reason="No GPU render device found")
def test_aig_gpu(api_request):
    logger.info("TC_GPU_002 Step 1/2: Checking GPU visibility in AIG")
    assert_device_visible("aig-server", "GPU")
    logger.info("TC_GPU_002 Step 2/2: Requesting and validating AIG GPU image inference")
    assert_aig_image_inference(api_request, "GPU")