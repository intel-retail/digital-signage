#
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

# Specify all Docker arguments for the Dockerfile
ARG BASE_IMAGE=ubuntu:22.04
FROM ${BASE_IMAGE} AS pca-server
LABEL description="Product Consumption Analyzer Server" 
LABEL vendor="Intel Corporation"

ARG PCA_VERSION=0.0.1

SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

RUN \
    apt-get update && \
    apt-get install -y -q --no-install-recommends gnupg=\* ca-certificates=\* wget=\* libtbb-dev=\* cmake=\* git=\* git-lfs=\* vim=\* numactl=\* && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Intel® NPU drivers (optional)
RUN export no_proxy= && \
    mkdir debs && \
    dpkg --purge --force-remove-reinstreq intel-driver-compiler-npu intel-fw-npu intel-level-zero-npu level-zero && \
    wget -q https://github.com/oneapi-src/level-zero/releases/download/v1.17.44/level-zero_1.17.44+u22.04_amd64.deb -P ./debs && \
    wget -q --no-check-certificate -nH --accept-regex="ubuntu22" --cut-dirs=5 -r https://github.com/intel/linux-npu-driver/releases/expanded_assets/v1.13.0 -P ./debs && \
    apt-get install -y -q --no-install-recommends ./debs/*.deb && \
    rm -r -f debs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -f /etc/ssl/certs/Intel*

# Intel® Data Center GPU Flex Series drivers (optional)
# hadolint ignore=SC1091
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
    intel-opencl-icd=\* ocl-icd-opencl-dev=\* intel-level-zero-gpu=\* level-zero=\* \
    libmfx1=\* libmfxgen1=\* libvpl2=\* intel-media-va-driver-non-free=\* \
    libgbm1=\* libigdgmm12=\* libxatracker2=\* libdrm-amdgpu1=\* \
    va-driver-all=\* vainfo=\* hwinfo=\* clinfo=\* && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN export no_proxy= && \
    echo "deb https://apt.repos.intel.com/openvino/2025 ubuntu22 main" | tee /etc/apt/sources.list.d/intel-openvino-2025.list && \
    wget -q https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB && \
    apt-key add GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB && \
    wget -q -O- https://eci.intel.com/sed-repos/gpg-keys/GPG-PUB-KEY-INTEL-SED.gpg | tee /usr/share/keyrings/sed-archive-keyring.gpg > /dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/sed-archive-keyring.gpg] https://eci.intel.com/sed-repos/jammy sed main" | tee /etc/apt/sources.list.d/sed.list && \
    echo "deb-src [signed-by=/usr/share/keyrings/sed-archive-keyring.gpg] https://eci.intel.com/sed-repos/jammy sed main" | tee -a /etc/apt/sources.list.d/sed.list && \
    bash -c 'echo -e "Package: *\nPin: origin eci.intel.com\nPin-Priority: 1000" > /etc/apt/preferences.d/sed'

# Install Python, pip and venv
RUN export no_proxy= && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    python3=\* python3-venv=\*  python3-pip=\*  && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ARG DEBIAN_FRONTEND=noninteractive

RUN export no_proxy= && \
    apt-get update -y && \
    apt-get clean -y && \
    rm -rf /var/lib/apt/lists/* && \
    useradd -ms /bin/bash pcauser && \
    chown -R pcauser: /opt && \
    chmod -R u+rw /opt

RUN \
    mkdir /python3venv && \
    chown -R pcauser: /python3venv && \
    chmod -R u+w /python3venv

ENV LIBVA_DRIVER_NAME=iHD
ENV LIBVA_DRIVERS_PATH=/usr/lib/x86_64-linux-gnu/dri
ENV PATH=/python3venv/bin:$PATH
ENV TERM=xterm


WORKDIR /home/pcauser
USER pcauser

RUN \
    python3 -m venv /python3venv && \
    /python3venv/bin/pip3 install --no-cache-dir --upgrade pip


######################## Update required packages ################################
USER root

WORKDIR /home/pcauser

RUN export no_proxy= && \
    apt-get update --allow-releaseinfo-change && apt-get install -y --no-install-recommends git autoconf  \
    automake \
    libglib2.0-dev \
    libusb-1.0-0-dev \
    libtool \
    zlib1g-dev \
    make \
    zip \
    unzip \
    libopencv-dev \
    libcjson-dev && \
    rm -rf /var/lib/apt/lists/*

ARG USER
ARG UID

RUN useradd -ms /bin/bash -G video,audio,users,plugdev ${USER} -o -u $UID && \
    chown ${USER}:${USER} -R /root

RUN mkdir -p /home/${USER}/ && chown -R ${USER}:${USER} /home/${USER}

WORKDIR /home/pca-server
USER $USER

# Copy source code
COPY ./docker/run.sh .

COPY ./src/ ./src

# Install server requirements
USER pcauser
RUN pip3 install --no-cache-dir -r  /home/pca-server/src/requirements.txt 

USER ${USER}
ENTRYPOINT ["./run.sh"]