#
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

# Specify all Docker arguments for the Dockerfile
FROM ubuntu:22.04 AS aig-server
LABEL description="Advertise Image Generator Server" 
LABEL vendor="Intel Corporation"


SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

RUN \
    apt-get update && \
    apt-get install -y -q --no-install-recommends intel-gpu-tools gnupg wget python3-pip \
    python3-venv libraqm-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Intel GPU tools and clean up
RUN export no_proxy= && \
    apt-get update && \
    . /etc/os-release && \
    if [[ ! "jammy" =~ ${VERSION_CODENAME} ]]; then \
        echo "Ubuntu version ${VERSION_CODENAME} not supported"; \
    else \
        wget --no-check-certificate -qO- https://repositories.intel.com/gpu/intel-graphics.key | gpg --dearmor --output /usr/share/keyrings/gpu-intel-graphics.gpg && \
        echo "deb [arch=amd64 signed-by=/usr/share/keyrings/gpu-intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu jammy client" | \
        tee /etc/apt/sources.list.d/intel-gpu-"${VERSION_CODENAME}".list && \
        apt-get update; \
    fi && \
    apt-get install -y --no-install-recommends \
    intel-opencl-icd intel-level-zero-gpu && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* 

ARG DEBIAN_FRONTEND=noninteractive

RUN useradd -ms /bin/bash aiguser && \
    chown -R aiguser: /opt && \
    chmod -R u+rw /opt

RUN \
    mkdir /python3venv && \
    chown -R aiguser: /python3venv && \
    chmod -R u+w /python3venv

RUN usermod -a -G video aiguser 

WORKDIR /home/aiguser
USER aiguser

RUN \
    python3 -m venv /python3venv && \
    /python3venv/bin/pip3 install --no-cache-dir --upgrade pip && \
    /python3venv/bin/pip3 install --no-cache-dir setuptools wheel

USER root

WORKDIR /home/aiguser

ENV LD_LIBRARY_PATH=/root/.local/bin:/usr/lib/wsl/lib \
    PYTHONPATH=$PYTHONPATH:/usr/local/lib/:/root/.local/bin:/python3venv/lib/python3.12/site-packages \
    PATH=/python3venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/root/.local/bin 

ARG USER
ARG UID

RUN echo "USER: ${USER}, UID: ${UID}"

RUN useradd -ms /bin/bash -G adm,video,audio,users,plugdev ${USER} -o -u $UID && \
    chown ${USER}:${USER} -R /root

RUN mkdir -p /home/${USER}/ && chown -R ${USER}:${USER} /home/${USER}

WORKDIR /home/aigserver
USER $USER

COPY src/requirements.txt /home/aigserver/src/requirements.txt

# Install server requirements
USER root

RUN /python3venv/bin/pip3 install --no-cache-dir -r /home/aigserver/src/requirements.txt

# Copy source code
COPY ./run.sh .
COPY ./src/ ./src

USER ${USER}
ENTRYPOINT ["./run.sh"]