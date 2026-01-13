#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

FROM python:3.13-slim

# Install system dependencies for OpenCV and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libgthread-2.0-0 \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY ./requirements.txt /app/
RUN pip install --upgrade pip
RUN pip3 install --no-cache-dir -r requirements.txt

RUN apt-get remove --purge -y --allow-remove-essential perl-base

COPY main.py .
COPY templates/ ./templates/

HEALTHCHECK --interval=5m CMD exit 0

ENTRYPOINT ["python3", "main.py"]
