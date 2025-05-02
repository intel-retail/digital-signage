#!/bin/bash
# Purpose: Utility functions for scripting and common variables (e.g., packages to manage)
# Script: Mario Divan
# ------------------------------------------

RED='\033[0;31m'    # Red
BLUE='\033[0;34m'   # Blue
CYAN='\033[0;36m'   # Cyan
GREEN='\033[0;32m'  # Green
YELLOW='\033[0;33m' # Yellow
NOCOLOR='\033[0m'
BWHITE='\033[1;37m' # White

mess_err() {
        printf "${RED}\u274c ${BWHITE} $1\n"
}

mess_oki() {
        printf "${GREEN}\u2705 ${NOCOLOR} $1\n"
}

mess_war() {
        printf "${YELLOW}\u26A0 ${BWHITE} $1\n"
}

mess_inf() {
        printf "${CYAN}\u24d8 ${NOCOLOR} $1\n"
}

isInstalled() {
        mess_inf "Verifying $1 package"
        return dpkg-query -Wf'${Status}' $1 2>/dev/null | grep 'ok installed' | wc -l
}

declare -a essential_packages=("git" "git-lfs" "gcc" "python3-venv" "python3-dev" "ffmpeg")

#GPU Drivers
GPU_FILES_DRIVER_VERSION="25.13.33276.16"
declare -a gpu_dependencies=("ocl-icd-libopencl1")
declare -a gpu_files_driver=("https://github.com/intel/intel-graphics-compiler/releases/download/v2.10.8/intel-igc-core-2_2.10.8+18926_amd64.deb" "https://github.com/intel/intel-graphics-compiler/releases/download/v2.10.8/intel-igc-opencl-2_2.10.8+18926_amd64.deb" "https://github.com/intel/compute-runtime/releases/download/25.13.33276.16/libigdgmm12_22.7.0_amd64.deb" "https://github.com/intel/compute-runtime/releases/download/25.13.33276.16/intel-level-zero-gpu_1.6.33276.16_amd64.deb" "https://github.com/intel/compute-runtime/releases/download/25.13.33276.16/intel-level-zero-gpu-dbgsym_1.6.33276.16_amd64.ddeb" "https://github.com/intel/compute-runtime/releases/download/25.13.33276.16/intel-opencl-icd_25.13.33276.16_amd64.deb" "https://github.com/intel/compute-runtime/releases/download/25.13.33276.16/intel-opencl-icd-dbgsym_25.13.33276.16_amd64.ddeb")

#NPU Drivers
NPU_FILES_DRIVER_VERSION="v1.16.0"
declare -a npu_dependencies=("libtbb12")
declare -a npu_files_driver_ubuntu22=("https://github.com/oneapi-src/level-zero/releases/download/v1.20.2/level-zero_1.20.2+u22.04_amd64.deb" "https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-driver-compiler-npu_1.16.0.20250328-14132024782_ubuntu22.04_amd64.deb" "https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-fw-npu_1.16.0.20250328-14132024782_ubuntu22.04_amd64.deb" https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-level-zero-npu_1.16.0.20250328-14132024782_ubuntu22.04_amd64.deb)
declare -a npu_files_driver_ubuntu24=("https://github.com/oneapi-src/level-zero/releases/download/v1.20.2/level-zero_1.20.2+u24.04_amd64.deb" "https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-driver-compiler-npu_1.16.0.20250328-14132024782_ubuntu24.04_amd64.deb" "https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-fw-npu_1.16.0.20250328-14132024782_ubuntu24.04_amd64.deb" "https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-level-zero-npu_1.16.0.20250328-14132024782_ubuntu24.04_amd64.deb")

#declare -a ovscripts=("utilities.sh" "installEnv.sh" "runEnv.sh" "runDemo.sh" "cleanEnv.sh")
