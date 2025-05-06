#!/bin/bash
# Purpose: Check PID pre-requisites and Install Intel GPU and NPU drivers
# Script: Mario Divan
# ------------------------------------------

source ./scripts/utilities.sh

mess_inf "Verifying Docker Availability"
# Check if docker is installed
if docker version >& /dev/null; then
    mess_oki "Docker is installed."
    docker version
else
    mess_err "Docker is not installed or could not be reached. Please install Docker (https://docs.docker.com/engine/install/ubuntu/)."
    exit 1
fi

mess_inf "Verifying Docker Installation"

if docker run hello-world >& /dev/null; then
    mess_oki "Docker is running correctly."
else
    mess_err "Docker is not running correctly. Please check your Docker installation."
    exit 1
fi

mess_inf "Verifying OS Compatibility"
if [ -f "/etc/os-release" ]; then
  source /etc/os-release
  if [[ "$ID" == "ubuntu" ]]; then

    if [[ "$VERSION_ID" == "22.04" ]]; then
      mess_oki "$PRETTY_NAME detected."
      UBUNTU2404="false"
    elif [[ "$VERSION_ID" == "24.04" ]]; then
      mess_oki "$PRETTY_NAME detected."
      UBUNTU2404="true"
    else
      mess_err "Ubuntu version is not 22.04 or 24.04."
      exit 1
    fi
  else
    mess_err "Not Ubuntu. OS is $NAME $VERSION_ID."
    mess_err "This script is designed for Ubuntu 22.04 or 24.04."
    exit 1
  fi
else
  mess_err "Cannot determine OS."
  exit 1
fi

# Checking Installation Control Variable
if [[ -v UBUNTU2404 ]]; then
    mess_inf "Proceeding with the driver verification and installation on $PRETTY_NAME."
else
  mess_err "Installation control variable not set. Exiting."
  exit 1
fi

#
mess_inf "Verifying essential dependencies..."
sudo apt --fix-broken install
mess_inf "Updating apt..."
sudo apt update &> /dev/null
mess_inf "Upgrading libraries..."
sudo apt upgrade -y &> /dev/null
clear

#GPU Driver Installation
    # Dependencies
NDEPENDENCIES_GPU=${#gpu_dependencies[*]}
mess_inf "iGPU/dGPU Driver > Dependencies ($NDEPENDENCIES_GPU)"
for idx in "${gpu_dependencies[@]}"; do
    if isInstalled "$idx" &> /dev/null; then
        mess_oki "\t $idx"
    else
        sudo apt install "$idx" -y &> /dev/null

        if isInstalled "$idx" &> /dev/null; then
                mess_oki "\t $idx"
        else
                mess_err "$idx could not be installed"
                exit 99
        fi
    fi
done

sudo apt --fix-broken install -y > /dev/null

    # Driver
      ## GPU Driver Version
mess_inf "iGPU/dGPU Driver"    
mess_inf "\tCreating the GPU directory" 

if [[ -d "GPU" ]]; then
    mess_war "\tGPU directory already exists. Removing it."
    rm -rf GPU
fi

if mkdir GPU; then
    mess_oki "\tGPU directory created."
else
    mess_err "\tFailed to create GPU directory."
    exit 1
fi

cd GPU || exit 1

if [[ "$UBUNTU2404" == "true" ]]; then
    sudo dpkg -r intel-ocloc-dev intel-ocloc libze-intel-gpu1 &> /dev/null
fi
    
for idx in "${gpu_files_driver[@]}"; do
    mess_inf "\tDownloading $idx"
    wget "$idx" -O "$(basename "$idx")" &> /dev/null  &> /dev/null  
    if [[ $? -ne 0 ]]; then
        mess_err "Failed to download $idx"
        cd ..
        rm -rf GPU
        exit 1
    fi

    mess_inf "\tInstalling $idx"
    sudo dpkg -i "$(basename "$idx")" &> /dev/null
    if [[ $? -ne 0 ]]; then
        mess_err "\tFailed to install $(basename "$idx")"
        cd ..
        rm -rf GPU
        exit 1
    else
        mess_oki "\t$(basename "$idx") installed successfully."
    fi
done

cd ..
if rm -rf GPU   ; then
    mess_oki "\tGPU directory removed."    
else
    mess_err "\tFailed to remove GPU directory."
fi

mess_oki "\tIntel Graphics Compute Runtime Driver v$GPU_FILES_DRIVER_VERSION (iGPU/dGPU) installed successfully."

    ## NPU Driver Version
      # Remove oldest ones
mess_inf "\nIntel NPU (Neural Processing Unit) Linux Driver > Removing Existing Versions"
dpkg --purge --force-remove-reinstreq intel-driver-compiler-npu intel-fw-npu intel-level-zero-npu &> /dev/null  

      # Dependencies 
mess_inf "\tIntel NPU (Neural Processing Unit) Linux Driver > Installing Dependencies"
for idx in "${npu_dependencies[@]}"; do
    if isInstalled "$idx" &> /dev/null; then
        mess_oki "\t\t $idx"
    else
        sudo apt install "$idx" -y

        if isInstalled "$idx" &> /dev/null; then
                mess_oki "\t\t $idx"
        else
                mess_err "\t$idx could not be installed"
                exit 99
        fi
    fi
done

sudo apt --fix-broken install -y > /dev/null

    # NPU Driver by OS version
if [[ -d "NPU" ]]; then
    mess_war "\tNPU directory already exists. Removing it."
    rm -rf NPU
fi

if mkdir NPU && cd NPU; then
    mess_oki "\tNPU directory created."
else
    mess_err "\tFailed to create NPU directory."
    exit 1
fi

if [[ "$UBUNTU2404" == "true" ]]; then
  declare -n npu_files_driver=npu_files_driver_ubuntu24
else
  declare -n npu_files_driver=npu_files_driver_ubuntu22
fi

for idx in "${npu_files_driver[@]}"; do
    mess_inf "\tDownloading $idx"
    wget "$idx" -O "$(basename "$idx")" &> /dev/null  
    if [[ $? -ne 0 ]]; then
        mess_err "\tFailed to download $idx"
        cd ..
        rm -rf NPU
        exit 1
    fi

    mess_inf "\tInstalling $idx"
    sudo dpkg -i "$(basename "$idx")" > /dev/null
    if [[ $? -ne 0 ]]; then
        mess_err "\tFailed to install $(basename "$idx")"
        cd ..
        rm -rf NPU
        exit 1
    else
        mess_oki "\t$(basename "$idx") installed successfully."
    fi
done    

cd ..
if rm -rf NPU   ; then
    mess_oki "\tNPU directory removed."    
else
    mess_err "\tFailed to remove NPU directory."
fi

mess_oki "\tIntel Neural Processing Unit Driver $NPU_FILES_DRIVER_VERSION (NPU) installed successfully."