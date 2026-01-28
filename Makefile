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
	$(DOCKER_COMPOSE) build;

.PHONY: build_copyleft_sources
build_copyleft_sources:
	@echo "Building Docker containers including copyleft licensed sources..."
	$(DOCKER_COMPOSE) build --build-arg COPYLEFT_SOURCES=true;

.PHONY: check_models
check_models:
	@echo "Checking if object detection and text to image models are available..."
	@for dir in pid/models aig/models; do \
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


.PHONY: validate_host_ip
validate_host_ip:
	@echo "Validating HOST_IP in .env..."
	@host_ip=$$(grep -E "^HOST_IP=" $(ENV_FILE) | cut -d'=' -f2); \
	if [ -z "$$host_ip" ]; then \
		echo "HOST_IP is not set in $(ENV_FILE)."; \
		exit 1; \
	fi; \
	if ! echo "$$host_ip" | grep -Eq '^([0-9]{1,3}\.){3}[0-9]{1,3}$$'; then \
		echo "HOST_IP ($$host_ip) is not a valid IPv4 address format."; \
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
	@echo "  make build_copyleft_sources - Build Docker containers including copyleft licensed sources"
	@echo "  make up    - Start Docker containers"
	@echo "  make down     - Stop Docker containers"
	@echo "  make restart  - Restart Docker containers"
	@echo "  make clean    - Remove all stopped containers and unused images"
	@echo "  make push_images     - Push the images to docker registry"
	@echo "  make help     - Display this help message"
