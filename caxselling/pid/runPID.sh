#!/bin/bash
# Purpose: It runs the PID containers
# Script: Mario Divan
# ------------------------------------------

source ./scripts/utilities.sh

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
    #Drivers
    mess_inf "Checking [Drivers] ..."
    if isInstalled "clinfo" &> /dev/null; then
        CLINFO=$(clinfo -v)   
        mess_oki "\t$CLINFO"
    else
        mess_err "\tclinfo package not found"
        exit 1
    fi
    
    COUNTER=$(clinfo | fgrep "Driver Version" | wc -l)
    if [[ $COUNTER -gt 0 ]]; then        
        GPU_VAR=$(clinfo | fgrep "Driver Version")
        mess_oki "\tiGPU/dGPU: Loaded!"
        mess_oki "\t$GPU_VAR"
    else
        mess_war "\t\tiGPU/dGPU: Not loaded"
    fi

    COUNTER=$(sudo dmesg | fgrep -i "vpu" | wc -l)
    if [[ $COUNTER -gt 0 ]]; then        
        NPU_VAR=$(sudo dmesg | fgrep -i "vpu")
        mess_oki "\tNPU: Loaded!"
        mess_oki "\t\t$NPU_VAR"
    else
        mess_war "\tNPU: Not Loaded"
    fi

    #Container Status
    #It verifies the container Status. 
    mess_inf "Container Status:"
    readarray -t containers <<< $(fgrep container_name: ./docker-compose.yml | sed 's/^.*: //')
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
    mess_inf "Starting PID containers ..."

    if check; then
        mess_oki "Docker and drivers."
    else
        mess_err "Docker or drivers are not installed correctly. Please check your installation."
        exit 1
    fi

    if test -e ./docker-compose.yml; then
        mess_oki "\tDocker compose file found"
    else
        mess_err "\tDocker compose file not found"
        exit 1
    fi

    #It Verifies to avoid twice the same container
    COUNTER=0
    readarray -t containers <<< $(fgrep container_name: ./docker-compose.yml | sed 's/^.*: //')
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

    if docker compose up -d &> /dev/null; then
        mess_oki "Docker containers are up and running."
    else
        mess_err "Docker containers failed to start. Please check your Docker Compose configuration."
        exit 1
    fi

    #It verifies the container Status. 
    readarray -t containers <<< $(fgrep container_name: ./docker-compose.yml | sed 's/^.*: //')
    for idcontainer in "${containers[@]}"; do
        running_status=$(docker inspect -f '{{.State.Running}}' $idcontainer 2> /dev/null)
        if [ "$running_status" == "true" ]; then
            mess_op2 "\t$idcontainer: " "Running"
        else
            mess_er2 "\t$idcontainer:  " "Unavailable"
        fi            
    done    
}

stop() {
    ##Stopping Process
    mess_inf "Stopping PID containers ..."

    if docker compose down &> /dev/null; then
        mess_oki "Docker containers are stopped."
    else
        mess_err "Docker containers failed to stop. Please check your Docker Compose configuration."
        exit 1
    fi

    #It verifies the container Status. 
    readarray -t containers <<< $(fgrep container_name: ./docker-compose.yml | sed 's/^.*: //')
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

e2e() { 
    #Tools
    for idx in "${test_tools[@]}"; do
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

    #Container Status
    #It verifies the container Status. 
    readarray -t containers <<< $(fgrep container_name: ./docker-compose.yml | sed 's/^.*: //')
    for idcontainer in "${containers[@]}"; do
        running_status=$(docker inspect -f '{{.State.Running}}' $idcontainer 2> /dev/null)
        if [ "$running_status" == "true" ]; then
            mess_oki "$idcontainer: Running"
        else
            mess_err "$idcontainer: Unavailable"
            exit 99
        fi            
    done    

    #Test MQTT
    mess_inf "Triggering the MQTT pipeline with default video"
   	curl localhost:8080/pipelines/user_defined_pipelines/pallet_defect_detection -X POST -H 'Content-Type: application/json' -d '{
		"source": {
			"uri": "file:///home/pipeline-server/resources/videos/classroom.avi",
			"type": "uri"
		},
		"destination": {
			"metadata": {
				"type": "mqtt",
				"publish_frame": false,
				"topic": "topic_od_mjd",
				"host":"mqtt:1883",
				"mqtt-client-id": "gva-meta-publish"
			},
			"frame": {
				"type": "rtsp",
				"path": "classroom-video-streaming"
			}
		},
		"parameters": {
			"detection-properties": {
				"model": "/home/pipeline-server/yolo_models/yolo11s/FP32/yolo11s.xml",
				"device": "CPU"
			}
		}
	}'

    mess_inf "Pipeline status: "
    curl --location -X GET http://localhost:8080/pipelines/status

    mess_inf "Subscribing to the MQTT topic: topic_od_mjd"
    
    mess_inf "Open your VLC Viewer at rtsp://localhost:8554/classroom-video-streaming for visualization."
    
    if [ -e ./e2e_detections.json ]; then
        rm -rf ./e2e_detections.json
    fi

    mess_inf "Subscribing to the MQTT topic: topic_od_mjd (See them in ./e2e_detections.json)"
    mosquitto_sub --topic topic_od_mjd -p 1883 -h 127.0.0.1 > ./e2e_detections.json &
}

help() {
    mess_inf "Usage: "
    mess_op1 "\t./runPID.sh [start | stop | check | e2e | help]"
    mess_op1 "\nOptions:"
    mess_op2 "\tstart: " "Start the PID containers."
    mess_op2 "\tstop: " "Stop the PID containers."
    mess_op2 "\tcheck: " "It verifies the docker installation and installed drivers."
    mess_op2 "\te2e: " "It triggers a pipeline using Yolo v11 for detection and consumes it through MQTT messages."    
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
    "e2e")
        e2e
    ;;
    "help")
        help
    ;;
    *)
        error
    ;;
esac

