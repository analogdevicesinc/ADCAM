#!/bin/bash

# --- Dynamically fetch GPIO labels ---
declare -A GPIO

# List of GPIO labels we are interested in, including ISP_RST at the start
GPIO_LIST=("ISP_RST")

# Check for GPIO34 first and assign it directly to ISP_RST
GPIO34_RESULT=$(sudo cat /sys/kernel/debug/gpio | grep -i "\bGPIO34\b")
if [[ -n "$GPIO34_RESULT" ]]; then
    gpio_num=$(echo "$GPIO34_RESULT" | sed -E 's/.*gpio-([0-9]+).*/\1/')
    if [[ -n "$gpio_num" ]]; then
        GPIO["ISP_RST"]=$gpio_num
        echo "Special case: GPIO34 assigned to ISP_RST -> GPIO$gpio_num" > /dev/null
    else
        echo "GPIO34 found, but GPIO number not extracted correctly"
        exit 0
    fi
else
    echo "GPIO34 not found"
    exit 0
fi


echo 0 > /sys/class/gpio/gpio${GPIO[ISP_RST]}/value

sleep 1

echo 1 > /sys/class/gpio/gpio${GPIO[ISP_RST]}/value

