#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

INCLUDE ?= default_INCLUDE

DOCKER_COMPOSE_FILE = ./docker-compose.yml
DOCKER_COMPOSE = docker compose
SECURE_MODE='false'

DRI_MOUNT_PATH := $(shell [ -d /dev/dri ] && [ -n "$$(ls -A /dev/dri 2>/dev/null)" ] && echo "/dev/dri" || echo "/dev/null")
export DRI_MOUNT_PATH

ACCEL_MOUNT_PATH := $(shell [ -d /dev/accel ] && [ -n "$$(ls -A /dev/accel 2>/dev/null)" ] && echo "/dev/accel" || echo "/dev/null")
export ACCEL_MOUNT_PATH

# Define the path to the .env file and scripts
ENV_FILE = ./.env
HELM_PACKAGE_SCRIPT = ./package_helm.sh
SCRIPTS_DIR = ./scripts
DOWNLOAD_MODELS_SCRIPT = $(SCRIPTS_DIR)/download-models.sh
CHECK_STACK_SCRIPT = $(SCRIPTS_DIR)/check-stack.sh

# Pass FORCE=1 to re-download models that are already present
FORCE ?=
MODEL_FORCE_FLAG = $(if $(filter 1 true yes,$(FORCE)),--force,)

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

.PHONY: build_copyleft_sources
build_copyleft_sources:
	@echo "Building Docker containers including copyleft licensed sources..."
	$(DOCKER_COMPOSE) build --build-arg COPYLEFT_SOURCES=true --pull;

.PHONY: check_models
check_models:
	@echo "Checking if object detection and text to image models are available..."
	@for dir in configs/pid/models aig/models; do \
		if [ ! -d "$$dir" ]; then \
			echo "Error: $$dir directory does not exist."; \
			exit 1; \
		fi; \
		if [ -z "$$(ls -A $$dir 2>/dev/null)" ]; then \
			echo "Error: $$dir directory is empty."; \
			exit 1; \
		fi; \
		echo "Models found in $$dir directory."; \
	done


# Download and prepare every model the stack needs: YOLO11s (detection) into
# configs/pid/models/, SDXL-Turbo and MiniLM into aig/models/. Idempotent - already
# populated targets are skipped unless FORCE=1 is passed. Expect tens of minutes on a
# first run, mostly the SDXL-Turbo export.
.PHONY: download_models
download_models:
	@$(DOWNLOAD_MODELS_SCRIPT) $(MODEL_FORCE_FLAG)

# Only the YOLO11s detection model (configs/pid/models/)
.PHONY: download_models_pid
download_models_pid:
	@$(DOWNLOAD_MODELS_SCRIPT) --pid-only $(MODEL_FORCE_FLAG)

# Only the SDXL-Turbo and MiniLM models (aig/models/)
.PHONY: download_models_aig
download_models_aig:
	@$(DOWNLOAD_MODELS_SCRIPT) --aig-only $(MODEL_FORCE_FLAG)

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
up: check_models check_env_variables validate_host_ip down
	@echo "Starting Docker containers..."; \
	$(DOCKER_COMPOSE) up -d;
	

# Health of the deployed stack: container state and restart counts, recent log errors,
# and live probes of the web UI and AIG API endpoints. Exits non-zero on failures.
.PHONY: check_stack
check_stack:
	@$(CHECK_STACK_SCRIPT)

# Status of the deployed containers
.PHONY: status
status: check_stack


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
	@echo "  make download_models        - Download and prepare all models (YOLO11s, SDXL-Turbo, MiniLM)"
	@echo "  make download_models_pid    - Download only the YOLO11s detection model"
	@echo "  make download_models_aig    - Download only the SDXL-Turbo and MiniLM models"
	@echo "                                add FORCE=1 to re-download models already present"
	@echo "  make build                  - Build Docker containers"
	@echo "  make build_copyleft_sources - Build Docker containers including copyleft licensed sources"
	@echo "  make up                     - Validate env and models, then start Docker containers"
	@echo "  make down                   - Stop Docker containers and remove volumes"
	@echo "  make status                 - Check stack health: containers, logs and endpoints"
	@echo "  make check_stack            - Same as 'make status'"
	@echo "  make check_models           - Verify the model directories are populated"
	@echo "  make check_env_variables    - Verify the WebRTC credentials in .env"
	@echo "  make validate_host_ip       - Verify HOST_IP in .env"
	@echo "  make push_images            - Push the images to docker registry"
	@echo "  make help                   - Display this help message"
