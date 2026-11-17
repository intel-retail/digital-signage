#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import re
import shutil
import logging

import pytest

from utils.common_utils import CONTAINERS, assert_condition
from utils.security_utils import get_compose_services, scan_published_tcp_ports, find_sensitive_values_in_logs


pytestmark = pytest.mark.security
logger = logging.getLogger(__name__)


def test_compose_security():
    logger.info("TC_SEC_001: Checking security settings declared in docker-compose.yml")
    services = get_compose_services()
    logger.info("Checking %s active Compose services", len(CONTAINERS))
    for name in CONTAINERS:
        assert_condition(name in services, f"{name} is missing from Compose")
        service = services[name]
        assert_condition(service.get("read_only") is True, f"{name} must declare read_only: true")
        assert_condition(not service.get("privileged", False), f"{name} must not declare privileged mode")
        assert_condition(
            any(option.split(":", 1)[0] == "no-new-privileges" for option in service.get("security_opt", [])),
            f"{name} must declare no-new-privileges",
        )
        logger.info("TC_SEC_001: Compose hardening passed for %s", name)


@pytest.mark.live
@pytest.mark.parametrize("name", CONTAINERS)
def test_container_security(deployed_containers, name):
    logger.info("TC_SEC_002: Checking runtime hardening settings for %s", name)
    config = deployed_containers[name]["HostConfig"]
    assert_condition(not config["Privileged"], f"{name} must not run privileged")
    assert_condition(config["ReadonlyRootfs"], f"{name} must use a read-only root filesystem")
    assert_condition(
        any(option.split(":", 1)[0] == "no-new-privileges" for option in (config["SecurityOpt"] or [])),
        f"{name} must disable privilege escalation",
    )
    logger.info("TC_SEC_002: Runtime hardening passed for %s", name)


@pytest.mark.live
@pytest.mark.parametrize("name", CONTAINERS)
def test_published_ports(deployed_containers, name):
    logger.info("TC_SEC_003: Checking published ports for %s", name)
    ports = deployed_containers[name]["NetworkSettings"]["Ports"] or {}
    published = {port for port, bindings in ports.items() if bindings}
    expected = {
        "nginx_proxy": {"15443/tcp"},
        "coturn": {"3478/tcp", "3478/udp"},
    }.get(name, set())
    logger.info("TC_SEC_003: %s published ports=%s; expected=%s", name, sorted(published), sorted(expected))
    assert_condition(published == expected, f"{name}: unexpected published ports {published}")


@pytest.mark.live
def test_nmap_ports(deployed_containers):
    scanner = shutil.which("nmap")
    if scanner is None:
        pytest.skip("Nmap is required for the published TCP-port scan; install it and rerun this test")
    logger.info("TC_SEC_004 Step 1/2: Scanning Compose-published TCP ports with Nmap")
    states = scan_published_tcp_ports(deployed_containers, scanner)
    logger.info("TC_SEC_004 Step 2/2: Nmap port states: %s", states)
    unavailable = {endpoint: state for endpoint, state in states.items() if state != "open"}
    assert_condition(not unavailable, f"Published TCP ports are not reachable: {unavailable}")


@pytest.mark.live
def test_secret_logs(deployed_containers):
    logger.info("TC_SEC_005: Checking recent container logs for configured secret values")
    leaks = find_sensitive_values_in_logs(deployed_containers)
    assert_condition(not leaks, "Configured secrets appeared in recent container logs: " + ", ".join(leaks))
    logger.info("TC_SEC_005: No configured secret values found in recent container logs")


@pytest.mark.live
@pytest.mark.parametrize("header,value", [
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "SAMEORIGIN"),
    ("Strict-Transport-Security", "max-age="),
])
def test_security_headers(get_endpoint, header, value):
    logger.info("TC_SEC_006: Checking nginx response header %s", header)
    response = get_endpoint("/")
    assert_condition(response.status_code == 200, f"UI: HTTP {response.status_code}")
    actual = response.headers.get(header, "")
    if header == "Strict-Transport-Security":
        match = re.search(r"(?:^|;)\s*max-age=(\d+)(?:;|$)", actual, re.IGNORECASE)
        assert_condition(match is not None and int(match.group(1)) > 0, "HSTS must set a positive max-age")
    else:
        assert_condition(actual.lower() == value.lower(), f"Missing or incorrect {header}: {actual!r}")
    logger.info("TC_SEC_006: Security header %s passed", header)


@pytest.mark.live
@pytest.mark.parametrize("payload", [{}, {"description": "functional test", "imgb64": "not-base64"}])
def test_invalid_ad_request(api_request, payload):
    logger.info("TC_SEC_007: Checking malformed predefined-ad request %s", "missing fields" if not payload else "invalid image")
    response = api_request("POST", "/aig-api/ase/predef/", json=payload)
    assert_condition(response.status_code == 400, "Invalid advertisement must be rejected before storage")
    body = response.json()
    if not payload:
        errors = body.get("errors", {})
        assert_condition(
            "description" in errors and "imgb64" in errors,
            f"Missing required-field validation details: {body}",
        )
    else:
        assert_condition(
            body.get("error", "").startswith("Invalid base64 image:"),
            f"Invalid image was rejected for an unexpected reason: {body}",
        )
    logger.info("TC_SEC_007: Malformed predefined-ad request was rejected as expected")