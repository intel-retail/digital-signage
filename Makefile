#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

INCLUDE ?= default_INCLUDE

DOCKER_COMPOSE_FILE = ./docker-compose.yml
DOCKER_COMPOSE = docker compose
SECURE_MODE='false'
MODEL_DOWNLOAD_PORT ?= 8000
export MODEL_DOWNLOAD_PORT

DRI_MOUNT_PATH := $(shell [ -d /dev/dri ] && [ -n "$$(ls -A /dev/dri 2>/dev/null)" ] && echo "/dev/dri" || echo "/dev/null")
export DRI_MOUNT_PATH

ACCEL_MOUNT_PATH := $(shell [ -d /dev/accel ] && [ -n "$$(ls -A /dev/accel 2>/dev/null)" ] && echo "/dev/accel" || echo "/dev/null")
export ACCEL_MOUNT_PATH

# Define the path to the .env file and scripts
ENV_FILE = ./.env
HELM_PACKAGE_SCRIPT = ./package_helm.sh

include $(ENV_FILE)
export $(shell sed 's/=.*//' $(ENV_FILE))

# Default values
KEY_LENGTH=3072
DAYS=365
SHA_ALGO="sha384"

# Build Docker containers
.PHONY: build
build:
	@echo "Building Docker containers..."
	$(DOCKER_COMPOSE) build --pull;

.PHONY: download_models
download_models:
	@echo "Downloading Digital Signage models with the model-download microservice..."
	./scripts/download_models.sh

COLLECT_METRICS ?= true
UP_SKIP_DOWN ?= false
BENCHMARK_WARMUP_SECONDS ?= 300
SKIP_BENCHMARK_STACK_RESET ?= false
RESULTS_ROOT := $(or $(RESULTS_PATH),results)
# One folder per make invocation; benchmark-all passes RUN_ID to sub-makes so they share it.
ifndef RUN_ID
RUN_ID := $(shell date +%Y%m%d_%H%M%S)
endif
RUN_DIR := $(abspath $(RESULTS_ROOT)/$(RUN_ID))
METRICS_DURATION ?= $(or $(BENCHMARK_DURATION),300)
METRICS_QMASSA_CYCLE ?= $(or $(QMASSA_CYCLE_SECONDS),$(shell expr $(METRICS_DURATION) + 60))
AIG_DEVICE ?= $(or $(BENCHMARK_DEVICE),GPU)
PID_DEVICE ?= CPU
PID_CONFIG ?= configs/pid/config.json
AIG_ENV_FILE ?= $(ENV_FILE)
SKIP_BENCHMARK_DEVICE_CONFIG ?= false
SKIP_PERFORMANCE_TOOLS_BUILD ?= false
# Benchmark targets start every service with instrumentation on; normal runs leave it off.
BENCHMARK_MODE ?= false
METRICS_COMPOSE = QMASSA_CYCLE_SECONDS=$(METRICS_QMASSA_CYCLE) docker compose -p signage-metrics -f performance-tools/docker/docker-compose.yaml
# The live /metrics API keeps only the last 60 samples, so export the full run from raw logs.
METRICS_EXPORT = METRICS_GPU_MAX_POINTS=1000000 RESULTS_DIR="$$log_dir" python3 -c 'import json,sys; sys.path.insert(0,"performance-tools/live-metrics"); from metrics_parser import build_metrics_payload; json.dump(build_metrics_payload(window=10**9), open(sys.argv[1],"w"), indent=2)'

