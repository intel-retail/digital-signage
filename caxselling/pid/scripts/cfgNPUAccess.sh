#!/bin/bash
# Purpose: Configure NPU access when available
# Script: Mario Divan
# ------------------------------------------

source ./scripts/utilities.sh

USER=$(whoami)
ACCELERATOR="/dev/accel/accel0"
UDEV_RULES="/etc/udev/rules.d/10-intel-vpu.rules"

function NPUsetup() {
    if [[ -n $1 ]]; then
        mess_inf "Verifying NPU Access Setup for: $1"
        USER=$1
    else
        mess_inf "Verifying NPU Access Setup for: $USER"
    fi

    if existUser $USER; then
        mess_ok2 "\tUser: " "OK"
    else
        mess_er2 "\tUser: " "Not found"
        return 1
    fi

    if test -e "$ACCELERATOR"; then
        mess_ok2 "\tNPU Device: " "Found."
    else
        mess_wa2 "\tNPU Device: " "Not Found"
        return 1
    fi

    # set the render group for accel device
    if [ "$(stat -c %U $ACCELERATOR)" == "root" ]; then
      if [ "$(stat -c %G $ACCELERATOR)" == "render" ]; then
        mess_ok2 "\tNPU Device Owner: " "root:render"
      else
        if sudo chown root:render "$ACCELERATOR"; then
            mess_ok2 "\tNPU Device Owner: " "root:render"
        else
            mess_wa2 "\tNPU Device Owner: " "Failed!"
            return 1
        fi
      fi
    else
        if sudo chown root:render "$ACCELERATOR"; then
            mess_ok2 "\tNPU Device Owner: " "root:render"
        else
            mess_wa2 "\tNPU Device Owner: " "Failed!"
            return 1
        fi
    fi

    if [[ -g "$ACCELERATOR" ]] && [[ -r "$ACCELERATOR" ]] && [[ -w "$ACCELERATOR" ]]; then
        mess_ok2 "\tNPU Device - Group Permissions: " "OK"
    else
        if sudo chmod g+rw "$ACCELERATOR"; then
            mess_ok2 "\tNPU Device - Group Permissions: " "OK"
        else
            mess_wa2 "\tNPU Device - Group Permissions: " "Failed!"
            return 1
        fi
    fi

    # add user to the render group
    if sudo usermod -a -G render "$USER"; then
        mess_ok2 "\tNPU Device - Group: " "$USER > Found"
    else
        mess_wa2 "\tNPU Device - Group: " "$USER > Not Found"
        return 1
    fi

    # user needs to restart the session to use the new group (log out and log in)
     if test -e "$UDEV_RULES"; then
        mess_ok2 "\tNPU Device - udev rules: " "Found"
    else
        if sudo bash -c "echo 'SUBSYSTEM==\"accel\", KERNEL==\"accel*\", GROUP=\"render\", MODE=\"0660\"' > $UDEV_RULES"; then
            mess_ok2 "\tNPU Device - udev rules: " "Registered"
        else
            mess_wa2 "\tNPU Device - udev rules: " "Failed"
            return 1
        fi
    fi   

    if sudo udevadm control --reload-rules; then
        mess_ok2 "\tNPU Device - udev rules reload: " "OK"
    else
        mess_wa2 "\tNPU Device - udev rules reload: " "Failed"
        retrun 1
    fi

    if sudo udevadm trigger --subsystem-match=accel; then
        mess_ok2 "\tNPU Device - udev rules triggering: " "OK"
    else
        mess_wa2 "\tNPU Device - udev rules triggering: " "Failed"
        retrun 1
    fi

    mess_oki "The NPU Device Access for $USER has been successfully completed."
    return 0
}