#!/bin/bash

if [[ $EUID > 0 ]]; then
        echo "This script must be run as root user"
        echo "Usage: sudo ./adi-adsd3500-reset.sh"
        exit
fi

sudo echo 0 > /sys/class/gpio/PAC.00/value

sleep 1

sudo echo 1 > /sys/class/gpio/PAC.00/value