# $(1): metrics file prefix, $(2): command to run while metrics are collected.
define run_with_metrics
	@set -eu; \
	mkdir -p "$(RUN_DIR)"; \
	stats_prefix="$(RUN_DIR)/$(1)_docker_stats"; \
	stats_ready="$$stats_prefix.$$$$.ready"; \
	stats_pid=; \
	start_docker_stats() { python3 performance-tools/benchmark-scripts/benchmark_signage_docker_stats.py --output-prefix "$$stats_prefix" --host-metrics "$(RUN_DIR)/$(1)_metrics.json" --ready-file "$$stats_ready" & stats_pid=$$!; while [ ! -f "$$stats_ready" ]; do if ! kill -0 "$$stats_pid" 2>/dev/null; then wait "$$stats_pid"; return $$?; fi; done; }; \
	stop_docker_stats() { if [ -n "$$stats_pid" ]; then kill -TERM "$$stats_pid" 2>/dev/null || true; stats_status=0; wait "$$stats_pid" || stats_status=$$?; stats_pid=; return "$$stats_status"; fi; }; \
	trap 'stop_docker_stats || true' EXIT; \
	if [ "$(COLLECT_METRICS)" != true ]; then \
		start_docker_stats; \
		status=0; $(2) || status=$$?; \
		stats_status=0; stop_docker_stats || stats_status=$$?; \
		if [ $$status -eq 0 ]; then status=$$stats_status; fi; \
		exit $$status; \
	fi; \
	if docker inspect metrics-collector >/dev/null 2>&1; then \
		project=$$(docker inspect --format '{{ index .Config.Labels "com.docker.compose.project" }}' metrics-collector); \
		if [ "$$project" != signage-metrics ]; then \
			echo "metrics-collector belongs to Compose project '$$project'; refusing to remove it" >&2; exit 1; \
		fi; \
	fi; \
	export log_dir="$(RUN_DIR)/$(1)_raw_metrics"; \
	mkdir -p "$$log_dir"; \
	$(METRICS_COMPOSE) down --remove-orphans 2>/dev/null; \
	trap 'stop_docker_stats || true; $(METRICS_COMPOSE) down --remove-orphans' EXIT; \
	$(METRICS_COMPOSE) up -d --no-build; \
	if ! curl -fsS --retry 30 --retry-connrefused --retry-delay 1 http://localhost:9000/health > /dev/null 2>&1; then \
		echo "Performance-tools metrics API did not become healthy at http://localhost:9000/health" >&2; exit 1; \
	fi; \
	start_docker_stats; \
	echo "Collecting host metrics into $$log_dir"; \
	status=0; $(2) || status=$$?; \
	$(METRICS_EXPORT) "$(RUN_DIR)/$(1)_metrics.json"; \
	curl -fsS http://localhost:9000/platform-info -o "$(RUN_DIR)/$(1)_platform_info.json"; \
	stats_status=0; stop_docker_stats || stats_status=$$?; \
	if [ $$status -eq 0 ]; then status=$$stats_status; fi; \
	echo "Results saved in $(RUN_DIR)"; \
	exit $$status
endef

BENCHMARK_PID_CMD = python3 performance-tools/benchmark-scripts/benchmark_signage_pid.py --duration $(or $(BENCHMARK_DURATION),300) --device $(PID_DEVICE) --no-restart --output $(RUN_DIR) $(if $(GPU_METRICS),--gpu-metrics $(GPU_METRICS),)
BENCHMARK_AIG_CMD = python3 performance-tools/benchmark-scripts/benchmark_signage_aig.py --iterations $(or $(BENCHMARK_ITERATIONS),10) --duration $(or $(BENCHMARK_DURATION),300) --device $(AIG_DEVICE) --output $(RUN_DIR) $(if $(filter true,$(BENCHMARK_INSECURE)),--insecure,) $(if $(filter true,$(BENCHMARK_COLD_START)),--cold-start,)
BENCHMARK_WEB_UI_CMD = python3 performance-tools/benchmark-scripts/benchmark_signage_web_ui.py --duration $(or $(BENCHMARK_DURATION),300) --output $(RUN_DIR)
BENCHMARK_QDRANT_CMD = python3 performance-tools/benchmark-scripts/benchmark_signage_qdrant.py --sizes $(or $(QDRANT_SIZES),100 1000) --queries $(or $(QDRANT_QUERIES),30) --output $(RUN_DIR)
# PID (passive) and Web UI trace capture run concurrently over the same live-pipeline window.
BENCHMARK_E2E_CMD = ( python3 performance-tools/benchmark-scripts/benchmark_signage_pid.py --duration $(or $(BENCHMARK_DURATION),300) --no-restart --output $(RUN_DIR) & pid_job=$$!; web_status=0; $(BENCHMARK_WEB_UI_CMD) || web_status=$$?; pid_status=0; wait $$pid_job || pid_status=$$?; if [ $$pid_status -ne 0 ]; then exit $$pid_status; fi; exit $$web_status )
CONSOLIDATE_CMD = python3 performance-tools/benchmark-scripts/benchmark_signage_consolidate_e2e.py --results $(RUN_DIR)

