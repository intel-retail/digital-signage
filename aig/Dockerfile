#
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

# Specify all Docker arguments for the Dockerfile
FROM ubuntu:24.04 AS aig-server
LABEL description="Advertise Image Generator Server" 
LABEL vendor="Intel Corporation"

ARG DEBIAN_FRONTEND=noninteractive

SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

RUN \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y -q --no-install-recommends intel-gpu-tools  gnupg wget python3-pip unzip fontconfig  \
    python3-venv libraqm-dev software-properties-common && \
    wget https://github.com/intel/intel-one-mono/releases/download/V1.4.0/ttf.zip && \
    unzip ttf.zip -d /usr/share/fonts && \
    fc-cache -f -v && \
    rm ttf.zip && \
    apt-get remove -y unzip fontconfig && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Intel GPU tools and clean up
RUN apt-get update && apt-get install -y --no-install-recommends curl libnuma1 ocl-icd-libopencl1 ca-certificates && rm -rf /var/lib/apt/lists/* && update-ca-certificates && \
    mkdir /tmp/gpu_deps && cd /tmp/gpu_deps && \
    # intel graphics compiler
    curl --fail -L -O https://github.com/intel/intel-graphics-compiler/releases/download/v2.41.5/intel-igc-core-2_2.41.5+22716_amd64.deb && \
    curl --fail -L -O https://github.com/intel/intel-graphics-compiler/releases/download/v2.41.5/intel-igc-opencl-2_2.41.5+22716_amd64.deb && \
    #intel compute runtime
    curl --fail -L -O   https://github.com/intel/compute-runtime/releases/download/26.35.39758.10/intel-ocloc_26.35.39758.10-0_amd64.deb && \
    curl --fail -L -O   https://github.com/intel/compute-runtime/releases/download/26.35.39758.10/intel-opencl-icd_26.35.39758.10-0_amd64.deb && \
    curl --fail -L -O   https://github.com/intel/compute-runtime/releases/download/26.35.39758.10/libigdgmm12_22.10.0_amd64.deb && \
    curl --fail -L -O   https://github.com/intel/compute-runtime/releases/download/26.35.39758.10/libze-intel-gpu1_26.35.39758.10-0_amd64.deb && \
    # install all the debs and clean up
	dpkg -i *.deb && rm -Rf /tmp/gpu_deps

# Intel NPU user-mode driver (Level Zero loader + NPU driver/compiler/firmware)
RUN apt-get update && apt-get install -y --no-install-recommends libtbb12 && rm -rf /var/lib/apt/lists/* && \
    mkdir /tmp/npu_deps && cd /tmp/npu_deps && \
    curl --fail -L -O https://github.com/intel/linux-npu-driver/releases/download/v1.38.0/linux-npu-driver-v1.38.0.20260910-34487311128-ubuntu2404.tar.gz && \
    tar -xf linux-npu-driver-*.tar.gz && \
    curl --fail -L -O https://snapshot.ppa.launchpadcontent.net/kobuk-team/intel-graphics/ubuntu/20260830T100000Z/pool/main/l/level-zero-loader/libze1_1.32.0-1~24.04~ppa1_amd64.deb && \
    dpkg -i *.deb && rm -Rf /tmp/npu_deps

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
RUN python -m pip uninstall -y pip

# Copy source code
COPY ./run.sh .
COPY ./src/ ./src

RUN chmod +x ./run.sh

USER ${USER}
ENTRYPOINT ["./run.sh"]