#
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

# Specify all Docker arguments for the Dockerfile
ARG BASE_IMAGE=ubuntu:22.04
FROM ${BASE_IMAGE} AS aig-server
LABEL description="Advertise Image Generator Server" 
LABEL vendor="Intel Corporation"

ARG AIG_VERSION=0.0.1

SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

RUN \
    apt-get update && \
    apt-get install -y -q --no-install-recommends gnupg=\* ca-certificates=\* gpg-agent=\* wget=\* libtbb-dev=\* cmake=\* git=\* git-lfs=\* vim=\* numactl=\* && \
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

# Intel GPU: https://www.intel.com/content/www/us/en/docs/oneapi/installation-guide-linux/2023-0/configure-wsl-2-for-gpu-workflows.html
# hadolint ignore=SC1091
RUN export no_proxy= && \
    apt-get update && \
    . /etc/os-release && \
    if [[ ! "jammy" =~ ${VERSION_CODENAME} ]]; then \
        echo "Ubuntu version ${VERSION_CODENAME} not supported"; \
    else \
        wget --no-check-certificate -qO - https://repositories.intel.com/graphics/intel-graphics.key | gpg --dearmor --output /usr/share/keyrings/intel-graphics.gpg && \
        echo 'deb [arch=amd64,i386 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/graphics/ubuntu jammy arc' | \
        tee /etc/apt/sources.list.d/intel.gpu.jammy.list && \
        apt-get update; \
        #wget --no-check-certificate -qO- https://repositories.intel.com/gpu/intel-graphics.key | gpg --dearmor --output /usr/share/keyrings/gpu-intel-graphics.gpg && \
        #echo "deb [arch=amd64 signed-by=/usr/share/keyrings/gpu-intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu jammy client" | \
        #tee /etc/apt/sources.list.d/intel-gpu-"${VERSION_CODENAME}".list && \
        #apt-get update; \
    fi && \
    apt-get install -y --no-install-recommends \
    intel-opencl-icd=\* intel-level-zero-gpu=\* level-zero=\* \
    intel-media-va-driver-non-free=\* libmfx1=\* libmfxgen1=\* libvpl2=\*  \
    libegl-mesa0 libegl1-mesa libegl1-mesa-dev libgbm1 libgl1-mesa-dev libgl1-mesa-dri \
    libglapi-mesa libgles2-mesa-dev libglx-mesa0 libigdgmm12 libxatracker2 vainfo mesa-va-drivers \
    mesa-vdpau-drivers mesa-vulkan-drivers va-driver-all \
    libigc-dev intel-igc-cm libigdfcl-dev libigfxcmrt-dev level-zero-dev \
    hwinfo=\* clinfo=\* && \
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

ARG DEBIAN_FRONTEND=noninteractive

#Align with the docker-compose file
RUN if ! getent group 4; then groupadd -g 4 adm; fi && \
    if ! getent group 44; then groupadd -g 44 video; fi && \
    if ! getent group 29; then groupadd -g 29 audio; fi && \
    if ! getent group 100; then groupadd -g 100 users; fi && \
    if ! getent group 992; then groupadd -g 992 render; fi && \
    if ! getent group 46; then groupadd -g 46 plugdev; fi

RUN export no_proxy= && \
    apt-get update -y && \
    apt-get clean -y && \
    rm -rf /var/lib/apt/lists/* && \
    useradd -ms /bin/bash aiguser && \
    chown -R aiguser: /opt && \
    chmod -R u+rw /opt

RUN \
    mkdir /python3venv && \
    chown -R aiguser: /python3venv && \
    chmod -R u+w /python3venv

    #LIBVA_DRIVER_NAME=iHD (or d3d12 in WSL2)
ENV LIBVA_DRIVER_NAME=d3d12
ENV LIBVA_DRIVERS_PATH=/usr/lib/x86_64-linux-gnu/dri:/usr/lib/wsl/lib
ENV GST_VA_ALL_DRIVERS=1
ENV PATH=/python3venv/bin:$PATH
ENV TERM=xterm

RUN usermod -a -G video aiguser 

# Install Python, pip and venv
RUN export no_proxy= && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    python3=\* python3-venv=\*  python3-pip=\*  && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*


WORKDIR /home/aiguser
USER aiguser

RUN \
    python3 -m venv /python3venv && \
    /python3venv/bin/pip3 install --no-cache-dir --upgrade pip && \
    /python3venv/bin/pip3 install --no-cache-dir --no-dependencies setuptools==75.8.0


######################## Update required packages ################################
USER root

WORKDIR /home/aiguser

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

ENV LD_LIBRARY_PATH=/root/.local/bin:/usr/lib/wsl/lib \
    PYTHONPATH=$PYTHONPATH:/usr/local/lib/:/root/.local/bin \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/root/.local/bin \
    PKG_CONFIG_PATH=/usr/share/pkgconfig:/usr/lib/x86_64-linux-gnu/pkgconfig:/usr/lib/pkgconfig:

RUN export no_proxy= && \
    apt-get update && \
    apt-get install -y -q --no-install-recommends libdrm-dev=\* && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ARG USER
ARG UID

RUN useradd -ms /bin/bash -G adm,video,audio,users,render,plugdev ${USER} -o -u $UID && \
    chown ${USER}:${USER} -R /root

RUN mkdir -p /home/${USER}/ && chown -R ${USER}:${USER} /home/${USER}

ENV cl_cache_dir=/home/.cl_cache \
    XDG_RUNTIME_DIR=/home/.xdg_runtime_dir \
    LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/usr/local/lib:/usr/local/lib/udfs \
    PYTHONPATH=$PYTHONPATH:/opt/intel/eii/lib:/usr/local/lib/

RUN mkdir -p $cl_cache_dir && chmod -R g+s $cl_cache_dir && chown ${USER}:users $cl_cache_dir
ENV XDG_RUNTIME_DIR=/home/.xdg_runtime_dir
RUN mkdir -p $XDG_RUNTIME_DIR && chmod -R g+s $XDG_RUNTIME_DIR && chown ${USER}:users $XDG_RUNTIME_DIR

ENV LD_LIBRARY_PATH ${LD_LIBRARY_PATH}:/usr/local/lib:/home/pipeline-server:${CMAKE_INSTALL_PREFIX}/lib:${CMAKE_INSTALL_PREFIX}/lib/udfs

### To install other/newer///
RUN apt-get update && apt-get install -y --no-install-recommends git

WORKDIR /home/aigserver
USER $USER

# Copy source code
COPY ./docker/run.sh .
COPY ./src/ ./src

# Install server requirements
USER root
RUN pip3 install --no-cache-dir -r  /home/aigserver/src/requirements.txt 

USER ${USER}
ENTRYPOINT ["./run.sh"]