.PHONY: update-submodules
update-submodules:
	@echo "Cloning/updating performance tool repositories..."
	git submodule deinit -f .
	git submodule update --init --recursive --remote
	@echo "Submodules updated successfully."

.PHONY: build-performance-tools
build-performance-tools:
	@if [ "$(COLLECT_METRICS)" = true ]; then log_dir=/tmp $(METRICS_COMPOSE) build benchmark; fi

.PHONY: benchmark-configure-devices
benchmark-configure-devices:
	@python3 -c 'import json,sys; from pathlib import Path; pid_device,aig_device,pid_file,env_file=sys.argv[1:]; assert pid_device in ("CPU","GPU","NPU"), "PID_DEVICE must be CPU, GPU, or NPU"; assert aig_device in ("CPU","GPU"), "AIG_DEVICE must be CPU or GPU"; pid_path=Path(pid_file); config=json.loads(pid_path.read_text()); detection=config["config"]["pipelines"][0]["payload"]["parameters"]["detection-properties"]; pid_changed=detection["device"] != pid_device; detection["device"]=pid_device; pid_path.write_text(json.dumps(config,indent=4)+"\n") if pid_changed else None; env_path=Path(env_file); lines=env_path.read_text().splitlines(); key="AIG_INFERENCE_DEVICE="; found=any(line.startswith(key) for line in lines); updated=[key+aig_device if line.startswith(key) else line for line in lines]; updated=updated if found else updated+[key+aig_device]; env_path.write_text("\n".join(updated)+"\n") if updated != lines else None; print(f"PID_DEVICE={pid_device} in {pid_path}; AIG_DEVICE={aig_device} in {env_path}")' "$(PID_DEVICE)" "$(AIG_DEVICE)" "$(PID_CONFIG)" "$(AIG_ENV_FILE)"

.PHONY: benchmark-stack-reset
benchmark-stack-reset:
	@if [ "$(SKIP_BENCHMARK_STACK_RESET)" = true ]; then \
		echo "Using the already prepared benchmark stack"; \
	else \
		case "$(BENCHMARK_WARMUP_SECONDS)" in ''|*[!0-9]*) echo "BENCHMARK_WARMUP_SECONDS must be a non-negative integer" >&2; exit 2;; esac; \
		$(MAKE) down && \
		$(MAKE) UP_SKIP_DOWN=true BENCHMARK_MODE=true up && \
		if [ "$(BENCHMARK_WARMUP_SECONDS)" -gt 0 ]; then \
			echo "Warming up the application stack for $(BENCHMARK_WARMUP_SECONDS) seconds"; \
			sleep "$(BENCHMARK_WARMUP_SECONDS)"; \
		fi; \
	fi

.PHONY: benchmark-pid
benchmark-pid: $(if $(filter true,$(SKIP_PERFORMANCE_TOOLS_BUILD)),,build-performance-tools) $(if $(filter true,$(SKIP_BENCHMARK_DEVICE_CONFIG)),,benchmark-configure-devices)
	$(MAKE) benchmark-stack-reset
	$(call run_with_metrics,pid,$(BENCHMARK_PID_CMD))

