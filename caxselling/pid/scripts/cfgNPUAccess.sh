#!/bin/bash
# Purpose: Configure NPU access when available
# Script: Mario Divan
# ------------------------------------------

source ./utilities.sh

mess_inf "Configuring NPU access for Non-root users"

if test -e /dev/accel/accel0; then
    mess_oki "\tNPU device found."
else
    mess_err "\tNPU device not found. Please check the NPU installation and reboot your system."
    exit 1
fi

mess_inf "\nSetting up NPU access for user: $(whoami)"
# set the render group for accel device
sudo chown root:render /dev/accel/accel0
sudo chmod g+rw /dev/accel/accel0
# add user to the render group
if sudo usermod -a -G render $(whoami); then
    mess_oki "User $(whoami) added to render group. Add any other users to the render group as needed!!!"
else
    mess_err "Failed to add user $(whoami) to render group."
    exit 1
fi

# user needs to restart the session to use the new group (log out and log in)
mess_inf "\tDefining udev rule for the accelerator device"
if sudo bash -c "echo 'SUBSYSTEM==\"accel\", KERNEL==\"accel*\", GROUP=\"render\", MODE=\"0660\"' > /etc/udev/rules.d/10-intel-vpu.rules"; then
    mess_oki "\tUdev rule created successfully."
else
    mess_err "\tFailed to create udev rule."
    exit 1
fi

if sudo udevadm control --reload-rules; then
    mess_oki "\tUdev rules reloaded successfully."
else
    mess_err "\tFailed to reload udev rules."
    exit 1
fi

if sudo udevadm trigger --subsystem-match=accel; then
    mess_oki "\tUdev rules triggered successfully."
else
    mess_err "\tFailed to trigger udev rules."
    exit 1
fi

mess_oki "\nNPU access is configured successfully. Restart the user session for the changes to take effect."