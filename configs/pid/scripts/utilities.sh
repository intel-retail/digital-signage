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

mess_er2() {
        printf "${BWHITE} $1 ${RED} $2\n"
}

mess_oki() {
        printf "${GREEN}\u2705 ${NOCOLOR} $1\n"
}

mess_ok2() {
        printf "${BWHITE} $1 ${GREEN} $2\n"
}

mess_war() {
        printf "${YELLOW}\u26A0 ${BWHITE} $1\n"
}

mess_wa2() {
        printf "${BWHITE} $1 ${YELLOW} $2\n"
}

mess_inf() {
        printf "${CYAN}\u24d8 ${NOCOLOR} $1\n"
}

mess_in2() {
        printf "${BWHITE} $1 ${CYAN} $2\n"
}

mess_op1() {
        printf "${BWHITE} $1\n"
}

mess_op2() {
        printf "${BWHITE} $1 ${GREEN} $2\n"
}

isInstalled() {
        mess_inf "Verifying $1 package"
        found=$(dpkg-query -Wf'${Status}' $1 2>/dev/null | grep 'ok installed' | wc -l)
        if [ $found -ge 1 ]; then
                return 0
        fi
        return 1 
}

is_array() {
  declare -p "$1" 2>/dev/null | grep -q "declare -a"
}

existUser() {
        if [ -z "$1" ]; then
                mess_err "No user provided"
                return 1
        fi

        if id -u "$1" &>/dev/null; then
                return 0
        else
                return 1
        fi
}

#It returns the names of the libraries as an array from the URL indicated as an array
getDriverNames() {
        array_return=() #Initialize the array to store the names
        if is_array "$1"; then 
                local -n array_name="$1" #creates a reference to the array passed as the first argument
        else
                mess_err "The variable $1 is not an array."
                array_return
        fi

        for idx in "${array_name[@]}"; do
                 reversed_string=$(rev <<< "$idx")
                index_from_end=$(expr index "$reversed_string" "/")

                if [[ -n "$index_from_end" ]]; then

                        index_from_start=$(( ${#string} - index_from_end + 1 ))
                        first=${idx:index_from_start}
                        #mess_inf "Indentified: ${first}"

                        if [[ "$first" =~ (.*)(-|_)([0-9]+) ]]; then
                                extracted_string="${BASH_REMATCH[1]}" # This captures the number after the - or _

                                array_return+=("$extracted_string") #Append the element in the array
                        fi        
                fi    
        done
 
        echo "${array_return[@]}"
}

checkDockerNetwork() {
        mess_inf "Checking Docker network"
        network_name="app_network"

        if docker network inspect "$network_name" > /dev/null 2>&1; then                
                mess_ok2 "Docker network $network_name: " "OK"
                return 0
        else
                if docker network create "$network_name" > /dev/null 2>&1; then
                        mess_ok2 "Docker network $network_name: " "Created"
                        return 0
                else
                        mess_e2r "Docker network $network_name: " "Failed to create"
                        return 1
                fi
        fi
}

declare -a essential_packages=("git" "git-lfs" "gcc" "python3-venv" "python3-dev" "ffmpeg")

# GPU Drivers
GPU_FILES_DRIVER_VERSION="25.13.33276.16"
declare -a gpu_dependencies=("clinfo" "ocl-icd-libopencl1")
declare -a gpu_files_driver=("https://github.com/intel/intel-graphics-compiler/releases/download/v2.10.8/intel-igc-core-2_2.10.8+18926_amd64.deb" "https://github.com/intel/intel-graphics-compiler/releases/download/v2.10.8/intel-igc-opencl-2_2.10.8+18926_amd64.deb" "https://github.com/intel/compute-runtime/releases/download/25.13.33276.16/libigdgmm12_22.7.0_amd64.deb" "https://github.com/intel/compute-runtime/releases/download/25.13.33276.16/intel-level-zero-gpu_1.6.33276.16_amd64.deb" "https://github.com/intel/compute-runtime/releases/download/25.13.33276.16/intel-level-zero-gpu-dbgsym_1.6.33276.16_amd64.ddeb" "https://github.com/intel/compute-runtime/releases/download/25.13.33276.16/intel-opencl-icd_25.13.33276.16_amd64.deb" "https://github.com/intel/compute-runtime/releases/download/25.13.33276.16/intel-opencl-icd-dbgsym_25.13.33276.16_amd64.ddeb")

# NPU Drivers
NPU_FILES_DRIVER_VERSION="v1.16.0"
declare -a npu_dependencies=("libtbb12")
declare -a npu_files_driver_ubuntu22=("https://github.com/oneapi-src/level-zero/releases/download/v1.20.2/level-zero_1.20.2+u22.04_amd64.deb" "https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-driver-compiler-npu_1.16.0.20250328-14132024782_ubuntu22.04_amd64.deb" "https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-fw-npu_1.16.0.20250328-14132024782_ubuntu22.04_amd64.deb" https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-level-zero-npu_1.16.0.20250328-14132024782_ubuntu22.04_amd64.deb)
declare -a npu_files_driver_ubuntu24=("https://github.com/oneapi-src/level-zero/releases/download/v1.20.2/level-zero_1.20.2+u24.04_amd64.deb" "https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-driver-compiler-npu_1.16.0.20250328-14132024782_ubuntu24.04_amd64.deb" "https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-fw-npu_1.16.0.20250328-14132024782_ubuntu24.04_amd64.deb" "https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-level-zero-npu_1.16.0.20250328-14132024782_ubuntu24.04_amd64.deb")

# Test Utilities
declare -a test_tools=("mosquitto-clients" "curl" "ffmpeg" "vlc-bin")