.PHONY: benchmark-aig
benchmark-aig: $(if $(filter true,$(SKIP_PERFORMANCE_TOOLS_BUILD)),,build-performance-tools) $(if $(filter true,$(SKIP_BENCHMARK_DEVICE_CONFIG)),,benchmark-configure-devices)
	$(MAKE) benchmark-stack-reset
	$(call run_with_metrics,aig,$(BENCHMARK_AIG_CMD))

.PHONY: benchmark-web-ui
benchmark-web-ui: $(if $(filter true,$(SKIP_PERFORMANCE_TOOLS_BUILD)),,build-performance-tools) $(if $(filter true,$(SKIP_BENCHMARK_DEVICE_CONFIG)),,benchmark-configure-devices)
	$(MAKE) benchmark-stack-reset
	$(call run_with_metrics,web_ui,$(BENCHMARK_WEB_UI_CMD))

.PHONY: benchmark-qdrant
benchmark-qdrant: $(if $(filter true,$(SKIP_PERFORMANCE_TOOLS_BUILD)),,build-performance-tools) $(if $(filter true,$(SKIP_BENCHMARK_DEVICE_CONFIG)),,benchmark-configure-devices)
	$(MAKE) benchmark-stack-reset
	$(call run_with_metrics,qdrant,$(BENCHMARK_QDRANT_CMD))

.PHONY: benchmark-metrics
benchmark-metrics: $(if $(filter true,$(SKIP_PERFORMANCE_TOOLS_BUILD)),,build-performance-tools) $(if $(filter true,$(SKIP_BENCHMARK_DEVICE_CONFIG)),,benchmark-configure-devices)
	$(MAKE) benchmark-stack-reset
	$(call run_with_metrics,host,sleep $(METRICS_DURATION))

.PHONY: benchmark-e2e
benchmark-e2e: $(if $(filter true,$(SKIP_PERFORMANCE_TOOLS_BUILD)),,build-performance-tools) $(if $(filter true,$(SKIP_BENCHMARK_DEVICE_CONFIG)),,benchmark-configure-devices)
	$(MAKE) benchmark-stack-reset
	$(call run_with_metrics,e2e,$(BENCHMARK_E2E_CMD))
	$(CONSOLIDATE_CMD)

# Sequential so synthetic AIG/Qdrant load does not distort the live E2E capture.
.PHONY: benchmark-all
benchmark-all: build-performance-tools benchmark-configure-devices
	$(MAKE) benchmark-stack-reset RUN_ID=$(RUN_ID)
	$(MAKE) SKIP_BENCHMARK_STACK_RESET=true SKIP_BENCHMARK_DEVICE_CONFIG=true SKIP_PERFORMANCE_TOOLS_BUILD=true benchmark-aig RUN_ID=$(RUN_ID)
	$(MAKE) SKIP_BENCHMARK_STACK_RESET=true SKIP_BENCHMARK_DEVICE_CONFIG=true SKIP_PERFORMANCE_TOOLS_BUILD=true benchmark-qdrant RUN_ID=$(RUN_ID)
	$(MAKE) SKIP_BENCHMARK_STACK_RESET=true SKIP_BENCHMARK_DEVICE_CONFIG=true SKIP_PERFORMANCE_TOOLS_BUILD=true benchmark-e2e RUN_ID=$(RUN_ID)
	@echo "All benchmark results saved in $(RUN_DIR)"

# Consolidates RUN_ID=<timestamp> if given, otherwise the newest results/<timestamp> folder.
.PHONY: consolidate-benchmarks
consolidate-benchmarks:
	@dir="$(if $(filter command line environment,$(origin RUN_ID)),$(RUN_DIR),$$(ls -1d $(abspath $(RESULTS_ROOT))/[0-9]*_[0-9]*/ 2>/dev/null | sort | tail -n1))"; \
	if [ -z "$$dir" ]; then echo "No results/<timestamp> folder found" >&2; exit 1; fi; \
	python3 performance-tools/benchmark-scripts/benchmark_signage_consolidate_e2e.py --results "$$dir"

