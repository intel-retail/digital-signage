#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import logging
import pytest

from utils.advertisement_utils import wait_for_advertisement
from utils.common_utils import assert_condition


pytestmark = [pytest.mark.live, pytest.mark.api]
logger = logging.getLogger(__name__)


def test_web_ui(get_endpoint):
    logger.info("TC_API_001: Checking landscape and portrait web UI pages")
    for path in ("/", "/portrait"):
        logger.info("TC_API_001: Requesting %s", path)
        response = get_endpoint(path)
        logger.info("TC_API_001: %s returned HTTP %s (%s)", path, response.status_code, response.headers.get("Content-Type"))
        assert_condition(response.status_code == 200, f"{path}: HTTP {response.status_code}")
        assert_condition("text/html" in response.headers.get("Content-Type", ""), f"{path}: expected HTML")
        assert_condition("<html" in response.text.lower(), f"{path}: missing HTML page")


def test_health(get_endpoint):
    logger.info("TC_API_002: Checking valid and invalid AIG health identifiers")
    cases = ((7, 200), ("not-an-integer", 404))
    for identifier, expected_status in cases:
        response = get_endpoint(f"/aig-api/aig/hstatus/{identifier}")
        logger.info("TC_API_002: AIG health ID=%r returned HTTP %s; expected HTTP %s", identifier, response.status_code, expected_status)
        assert_condition(
            response.status_code == expected_status,
            f"AIG health for ID {identifier!r}: HTTP {response.status_code}",
        )
        if expected_status == 200:
            assert_condition(
                response.json() == {"status": "ok", "id": identifier},
                "Unexpected health response",
            )
            logger.info("TC_API_002: Health response JSON matched ID %r", identifier)


def test_api_docs(get_endpoint):
    logger.info("TC_API_003 Step 1/2: Requesting Swagger UI")
    response = get_endpoint("/aig-api/")
    logger.info("TC_API_003: Swagger UI returned HTTP %s", response.status_code)
    logger.info("Swagger UI returned HTTP %s", response.status_code)
    assert_condition(response.status_code == 200, f"Swagger UI: HTTP {response.status_code}")
    assert_condition("text/html" in response.headers.get("Content-Type", ""), "Expected HTML")
    assert_condition('id="swagger-ui"' in response.text.lower(), "Missing Swagger UI container")

    specification = get_endpoint("/aig-api/swagger.json")
    logger.info("TC_API_003 Step 2/2: Swagger spec returned HTTP %s", specification.status_code)
    logger.info("AIG API specification returned HTTP %s", specification.status_code)
    assert_condition(specification.status_code == 200, "AIG Swagger specification is unavailable")
    spec = specification.json()
    assert_condition(spec.get("info", {}).get("title") == "AIG Server", "Unexpected AIG API specification")
    assert_condition("/aig/hstatus/{id}" in spec.get("paths", {}), "AIG health route is missing from the specification")
    logger.info("TC_API_003: Swagger UI and expected AIG health route are present")


def test_current_ad(get_endpoint):
    logger.info("TC_API_004: Waiting for the signage flow to deliver an advertisement")
    response = wait_for_advertisement(get_endpoint)
    assert_condition(response.status_code == 200, f"Current ad: HTTP {response.status_code}")
    assert_condition(response.content, "The current advertisement is empty")
    media_type = response.headers.get("Content-Type", "").split(";", 1)[0]
    logger.info("TC_API_004: Ad delivered with HTTP %s, media=%s, bytes=%s", response.status_code, media_type, len(response.content))
    assert_condition(
        media_type in ("image/jpeg", "image/webp", "image/gif", "video/mp4"),
        f"Unexpected advertisement media type: {media_type}",
    )