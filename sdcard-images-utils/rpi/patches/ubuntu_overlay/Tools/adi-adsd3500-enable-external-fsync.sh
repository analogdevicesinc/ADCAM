#!/bin/bash

# --- Dynamically fetch GPIO labels ---
declare -A GPIO

# List of GPIO labels we are interested in, including ISP_RST at the start
GPIO_LIST=("NET_HOST_IO_SEL" "HOST_IO_DIR")

# Now process the GPIO labels, starting from the second element (index 1)
for label in "${GPIO_LIST[@]}"; do
    # Search for each GPIO label in the debug output and extract the GPIO number
    result=$(sudo cat /sys/kernel/debug/gpio | grep -i "\b$label\b")

    # Check if the result is non-empty and contains the GPIO number
    if [[ -n "$result" ]]; then
        gpio_num=$(echo "$result" | sed -E 's/.*gpio-([0-9]+).*/\1/')

        # Store the GPIO number in the associative array
        if [[ -n "$gpio_num" ]]; then
            GPIO["$label"]=$gpio_num
            echo "Label: $label -> GPIO$gpio_num" > /dev/null
        else
            echo "Label: $label found, but GPIO number not extracted correctly"
	    exit 0
        fi
    else
        echo "Label: $label not found"
	exit 0
    fi
done

# Set 0: EXT_FSYNC / 1: ISP_INT
echo 0 > /sys/class/gpio/gpio${GPIO[NET_HOST_IO_SEL]}/value

# Set 0: EXT_FSYNC / 1: ISP_INT
echo 0 > /sys/class/gpio/gpio${GPIO[HOST_IO_DIR]}/value

# Enable external fsync
v4l2-ctl --set-ctrl=fsync_trigger=0 -d /dev/v4l-subdev2