.PHONY: build_copyleft_sources
build_copyleft_sources:
	@echo "Building Docker containers including copyleft licensed sources..."
	$(DOCKER_COMPOSE) build --build-arg COPYLEFT_SOURCES=true --pull;

.PHONY: check_models
check_models:
	@echo "Checking required model artifacts..."
	@for file in \
		configs/pid/models/object_detection/yolo11s/INT8/yolo11s.xml \
		configs/pid/models/object_detection/yolo11s/INT8/yolo11s.bin \
		aig/models/sdxl_turbo_ov/int8/graph.pbtxt \
		aig/models/all-MiniLM-L12-v2/config.json; do \
		if [ ! -s "$$file" ]; then \
			echo "Missing required model artifact: $$file"; \
			echo "Run 'make download_models' before 'make up'."; \
			exit 1; \
		fi; \
	done
	@echo "All required model artifacts are present."


.PHONY: validate_host_ip
validate_host_ip:
	@echo "Validating HOST_IP in .env..."
	@host_ip=$$(grep -E "^HOST_IP=" $(ENV_FILE) | cut -d'=' -f2); \
	if [ -z "$$host_ip" ]; then \
		echo "HOST_IP is not set in $(ENV_FILE)."; \
		exit 1; \
	fi; \
	if [ "$$host_ip" = "localhost" ]; then \
		echo "HOST_IP ($$host_ip) is valid."; \
		exit 0; \
	fi; \
	if ! echo "$$host_ip" | grep -Eq '^([0-9]{1,3}\.){3}[0-9]{1,3}$$'; then \
		echo "HOST_IP ($$host_ip) is not a valid IPv4 address format or localhost."; \
		exit 1; \
	fi; \
	for octet in $$(echo "$$host_ip" | tr '.' ' '); do \
		if [ "$$octet" -lt 0 ] || [ "$$octet" -gt 255 ]; then \
			echo "HOST_IP ($$host_ip) has an invalid octet: $$octet"; \
			exit 1; \
		fi; \
	done; \
	echo "HOST_IP ($$host_ip) is valid."

# Check if multiple particular variables in .env are assigned with values
.PHONY: check_env_variables
check_env_variables:
	@echo "Checking if username/password in .env are matching the rules set..."
	@variables="MTX_WEBRTCICESERVERS2_0_USERNAME MTX_WEBRTCICESERVERS2_0_PASSWORD"; \
	for variable_name in $$variables; do \
		value=$$(grep -E "^$$variable_name=" $(ENV_FILE) | cut -d'=' -f2); \
		if [ -z "$$value" ]; then \
			echo "'$$variable_name' in $(ENV_FILE) is unassigned."; \
			exit 1; \
		fi; \
		case "$$variable_name" in \
			MTX_WEBRTCICESERVERS2_0_USERNAME) \
				if ! echo "$$value" | grep -Eq "^[A-Za-z]{5,}$$"; then \
					echo "MTX_WEBRTCICESERVERS2_0_USERNAME must contain only alphabets and be at least 5 characters minimum"; \
					exit 1; \
				fi \
				;; \
			MTX_WEBRTCICESERVERS2_0_PASSWORD) \
				if ! echo "$$value" | grep -Eq "^[A-Za-z0-9]{8,}$$" || ! echo "$$value" | grep -q "[0-9]" || ! echo "$$value" | grep -q "[A-Za-z]"; then \
					echo "MTX_WEBRTCICESERVERS2_0_PASSWORD length must be a minimum of 8 alphanumeric characters with at least one digit"; \
					exit 1; \
				fi \
				;; \
		esac; \
	done

.PHONY: up
up: check_env_variables validate_host_ip check_models
	@if [ "$(UP_SKIP_DOWN)" != true ]; then $(MAKE) down; fi
	@echo "Starting Docker containers..."
	BENCHMARK_MODE=$(BENCHMARK_MODE) $(DOCKER_COMPOSE) up -d
	

