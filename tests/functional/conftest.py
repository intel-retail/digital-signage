#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import csv
import json
import logging
import os
import warnings
from urllib.parse import urlparse

import pytest
import requests
import urllib3

from utils.common_utils import APP_ROOT, CONTAINERS, assert_condition, exec_command, generate_test_credentials
from utils.advertisement_utils import wait_for_http_ready
from utils.deployment_utils import (
    get_deployed_containers,
    wait_for_mqtt_subscription,
    wait_until_containers_ready,
)

logger = logging.getLogger(__name__)


@pytest.fixture
def deployed_containers(setup_environment):
    return get_deployed_containers()


@pytest.fixture
def setup_environment(tmp_path_factory):
    logger.info("TC_SETUP_001: Preparing Digital Signage functional-test environment")
    logger.info("TC_SETUP_001 Step 1/4: Generating temporary WebRTC test credentials")
    host_ip = "127.0.0.1"
    env_path = APP_ROOT / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("HOST_IP="):
                host_ip = line.partition("=")[2].strip() or host_ip
                break

    test_env_file = tmp_path_factory.mktemp("digital-signage-test-env") / ".env"
    credentials = generate_test_credentials()
    test_env_file.write_text(
        f"HOST_IP={host_ip}\n"
        f"MTX_WEBRTCICESERVERS2_0_USERNAME={credentials['MTX_WEBRTCICESERVERS2_0_USERNAME']}\n"
        f"MTX_WEBRTCICESERVERS2_0_PASSWORD={credentials['MTX_WEBRTCICESERVERS2_0_PASSWORD']}\n",
        encoding="utf-8",
    )
    os.environ["ENV_FILE"] = str(test_env_file)
    for target in ("check_env_variables", "validate_host_ip"):
        logger.info("TC_SETUP_001 Step 2/4: Running make %s", target)
        result = exec_command(["make", target], capture_output=True)
        assert_condition(result.returncode == 0, result.stdout + result.stderr)

    logger.info("TC_SETUP_001 Step 3/4: Checking required model artifacts")
    result = exec_command(["make", "check_models"], capture_output=True)
    if result.returncode != 0:
        logger.info("Model artifacts are missing; running make download_models")
        result = exec_command(
            ["make", "download_models", "SKIP_LTX_VIDEO_EXPORT=true"],
            timeout=7200,
        )
        assert_condition(result.returncode == 0, f"make download_models failed with exit status {result.returncode}")
        result = exec_command(["make", "check_models"], capture_output=True)
    assert_condition(result.returncode == 0, result.stdout + result.stderr)
    logger.info("TC_SETUP_001 Step 3/4: Required model artifacts are ready")

    try:
        logger.info("TC_SETUP_001 Step 4/4: Starting stack with make up")
        result = exec_command(["make", "up"], timeout=900)
        assert_condition(result.returncode == 0, f"make up failed with exit status {result.returncode}")
        logger.info("TC_SETUP_001: Stack command completed; waiting for containers and service readiness")
        wait_until_containers_ready()
        wait_for_mqtt_subscription()
        logger.info("TC_SETUP_001: Stack is ready and web UI is subscribed to MQTT")
        yield
    finally:
        logger.info("TC_SETUP_001 Cleanup: Running make down and removing test volumes")
        down_result = exec_command(["make", "down"], capture_output=True, timeout=120)
        if down_result.stdout:
            logger.info("make down output:\n%s", down_result.stdout.rstrip())
        if down_result.stderr:
            logger.info("make down diagnostics:\n%s", down_result.stderr.rstrip())

        result = exec_command(["docker", "ps", "--all", "--format", "{{.Names}}"], capture_output=True)
        assert_condition(result.returncode == 0, result.stderr)
        remaining = sorted(set(result.stdout.splitlines()) & set(CONTAINERS))
        assert_condition(not remaining, f"Digital Signage containers remain after make down: {remaining}")
        if down_result.returncode != 0:
            details = down_result.stdout + down_result.stderr
            shared_network = "Resource is still in use" in details
            assert_condition(
                shared_network,
                f"make down failed with exit status {down_result.returncode}: {details}",
            )
            logger.warning("Compose kept the shared app network because another container is attached; app containers are removed")
        logger.info("TC_SETUP_001 Cleanup: Test stack removed")


