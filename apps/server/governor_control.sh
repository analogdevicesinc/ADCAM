#!/bin/bash

# Check if an argument is provided
if [ -z "$1" ]; then
    echo "Usage: $0 {on|off}"
    exit 1
fi

case "$1" in
    on)
        echo "Setting governor to 'schedutil'..."
        echo schedutil | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
        ;;
    off)
        echo "Setting governor to 'performance'..."
        echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
        ;;
    *)
        echo "Invalid option. Please use 'on' or 'off'."
        exit 1
        ;;
esac