# Status of the deployed containers
.PHONY: status
status:
	@echo "Status of the deployed containers..."; \
	docker ps -a --filter "name=^ia-" --filter "name=mr_" --filter "name=model_" --filter "name=wind-turbine" --format "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}"; \
	echo "Parsing the logs of all containers to catch any error messages..."; \
	sleep 20; \
	containers=$$(docker ps -a --filter "name=^ia-" --filter "name=mr_" --filter "name=model_" --filter "name=wind-turbine" --format "{{.Names}}"); \
	failure_cont_flag=0; \
	for container in $$containers; do \
		errors=$$(docker logs --tail 5 $$container 2>&1 | grep -i "error"); \
		error_count=0; \
		if [ -n "$$errors" ]; then \
			error_count=$$(echo "$$errors" | wc -l); \
		fi; \
		if [ $$error_count -gt 0 ]; then \
			echo ""; \
			echo "=============Found errors in container $$container========"; \
			echo "$$errors"; \
			echo "******************************************************"; \
			echo ""; \
			failure_cont_flag=1; \
		fi; \
	done; \
	if [ $$failure_cont_flag -eq 0 ]; then \
		echo ""; \
		echo "All containers are up and running without errors."; \
		echo ""; \
	else \
		echo ""; \
		echo "Some containers have errors. Please check the logs above."; \
		echo ""; \
	fi;
	
# Removes docker compose containers and volumes
.PHONY: down
down:
	@echo "Stopping Docker containers...";
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) down -v --remove-orphans

# Push the docker images to docker registry, ensure to configure DOCKER_REGISTRY in .env
# and have logged into that. Applies mainly when one is dealing with internal docker registry.
# If you are using docker hub, ensure to have logged in with `docker login` command
# before running this command.
.PHONY: push_images
push_images: build
	@echo "Pushing the images to docker registry"
	docker compose -f $(DOCKER_COMPOSE_FILE) push

# Help
.PHONY: help
help:
	@echo "Makefile commands:"
	@echo "  make build    - Build Docker containers"
	@echo "  make download_models - Download required PID and AIG models"
	@echo "  make update-submodules - Clone/update git submodules"
	@echo "  make benchmark-pid - Benchmark PID inference (PID_DEVICE=CPU|GPU|NPU, BENCHMARK_WARMUP_SECONDS=300)"
	@echo "  Benchmark targets reset the stack and wait 300 seconds; set BENCHMARK_WARMUP_SECONDS to override"
	@echo "  make benchmark-aig - Benchmark ASe search and AIG generation (AIG_DEVICE=GPU, BENCHMARK_ITERATIONS=10)"
	@echo "  make benchmark-web-ui - Collect Web UI selection metrics for 300 seconds"
	@echo "  make benchmark-qdrant - Benchmark vector search, memory and ad indexing"
	@echo "  make benchmark-metrics - Collect host metrics only (METRICS_DURATION=300)"
	@echo "  make benchmark-e2e - Capture live PID -> Web UI -> ASe/AIG -> browser timings and consolidate"
	@echo "  make benchmark-all - Run AIG, Qdrant, then E2E benchmarks and consolidate"
	@echo "  make consolidate-benchmarks - Merge the latest benchmark results into an E2E stage table"
	@echo "  Benchmark targets collect CPU/GPU/NPU/memory/power metrics during the run; set COLLECT_METRICS=false to skip"
	@echo "  make build_copyleft_sources - Build Docker containers including copyleft licensed sources"
	@echo "  make up    - Start Docker containers"
	@echo "  make down     - Stop Docker containers"
	@echo "  make restart  - Restart Docker containers"
	@echo "  make clean    - Remove all stopped containers and unused images"
	@echo "  make push_images     - Push the images to docker registry"
	@echo "  make help     - Display this help message"
