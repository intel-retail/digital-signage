#!/bin/bash
# Purpose: Stop AIG (if running) abd remove the installed libraries (Including drivers)
# Script: Mario Divan
# ------------------------------------------

source ../pid/scripts/utilities.sh

removeImages() {    
    mess_inf "Removing Containers' Images from Docker"
    #It verifies the container to remove from the docker-compose file. 
    readarray -t containers <<< $(fgrep image: ./docker/docker-compose.yml | sed 's/^.*: //')
    for idcontainer in "${containers[@]}"; do
        image_ids=$(sudo docker images "$idcontainer" --format "{{.ID}}")

        if [ -n "$image_ids" ]; then
            echo "$image_ids" | xargs -r sudo docker rmi -f > /dev/null 2>&1
            mess_ok2 "$idcontainer: " "Removed (all tags)"
        else
            mess_ok2 "$idcontainer: " "No images found"
        fi        
    done    
}

mess_war "This action will remove AIG Docker images from your system. "
read -p "Are you sure to continue? (y/n) " -n 1 -r
echo    # (optional) move to a new line
if [[ $REPLY =~ ^[Yy]$ ]]
then
  # commands if yes
  mess_ok2 "Delete Procedure: " "Confirmed"
else
  # commands if no
  mess_wa2 "Delete Procedure: " "Cancelled"
  exit 1
fi

mess_inf "Verifying Docker Installation"

if docker run hello-world >& /dev/null; then
    mess_oki "Docker is running correctly."
else
    mess_err "Docker is not running correctly. Please check your Docker installation."
    exit 1
fi

# Stop containers (if required)
mess_inf "Stopping AIG containers"
if ./runAIG.sh stop; then
    mess_ok2 "\tAIG Containers: " "Stopped"
else
    mess_err "\tAIG Containers: " "No Stopped"
    exit 1
fi

mess_inf "Removing AIG Docker images from your system"
if removeImages; then
    mess_ok2 "\tAIG containers: " "Removed"
else
    mess_er2 "\tAIG Containers: " "Not Removed"
    exit 1
fi

mess_inf "Removing the Virtual Environment of Models"
if [ -d ./docker/.modelenv ]; then
    if rm -rf ./docker/.modelenv; then
        mess_ok2 "\tModels Virtual Environment: " "Removed"
    else
        mess_er2 "\tModels Virtual Environment: " "Not Removed"
        exit 1
    fi
else
    mess_ok2 "\tModels Virtual Environment: " "Removed"
fi

if rm -rf ./docker/models/* ./docker/models/.[!.]*; then
    mess_ok2 "\tModels Directory: " "Cleaned"
else
    mess_wa2 "\tModels Directory: " "Not Removed"
fi

mess_oki "AIG Removal Completed"