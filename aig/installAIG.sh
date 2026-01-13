#!/bin/bash -x
# Purpose: Check AIG pre-requisites and Install Intel GPU and NPU drivers
# Script: Mario Divan
# ------------------------------------------

source ../pid/scripts/utilities.sh
source ./docker/.env

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

if test -e ./docker/docker-compose.yml; then
    mess_ok2 "\tDocker compose file: " "Found"
else
    mess_er2 "\tDocker compose file: " "Not Found"
    exit 1
fi

if checkDockerNetwork; then
    mess_oki "Docker network is available."
else
    mess_err "Docker network is not available. Please check your Docker installation."
    exit 1
fi

# Pull and create the docker image
mess_inf "Pulling the AIG Docker image ..."
readarray -t theimages <<< $(fgrep image: ./docker/docker-compose.yml | sed 's/^.*: //')
for animage in "${theimages[@]}"; do
    if [[ $animage == *"aig"* ]]; then
        mess_wa2 "\t$animage: " "To be created"
        continue
    else
        running_status=$(docker pull $animage 2> /dev/null)
        
        if docker inspect --type=image "$animage" > /dev/null 2>&1; then
            mess_op2 "\t$animage: " "Available"
        else
            mess_er2 "\t$animage:  " "Unavailable"
        fi            
    fi  
done 

# mess_inf "Creating AIG Server ..."
# if docker compose -f ./docker/docker-compose.yml build; then 
#     mess_ok2 "\tAIG Server (RestX): " "Created"
# else
#     mess_er2 "\tAIG Server (RestX): " "Failed"
#     exit 1
# fi

mess_inf "Creating Virtual Environment for Model Download and Conversion ..."
if [ -d docker ]; then
    cd docker || exit 1
else
    mess_er2 "docker folder does not exist"
fi

if [ -d .modelenv ]; then
    if rm -rf .modelenv; then
        mess_ok2 "\tVirtual Environment: " "Removed"
    else
        mess_er2 "\tVirtual Environment: " "Failed to remove"
        exit 1
    fi
fi

if python3 -m venv .modelenv; then
    mess_ok2 "\tVirtual Environment: " "Created"
else
    mess_er2 "\tVirtual Environment: " "Failed to recreate"
    exit 1
fi

if source ./.modelenv/bin/activate; then
    mess_ok2 "\tVirtual Environment: " "Activated"
else
    mess_er2 "\tVirtual Environment: " "Failed to activate"
    exit 1
fi

if pip install --upgrade pip 1>/dev/null 2>&1; then
    mess_ok2 "\tPip: " "Upgraded"
else
    mess_er2 "\tPip: " "Failed to upgrade"
    exit 1
fi

# Start pip install in the background
pip install --upgrade-strategy eager -r export-requirements.txt 
#1>/dev/null 2>&1 & pip_pid=$!

# # Spinner animation
# spin='-\|/'
# i=0
# mess_op2 "\tRequirements: " "Installing..."
# while kill -0 $pip_pid 2>/dev/null; do
#     i=$(( (i+1) %4 ))
#     printf "\r ${spin:$i:1}"
#     sleep 0.2
# done

wait $pip_pid
pip_status=$?

if [ $pip_status -eq 0 ]; then
    mess_ok2 "\tRequirements: " "Installed"
else
    mess_er2 "\tRequirements: " "Failed to install"
    exit 1
fi

if [ -d ./models/dreamlike_anime_1_0_ov ]; then
    if rm -rf ./models/dreamlike_anime_1_0_ov; then
        mess_ok2 "\tOld Model: " "Removed"
    else
        mess_er2 "\tOld Model: " "Failed to remove"
        exit 1
    fi
fi

cd ..

if [ -n "$SUDO_USER" ]; then
    chown -R $SUDO_USER:$SUDO_USER ./docker/models/
else
    mess_wa2 "\tRunning as root: " "Skipping ownership change"
fi

mess_oki "All Containers are available and ready for execution!"