@pytest.fixture
def controlled_advertisements(setup_environment, tmp_path, get_endpoint):
    logger.info("TC_AD_SETUP_001 Step 1/4: Selecting a catalog product with a predefined image")
    with (APP_ROOT / "web-ui" / "ProductAssociations.csv").open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        fieldnames = reader.fieldnames
        row = next(
            (entry for entry in reader if entry.get("pre_defined_ad_image")
             and (APP_ROOT / "web-ui" / "pre-defined-ads" / entry["pre_defined_ad_image"]).is_file()),
            None,
        )
    assert_condition(row is not None, "A catalog row with an existing predefined JPEG is required")
    logger.info("TC_AD_SETUP_001 Step 2/4: Preparing temporary catalog for product %s", row["primary_product"])
    catalog = tmp_path / "ProductAssociations.csv"
    with catalog.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)
    catalog.chmod(0o644)
    override = tmp_path / "compose-test.json"
    override.write_text(json.dumps({
        "services": {"web-ui": {
            "environment": {
                "OBJECT_RECENCY_FRAME_COUNT": "3",
                "OBJECT_CONFIDENCE_THRESHOLD": "0.8",
                "TIME_TO_DISPLAY_AD_SECONDS": "0",
                "QSR_EVENTS_URL": "",
                "BENCHMARK_MODE": "false",
            },
            "volumes": [{
                "type": "bind", "source": str(catalog),
                "target": "/app/ProductAssociations.csv", "read_only": True,
            }],
        }},
    }), encoding="utf-8")
    logger.info("TC_AD_SETUP_001 Step 3/4: Pausing simulation pipeline for controlled MQTT detections")
    result = exec_command(["docker", "pause", "dlstreamer-pipeline-server"], capture_output=True, timeout=120)
    assert_condition(result.returncode == 0, result.stdout + result.stderr)
    result = exec_command(
        ["docker", "compose", "-f", "docker-compose.yml", "-f", str(override),
         "up", "-d", "--no-deps", "--force-recreate", "web-ui"],
        capture_output=True, timeout=180,
    )
    assert_condition(result.returncode == 0, result.stdout + result.stderr)
    logger.info("TC_AD_SETUP_001 Step 3/4: Recreated web UI with temporary catalog")
    result = exec_command(["docker", "restart", "nginx_proxy"], capture_output=True, timeout=120)
    assert_condition(result.returncode == 0, result.stdout + result.stderr)
    running_names = tuple(name for name in get_deployed_containers() if name != "dlstreamer-pipeline-server")
    wait_until_containers_ready(names=running_names)
    wait_for_mqtt_subscription()
    wait_for_http_ready(get_endpoint)
    assert_condition(
        get_endpoint("/get_current_advertisement", params={"client_id": "functional-baseline"}).status_code == 204,
        "A controlled test must start with no camera or agent advertisement",
    )
    logger.info("TC_AD_SETUP_001 Step 4/4: MQTT and HTTP services are ready")
    yield row


@pytest.fixture
def api_request(setup_environment):
    base_url = os.getenv("DS_TEST_BASE_URL", "https://127.0.0.1:5000").rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise pytest.UsageError("DS_TEST_BASE_URL must be an HTTP(S) URL.")
    with requests.Session() as session:
        session.verify = os.getenv("REQUESTS_CA_BUNDLE") or False

        def request(method, path, **kwargs):
            with warnings.catch_warnings():
                if not session.verify:
                    warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
                kwargs.setdefault("timeout", 30)
                return session.request(
                    method, base_url + path, allow_redirects=False, **kwargs
                )

        yield request


@pytest.fixture
def get_endpoint(api_request):
    def get(path, **kwargs):
        return api_request("GET", path, **kwargs)

    return get