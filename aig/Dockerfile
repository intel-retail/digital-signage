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
RUN apt-get update && apt-get install -y curl libnuma1 ocl-icd-libopencl1 --no-install-recommends && rm -rf /var/lib/apt/lists/* && \
    mkdir /tmp/gpu_deps && cd /tmp/gpu_deps && \
    curl --fail -L -O  https://github.com/intel/intel-graphics-compiler/releases/download/v2.32.7/intel-igc-core-2_2.32.7+21184_amd64.deb && \
    curl --fail -L -O  https://github.com/intel/intel-graphics-compiler/releases/download/v2.32.7/intel-igc-opencl-2_2.32.7+21184_amd64.deb && \
    curl --fail -L -O  https://github.com/intel/compute-runtime/releases/download/26.14.37833.4/intel-ocloc_26.14.37833.4-0_amd64.deb && \
    curl --fail -L -O  https://github.com/intel/compute-runtime/releases/download/26.14.37833.4/intel-opencl-icd_26.14.37833.4-0_amd64.deb && \
    curl --fail -L -O  https://github.com/intel/compute-runtime/releases/download/26.14.37833.4/libigdgmm12_22.9.0_amd64.deb && \
    curl --fail -L -O  https://github.com/intel/compute-runtime/releases/download/26.14.37833.4/libze-intel-gpu1_26.14.37833.4-0_amd64.deb && \
	dpkg -i *.deb && rm -Rf /tmp/gpu_deps

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
RUN rm -rf /python3venv/lib/python3.10/site-packages/setuptools/_vendor/jaraco.context-5.3.0.dist-info

# Copy source code
COPY ./run.sh .
COPY ./src/ ./src

USER ${USER}
ENTRYPOINT ["./run.sh"]