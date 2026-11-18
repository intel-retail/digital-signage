#
# Apache v2 license
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import ipaddress
import re

import yaml
from defusedxml import ElementTree

from utils.common_utils import APP_ROOT, assert_condition, exec_command
from utils.deployment_utils import get_container_logs


def get_compose_services():
    with (APP_ROOT / "docker-compose.yml").open(encoding="utf-8") as source:
        config = yaml.safe_load(source)
    return {
        service.get("container_name", name): service
        for name, service in config["services"].items()
        if not service.get("profiles")
    }


def scan_published_tcp_ports(containers, scanner):
    targets = {}
    for container in containers.values():
        for port, bindings in (container["NetworkSettings"]["Ports"] or {}).items():
            if not port.endswith("/tcp"):
                continue
            for binding in bindings or []:
                address = ipaddress.ip_address(binding["HostIp"])
                if address.is_unspecified:
                    address = ipaddress.ip_address("::1" if address.version == 6 else "127.0.0.1")
                host_port = int(binding["HostPort"])
                assert_condition(1 <= host_port <= 65535, "Invalid published port")
                targets.setdefault(address, set()).add(host_port)
    assert_condition(targets, "No published TCP ports found to scan")
    states = {}
    for address, ports in targets.items():
        command = [scanner, "-sT", "-Pn", "-n", "--host-timeout", "30s", "--max-retries", "1"]
        if address.version == 6:
            command.append("-6")
        command.extend(["-p", ",".join(str(port) for port in sorted(ports)), "-oX", "-", str(address)])
        result = exec_command(command, capture_output=True, timeout=45)
        assert_condition(result.returncode == 0, f"Nmap failed for {address}: {result.stderr}")
        report = ElementTree.fromstring(result.stdout)
        scanned = {
            int(port.attrib["portid"]): port.find("state").attrib["state"]
            for port in report.findall("./host/ports/port")
            if port.attrib.get("protocol") == "tcp" and port.find("state") is not None
        }
        for port in ports:
            states[f"[{address}]:{port}"] = scanned.get(port, "not-reported")
    return states


def find_sensitive_values_in_logs(containers):
    secret_key = re.compile(r"(?:^|_)(?:PASSWORD|PASS|TOKEN|SECRET|API_KEY|PRIVATE_KEY|ACCESS_KEY)(?:_|$)", re.I)
    secrets = {}
    for name, container in containers.items():
        for setting in container["Config"].get("Env") or []:
            key, separator, value = setting.partition("=")
            if separator and value and secret_key.search(key):
                secrets[f"{name}:{key}"] = value
    assert_condition(secrets, "No configured runtime secrets were available for the log check")
    leaks = []
    for name in containers:
        logs = get_container_logs(name, tail=1000)
        for field, value in secrets.items():
            if value in logs:
                leaks.append(f"{name} ({field})")
    return leaks