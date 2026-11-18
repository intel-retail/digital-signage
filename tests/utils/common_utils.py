#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import os
import secrets
import subprocess  # nosec B404 # exec_command explicitly disables shell execution
import string
from pathlib import Path
from typing import Sequence


APP_ROOT = Path(__file__).resolve().parents[2]
CONTAINERS = (
    "mqtt-broker",
    "ase-qdrant",
    "mediamtx",
    "coturn",
    "dlstreamer-pipeline-server",
    "aig-server",
    "web-ui",
    "nginx_proxy",
)


def generate_test_credentials():
    username = "".join(secrets.choice(string.ascii_letters) for _ in range(10))
    password = [secrets.choice(string.ascii_letters), secrets.choice(string.digits)]
    password.extend(secrets.choice(string.ascii_letters + string.digits) for _ in range(14))
    secrets.SystemRandom().shuffle(password)
    return {
        "MTX_WEBRTCICESERVERS2_0_USERNAME": username,
        "MTX_WEBRTCICESERVERS2_0_PASSWORD": "".join(password),
    }


def assert_condition(condition, message=""):
    assert condition, message  # nosec B101 # assertions intentionally fail functional tests


def _device_mount_path(device):
    path = Path("/dev") / device
    try:
        return str(path) if path.is_dir() and any(path.iterdir()) else "/dev/null"
    except OSError:
        return "/dev/null"


def exec_command(
        command: Sequence[str],
        *,
        capture_output: bool = False,
        check: bool = False,
        text: bool = True,
        **kwargs) -> subprocess.CompletedProcess:
    command = list(command)
    if command and os.path.basename(str(command[0])) == "make" and "-e" not in command[1:]:
        command.insert(1, "-e")
    kwargs.setdefault("cwd", APP_ROOT)
    command_env = kwargs.get("env")
    if command_env is None:
        command_env = {**os.environ, "PWD": str(APP_ROOT)}
    else:
        command_env = dict(command_env)
    if command[:2] == ["docker", "compose"]:
        command_env.setdefault("DRI_MOUNT_PATH", _device_mount_path("dri"))
        command_env.setdefault("ACCEL_MOUNT_PATH", _device_mount_path("accel"))
    kwargs["env"] = command_env
    kwargs.setdefault("timeout", 30)
    return subprocess.run(  # nosec B603 # test-defined argument lists execute with shell=False
        command,
        shell=False,
        capture_output=capture_output,
        check=check,
        text=text,
        **kwargs,
    )