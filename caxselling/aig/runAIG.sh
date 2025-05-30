#!/bin/bash
# Purpose: It runs the AIG containers
# Script: Mario Divan
# ------------------------------------------

source ../pid/scripts/utilities.sh

# Functions
error() {
    mess_war "The indicated action is not recognized."
    help
    exit 1
}

check() {
    #Docker
    mess_inf "Checking [Docker] ..."
    if docker run hello-world >& /dev/null; then
        mess_oki "Docker is running correctly."
    else
        mess_err "Docker is not running correctly. Please check your Docker installation."
        exit 1
    fi

    #Container Status
    #It verifies the container Status. 
    mess_inf "Container Status:"
    readarray -t containers <<< $(fgrep container_name: ./docker/docker-compose.yml | sed 's/^.*: //')
    for idcontainer in "${containers[@]}"; do
        running_status=$(docker inspect -f '{{.State.Running}}' $idcontainer 2> /dev/null)
        if [ "$running_status" == "true" ]; then
            mess_op2 "\t$idcontainer: " "Running"
        else
            mess_er2 "\t$idcontainer:  " "Unavailable"
        fi            
    done    

    return 0
}

start() {
    ##Starting Process
    mess_inf "Starting AIG containers ..."

    if check; then
        mess_ok2 "Docker and Containers: " "OK"
    else
        mess_wa2 "Docker and Containers: " "Failed"
        exit 1
    fi
    
    if test -e ./docker/docker-compose.yml; then
        mess_ok2 "\tDocker compose file: " "Found"
    else
        mess_er2 "\tDocker compose file: " "Not Found"
        exit 1
    fi

    #It Verifies to avoid twice the same container
    COUNTER=0
    readarray -t containers <<< $(fgrep container_name: ./docker/docker-compose.yml | sed 's/^.*: //')
    for idcontainer in "${containers[@]}"; do
        running_status=$(docker inspect -f '{{.State.Running}}' $idcontainer 2> /dev/null)
        if [ "$running_status" == "true" ]; then
            COUNTER=$((COUNTER+1))
        fi            
    done    

    if [[ $COUNTER -eq ${#containers[@]} ]]; then
        mess_oki "Containers already running!"        
        exit 0
    fi

    if docker compose -f ./docker/docker-compose.yml  up -d ; then #&> /dev/null
        mess_oki "Docker containers are up and running."
    else
        mess_err "Docker containers failed to start. Please check your Docker Compose configuration."
        exit 1
    fi

    #It verifies the container Status. 
    readarray -t containers <<< $(fgrep container_name: ./docker/docker-compose.yml | sed 's/^.*: //')
    for idcontainer in "${containers[@]}"; do
        running_status=$(docker inspect -f '{{.State.Running}}' $idcontainer 2> /dev/null)
        if [ "$running_status" == "true" ]; then
            mess_op2 "\t$idcontainer: " "Running"
        else
            mess_er2 "\t$idcontainer: " "Unavailable"
        fi            
    done    
}

stop() {
    ##Stopping Process
    mess_inf "Stopping AIG containers ..."

    if docker compose -f ./docker/docker-compose.yml  down &> /dev/null; then
        mess_oki "Docker containers are stopped."
    else
        mess_err "Docker containers failed to stop. Please check your Docker Compose configuration."
        exit 1
    fi

    #It verifies the container Status. 
    readarray -t containers <<< $(fgrep container_name: ./docker/docker-compose.yml | sed 's/^.*: //')
    for idcontainer in "${containers[@]}"; do
        #It verifies if the container is running
        if docker inspect $container_id > /dev/null 2>&1; then
            #If so, it will collect the status
            running_status=$(docker inspect -f '{{.State.Running}}' $idcontainer)
            if [ "$running_status" == "true"]; then
                mess_war "$idcontainer: Running"
            else
                mess_oki "$idcontainer: Stopped"
            fi            
        else
            #If not present, the container was fully stopped
            mess_oki "$idcontainer: Stopped"
        fi
    done    
}

help() {
    mess_inf "Usage: "
    mess_op1 "\t./runAIG.sh [start | stop | check | help]"
    mess_op1 "\nOptions:"
    mess_op2 "\tstart: " "Start the AIG containers."
    mess_op2 "\tstop: " "Stop the AIG containers."
    mess_op2 "\tcheck: " "It verifies the docker installation and containers."
    mess_op2 "\thelp: " "Show this help message."
}

# Actions
ACTION="up"

if [[ $1 ]];    then
    ACTION=$1
fi

case "$ACTION" in
    "start")
        start
    ;;
    "stop")
        stop
    ;;
    "check")
        check
    ;;
    "help")
        help
    ;;
    *)
        error
    ;;
esac