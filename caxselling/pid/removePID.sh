#!/bin/bash
# Purpose: Stop PID (if running) abd remove the installed libraries (Including drivers)
# Script: Mario Divan
# ------------------------------------------

source ./scripts/utilities.sh

removeImages() {    
    mess_inf "Removing Containers' Images from Docker"
    #It verifies the container to remove from the docker-compose file. 
    readarray -t containers <<< $(fgrep image: ./docker-compose.yml | sed 's/^.*: //')
    for idcontainer in "${containers[@]}"; do
        #It verifies if the container is running
        if sudo docker rmi -f "$idcontainer" &> /dev/null; then #> /dev/null 2>&1
            # Check whether the image was removed           
            if  sudo docker images | grep -q "$idcontainer" &> /dev/null; then
                mess_er2 "\t$idcontainer: " "It could not be removed"
                exit 99
            else
                mess_ok2 "\t$idcontainer: " "Removed"
            fi            
        else
            #If not present, the image was removed
            mess_ok2 "$idcontainer: " "Removed"
        fi
    done    
}

mess_inf "Verifying OS Compatibility"
if [ -f "/etc/os-release" ]; then
  source /etc/os-release
  if [[ "$ID" == "ubuntu" ]]; then

    if [[ "$VERSION_ID" == "22.04" ]]; then
      UBUNTU2404="false"
    elif [[ "$VERSION_ID" == "24.04" ]]; then
      UBUNTU2404="true"
    else
      mess_err "Ubuntu version is not 22.04 or 24.04."
      exit 1
    fi
    
    mess_ok2 "OS: " "$PRETTY_NAME"    
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
    mess_inf "Proceeding with the driver verification and removal on $PRETTY_NAME."
else
    mess_err "Installation control variable not set. Exiting."
    exit 1
fi

# Stop containers (if required)
mess_inf "Stopping PID containers"
if ./runPID.sh stop; then
    mess_ok2 "\tPID Containers: " "Stopped"
else
    mess_err "\tPID Containers: " "No Stopped"
    exit 1
fi

if removeImages; then
    mess_ok2 "\tPID containers: " "Removed"
else
    mess_er2 "\tPID Containers: " "Not Removed"
    exit 1
fi
 
mess_inf "Intel NPU (Neural Processing Unit) Linux Driver > Removing Existing Versions"
if sudo dpkg --purge --force-remove-reinstreq intel-driver-compiler-npu intel-fw-npu intel-level-zero-npu &> /dev/null; then
    mess_ok2 "\tIntel NPU Driver: " "Removed"
else
    mess_er2 "\tIntel NPU Driver: " "Not Removed"
fi  

mess_inf "Intel dGPU/iGPU Linux Driver > Removing Existing Versions"
GPU_driverlist=($(getDriverNames gpu_files_driver))
if is_array GPU_driverlist; then
    mess_ok2 "\tGPU Driver: " "Available List"
else
    mess_er2 "\tGPU Driver: " "Unavailable List"
    exit 1
fi

oneline="${GPU_driverlist[*]}"
sudo dpkg --purge --force-remove-reinstreq $oneline &> /dev/null
mess_ok2 "\tIntel dGPU/iGPU Driver: " "Removed"

mess_inf "APT Dependencies Maintenance"
sudo apt --fix-broken install -y &> /dev/null

mess_oki "PID Removal Completed"
