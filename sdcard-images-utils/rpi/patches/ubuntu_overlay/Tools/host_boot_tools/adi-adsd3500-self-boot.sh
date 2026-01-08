#!/bin/bash

MODULE=$(tr -d '\0' < /proc/device-tree/chosen/overlay-name 2>/dev/null)

declare -A GPIO

# Function to dynamically fetch GPIO labels
fetch_gpio_labels() {

    # List of GPIO labels we are interested in, including ISP_RST at the start
    GPIO_LIST=("ISP_RST" "EN_1P8" "EN_0P8" "I2CM_SEL" "ISP_BS0" "ISP_BS1" "ISP_BS4" "ISP_BS5")

    # Check for GPIO34 first and assign it directly to ISP_RST
    GPIO34_RESULT=$(sudo cat /sys/kernel/debug/gpio | grep -i "\bGPIO34\b" 2>/dev/null)
    if [[ -n "$GPIO34_RESULT" ]]; then
        gpio_num=$(echo "$GPIO34_RESULT" | sed -E 's/.*gpio-([0-9]+).*/\1/')
        if [[ -n "$gpio_num" ]]; then
            GPIO["ISP_RST"]=$gpio_num
            echo "Special case: GPIO34 assigned to ISP_RST -> GPIO$gpio_num" >/dev/null
        else
            echo "GPIO34 found, but GPIO number not extracted correctly"
	    exit 0
        fi
    else
        echo "GPIO34 not found"
	exit 0
    fi

    # Now process the GPIO labels, starting from the second element (index 1)
    for label in "${GPIO_LIST[@]:1}"; do
        # Search for each GPIO label in the debug output and extract the GPIO number
        result=$(sudo cat /sys/kernel/debug/gpio | grep -i "\b$label\b" 2>/dev/null)

        # Check if the result is non-empty and contains the GPIO number
        if [[ -n "$result" ]]; then
            gpio_num=$(echo "$result" | sed -E 's/.*gpio-([0-9]+).*/\1/')

            # Store the GPIO number in the associative array
            if [[ -n "$gpio_num" ]]; then
                GPIO["$label"]=$gpio_num
                echo "Label: $label -> GPIO$gpio_num" >/dev/null
            else
                echo "Label: $label found, but GPIO number not extracted correctly"
		exit 0
            fi
        else
            echo "Label: $label not found"
	    exit 0
        fi
    done

}

adsd3500_power_sequence() {

    # Pull ADSD3500 reset low
    echo 0 > /sys/class/gpio/gpio${GPIO[ISP_RST]}/value

    # Disable the supply voltage
    echo 0 > /sys/class/gpio/gpio${GPIO[EN_1P8]}/value
    echo 0 > /sys/class/gpio/gpio${GPIO[EN_0P8]}/value

    sleep 0.2

    # I2CM_SEL
    echo 0 > /sys/class/gpio/gpio${GPIO[I2CM_SEL]}/value

    # ISP_BS0
    echo 0 > /sys/class/gpio/gpio${GPIO[ISP_BS0]}/value

    # ISP_BS1
    echo 0 > /sys/class/gpio/gpio${GPIO[ISP_BS1]}/value

    # ISP_BS4
    echo 0 > /sys/class/gpio/gpio${GPIO[ISP_BS4]}/value

    # ISP_BS5
    echo 0 > /sys/class/gpio/gpio${GPIO[ISP_BS5]}/value

    # Re-enable the supply voltage
    echo 1 > /sys/class/gpio/gpio${GPIO[EN_1P8]}/value
    sleep 0.2

    echo 1 > /sys/class/gpio/gpio${GPIO[EN_0P8]}/value
    sleep 0.2

    # Pull ADSD3500 reset high
    echo 1 > /sys/class/gpio/gpio${GPIO[ISP_RST]}/value
}

enable_self_boot() {

    case $MODULE in
        "adi_dual_adsd3500_adsd3100")
            echo "Running on DUAL ADSD3500 + ADSD3100"
            fetch_gpio_labels
            adsd3500_power_sequence
            echo "Self boot completed"
            ;;
        *)
            echo "Invalid camera module"
            exit 1
            ;;
    esac
}

main() {
    enable_self_boot
}

main
