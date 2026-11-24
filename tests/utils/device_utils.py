#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import glob
import json
import logging
import time

from utils.common_utils import APP_ROOT, assert_condition, exec_command

logger = logging.getLogger(__name__)


def device_available(device):
    paths = {"GPU": "/dev/dri/renderD*", "NPU": "/dev/accel/accel*"}
    return bool(glob.glob(paths[device.upper()]))


def assert_device_visible(container, device):
    device = device.upper()
    directory = {"GPU": "/dev/dri", "NPU": "/dev/accel"}[device]
    result = exec_command(["docker", "exec", container, "ls", "-1", directory], capture_output=True)
    node_prefix = "renderD" if device == "GPU" else "accel"
    nodes = result.stdout.splitlines()
    assert_condition(
        result.returncode == 0 and any(node.startswith(node_prefix) for node in nodes),
        f"{device} device node is not visible in {container}: {nodes}",
    )


def assert_dlstreamer_device_configured(device):
    result = exec_command(
        ["docker", "exec", "dlstreamer-pipeline-server", "cat", "/home/pipeline-server/config.json"],
        capture_output=True,
    )
    assert_condition(result.returncode == 0, result.stderr)
    config = json.loads(result.stdout)
    pipeline_devices = [
        pipeline.get("payload", {}).get("parameters", {}).get("detection-properties", {}).get("device")
        for pipeline in config.get("config", {}).get("pipelines", [])
    ]
    assert_condition(pipeline_devices and all(value == device.upper() for value in pipeline_devices),
                     f"DL Streamer did not load the {device} PID configuration: {pipeline_devices}")


def configure_dlstreamer(device, directory):
    logger.info("Preparing temporary DL Streamer PID config for %s", device.upper())
    config_path = APP_ROOT / "configs" / "pid" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    pipelines = config.get("config", {}).get("pipelines", [])
    assert_condition(pipelines, "No DL Streamer pipeline is configured")
    for pipeline in pipelines:
        detection = pipeline.get("payload", {}).get("parameters", {}).get("detection-properties")
        assert_condition(detection is not None, "DL Streamer pipeline has no detection properties")
        detection["device"] = device.upper()

    override_config = directory / "pid-config.json"
    override_config.write_text(json.dumps(config, indent=2), encoding="utf-8")
    override_config.chmod(0o644)
    override_compose = directory / "compose-device.json"
    override_compose.write_text(json.dumps({
        "services": {"dlstreamer-pipeline-server": {
            "volumes": [{
                "type": "bind",
                "source": str(override_config),
                "target": "/home/pipeline-server/config.json",
                "read_only": True,
            }],
        }},
    }), encoding="utf-8")
    result = exec_command(
        ["docker", "compose", "-f", "docker-compose.yml", "-f", str(override_compose), "config", "--format", "json"],
        capture_output=True,
    )
    assert_condition(result.returncode == 0, result.stdout + result.stderr)
    merged = json.loads(result.stdout)
    mounts = [mount for mount in merged["services"]["dlstreamer-pipeline-server"]["volumes"]
              if mount.get("target") == "/home/pipeline-server/config.json"]
    assert_condition(len(mounts) == 1, "Temporary device configuration did not replace the PID config mount")
    assert_condition(mounts[0]["source"] == str(override_config), "Compose is not using the temporary PID config")
    return override_compose


def wait_for_pipeline(api_request, previous_ids, timeout=180):
    logger.info("Waiting up to %s seconds for the %s pipeline to start", timeout, "configured")
    deadline = time.monotonic() + timeout
    last_report = time.monotonic()
    details = ""
    while True:
        response = api_request("GET", "/dsps-api/pipelines/status")
        if response.status_code == 200:
            instances = response.json()
            for instance in instances:
                if instance.get("state") == "RUNNING" and instance.get("id") not in previous_ids:
                    logger.info("New DL Streamer pipeline is running: %s", instance["id"])
                    return instance["id"]
            details = str(instances)
        else:
            details = f"HTTP {response.status_code}: {response.text[:500]}"
        if time.monotonic() >= deadline:
            assert_condition(False, f"New DL Streamer pipeline did not become RUNNING: {details}")
        if time.monotonic() - last_report >= 15:
            logger.info("DL Streamer pipeline is not running yet: %s", details)
            last_report = time.monotonic()
        time.sleep(2)


def wait_for_device_detection(instance_id, timeout=120):
    logger.info("Waiting up to %s seconds for detections from pipeline %s", timeout, instance_id)
    deadline = time.monotonic() + timeout
    last_shape_log = 0.0
    while time.monotonic() < deadline:
        result = exec_command(
            ["docker", "exec", "mqtt-broker", "mosquitto_sub", "-h", "127.0.0.1",
             "-t", "yolo_od_results", "-C", "1", "-W", "5"],
            capture_output=True, timeout=8,
        )
        if result.returncode == 0:
            try:
                message = json.loads(result.stdout)
            except json.JSONDecodeError:
                continue
            tensors = [
                tensor
                for metadata in message.get("metadata", {}).get("gva_meta", [])
                for tensor in metadata.get("tensor", [])
                if isinstance(tensor, dict)
                and isinstance(tensor.get("label"), str)
                and tensor["label"].strip()
                and isinstance(tensor.get("confidence", 0), (int, float))
                and tensor["confidence"] > 0
            ]
            if tensors:
                logger.info("Received detection from pipeline %s: %s (confidence=%.3f)",
                            instance_id, tensors[0]["label"], tensors[0]["confidence"])
                return tensors[0]
            if time.monotonic() - last_shape_log >= 30:
                pipeline_id = message.get("pipeline", {}).get("instance_id")
                logger.debug("Received MQTT message without a valid detection; pipeline instance=%s; keys=%s",
                             pipeline_id, sorted(message.keys()))
                last_shape_log = time.monotonic()
    assert_condition(False, f"No real detections received from DL Streamer instance {instance_id}")


def assert_aig_image_inference(api_request, device):
    logger.info("Requesting AIG image inference on %s", device)
    response = api_request(
        "POST",
        "/aig-api/aig/minf/",
        json={
            "description": "A simple red apple on a clean white background, product photo",
            "device": device,
            "seed": 19,
        },
        timeout=600,
    )
    assert_condition(response.status_code == 200, f"AIG {device} inference failed: HTTP {response.status_code} {response.text[:500]}")
    assert_condition(response.headers.get("Content-Type", "").startswith("image/jpeg"), "AIG did not return a JPEG image")
    from io import BytesIO
    from PIL import Image

    with Image.open(BytesIO(response.content)) as image:
        assert_condition(image.format == "JPEG", "AIG response is not a decodable JPEG")
        assert_condition(image.width > 0 and image.height > 0, "AIG returned an empty image")
        logger.info("AIG %s inference returned a valid %sx%s JPEG", device, image.width, image.height)