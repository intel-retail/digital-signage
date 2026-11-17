#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

from io import BytesIO
import logging
from uuid import uuid4

import pytest
from PIL import Image

from utils.advertisement_utils import (
    assert_no_advertisement,
    get_signage_events,
    publish_detection,
    wait_for_advertisement,
)
from utils.common_utils import assert_condition


pytestmark = [pytest.mark.live, pytest.mark.advertisements, pytest.mark.destructive]
logger = logging.getLogger(__name__)


@pytest.mark.parametrize("normalize_label,confidence", [
    pytest.param(False, 0.9, id="predefined-and-multiple-clients"),
    pytest.param(False, 0.8, id="confidence-boundary"),
    pytest.param(True, 0.9, id="label-normalization"),
])
def test_ad_delivery(controlled_advertisements, get_endpoint, normalize_label, confidence):
    product = controlled_advertisements["primary_product"]
    label = f"  {product.upper()}  " if normalize_label else product
    logger.info("TC_AD_001: Product=%s confidence=%.2f normalized=%s", product, confidence, normalize_label)
    logger.info("TC_AD_001 Step 1/4: Publishing controlled product detection")
    publish_detection(label, confidence=confidence)
    logger.info("TC_AD_001 Step 2/4: Waiting for predefined ad delivery")
    response = wait_for_advertisement(get_endpoint)
    logger.info("TC_AD_001 Step 3/4: Ad returned HTTP %s, content type=%s, bytes=%s", response.status_code, response.headers.get("Content-Type"), len(response.content))
    assert_condition(response.headers.get("Content-Type", "").startswith("image/jpeg"), "Expected JPEG")
    with Image.open(BytesIO(response.content)) as image:
        image.verify()
        logger.info("TC_AD_001: Predefined image is valid %sx%s JPEG", image.width, image.height)
    events = get_signage_events()
    assert_condition(any(
        event["event_type"] == "ad_displayed"
        and event["data"] == {"product": product, "variant": "predefined", "media": "image", "trigger": "camera"}
        for event in events
    ), "The known product was not delivered through the predefined camera-ad path")
    logger.info("TC_AD_001 Step 4/4: Verified predefined camera ad_displayed event for %s", product)

    if not normalize_label and confidence == 0.9:
        ad_id = response.headers.get("X-Ad-Id")
        assert_condition(ad_id is not None, "Camera advertisement must include its generation ID")
        for client_id in (f"functional-{uuid4().hex}", f"functional-{uuid4().hex}"):
            current = get_endpoint("/get_current_advertisement", params={"client_id": client_id})
            logger.info(
                "TC_AD_001: Client ID=%s received HTTP %s, ad ID=%s",
                client_id, current.status_code, current.headers.get("X-Ad-Id"),
            )
            assert_condition(current.status_code == 200, "Each new client must receive the current ad")
            assert_condition(current.content == response.content, "Clients received different ad bytes")
            assert_condition(current.headers.get("X-Ad-Id") == ad_id, "Clients received different generations")
            repeated = get_endpoint("/get_current_advertisement", params={"client_id": client_id})
            logger.info("TC_AD_001: Repeat poll for client ID=%s returned HTTP %s", client_id, repeated.status_code)
            assert_condition(repeated.status_code == 204, "A client received the same generation twice")


@pytest.mark.parametrize("confidence,count", [(0.79, 3), (0.9, 2)])
def test_detection_filter(controlled_advertisements, get_endpoint, confidence, count):
    product = controlled_advertisements["primary_product"]
    logger.info("TC_AD_002: Checking that %s detections at confidence %.2f do not produce an ad", count, confidence)
    publish_detection(product, confidence=confidence, count=count)
    assert_no_advertisement(get_endpoint)
    assert_condition(not get_signage_events(), "An ineligible detection emitted a signage event")
    logger.info("TC_AD_002: Ineligible detections produced no ad and no signage event")


def test_unknown_product(controlled_advertisements, get_endpoint):
    label = f"unknown-{uuid4().hex}"
    logger.info("TC_AD_003: Checking that an unknown product label is ignored")
    publish_detection(label)
    assert_no_advertisement(get_endpoint)
    logger.info("TC_AD_003: Unknown product produced no advertisement")
    assert_condition(
        not any(event["event_type"] == "ad_displayed" for event in get_signage_events()),
        "An unknown product caused an advertisement display event",
    )