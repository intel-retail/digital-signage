#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import logging
from uuid import uuid4

import pytest

from utils.common_utils import assert_condition, exec_command


pytestmark = pytest.mark.configuration
logger = logging.getLogger(__name__)


def test_host_ip(tmp_path):
    logger.info("TC_CFG_001: Checking valid and invalid HOST_IP values")
    cases = [
        ("127.0.0.1", True),
        ("192.168.1.10", True),
        ("", False),
        ("localhost", False),
        ("256.1.1.1", False),
        ("192.168.1", False),
        ("::1", False),
    ]
    env_file = tmp_path / ".env"
    for host_ip, valid in cases:
        logger.info("TC_CFG_001: Checking HOST_IP case %r (expected valid=%s)", host_ip, valid)
        env_file.write_text(f"HOST_IP={host_ip}\n", encoding="utf-8")
        result = exec_command(
            ["make", "--no-print-directory", f"ENV_FILE={env_file}", "validate_host_ip"],
            capture_output=True,
        )
        logger.info("TC_CFG_001: HOST_IP validation exit code=%s; expected valid=%s", result.returncode, valid)
        assert_condition(
            (result.returncode == 0) == valid,
            f"HOST_IP={host_ip!r}:\n{result.stdout}{result.stderr}",
        )


def test_webrtc_credentials(tmp_path):
    logger.info("TC_CFG_002: Checking WebRTC username and password validation cases")
    cases = [
        ("Signage", "valid", True),
        ("", "valid", False),
        ("Abcd", "valid", False),
        ("User123", "valid", False),
        ("Signage", "blank", False),
        ("Signage", "short", False),
        ("Signage", "letters_only", False),
        ("Signage", "digits_only", False),
        ("Signage", "special", False),
    ]
    generated = uuid4().hex + "A1"
    passwords = {
        "valid": generated,
        "blank": "",
        "short": generated[:3],
        "letters_only": "A" * 12,
        "digits_only": "1" * 12,
        "special": generated + "!",
    }
    env_file = tmp_path / ".env"
    for username, password_case, valid in cases:
        logger.info("TC_CFG_002: Checking username %r with password case %s (expected valid=%s)", username, password_case, valid)
        env_file.write_text(
            f"MTX_WEBRTCICESERVERS2_0_USERNAME={username}\n"
            f"MTX_WEBRTCICESERVERS2_0_PASSWORD={passwords[password_case]}\n",
            encoding="utf-8",
        )
        result = exec_command(
            ["make", "--no-print-directory", f"ENV_FILE={env_file}", "check_env_variables"],
            capture_output=True,
        )
        logger.info(
            "TC_CFG_002: Credential validation username=%r password_case=%s exit code=%s; expected valid=%s",
            username, password_case, result.returncode, valid,
        )
        assert_condition(
            (result.returncode == 0) == valid,
            f"Username={username!r}, password case={password_case}:\n{result.stdout}{result.stderr}",
        )