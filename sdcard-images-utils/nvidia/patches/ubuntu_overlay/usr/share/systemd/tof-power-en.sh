#!/bin/bash
# ToF sensor power/reset sequence using max7327 GPIOs via sysfs

# Function to export and configure GPIO
setup_gpio() {
    local gpio=$1
    local direction=$2
    local value=${3:-0}

    [ ! -d /sys/class/gpio/gpio$gpio ] && echo "$gpio" > /sys/class/gpio/export
    sleep 0.05
    echo "$direction" > /sys/class/gpio/gpio$gpio/direction
    [[ "$direction" == "out" ]] && echo "$value" > /sys/class/gpio/gpio$gpio/value
}

# ToF power sequence for CONFIG 1 (ADSD3500 only) and CONFIG 2 (RGB + ADSD3500/ADSD3100)
run_tof_power_sequence() {
    # --- Dynamically fetch GPIO labels ---
    declare -A GPIO

    # List of GPIO labels we are interested in, including ISP_RST at the start
    GPIO_LIST=("ISP_RST" "EN_1P8" "EN_0P8" "P2" "I2CM_SEL" "ISP_BS3" "NET_HOST_IO_SEL" "ISP_BS0" "ISP_BS1" "HOST_IO_DIR" "ISP_BS4" "ISP_BS5" "FSYNC_DIR" "EN_VAUX" "EN_VAUX_LS" "EN_SYS")

    # GPIO name to search for (easy to change later)
    GPIO_NAME="PAC.00"

    # Check for the GPIO name and assign it to ISP_RST
    GPIO_RESULT=$(sudo cat /sys/kernel/debug/gpio | grep -i "\b${GPIO_NAME}\b")
    if [[ -n "$GPIO_RESULT" ]]; then
        gpio_num=$(echo "$GPIO_RESULT" | sed -E 's/.*gpio-([0-9]+).*/\1/')
        if [[ -n "$gpio_num" ]]; then
            GPIO["ISP_RST"]=$gpio_num
            echo "Special case: ${GPIO_NAME} assigned to ISP_RST -> $gpio_num"
            echo $gpio_num > /sys/class/gpio/export
            echo out > /sys/class/gpio/$GPIO_NAME/direction
        else
            echo "${GPIO_NAME} found, but GPIO number not extracted correctly"
            exit 0
        fi
    else
        echo "${GPIO_NAME} not found"
        exit 0
    fi

    # Now process the GPIO labels, starting from the second element (index 1)
    for label in "${GPIO_LIST[@]:1}"; do
        # Search for each GPIO label in the debug output and extract the GPIO number
        result=$(sudo cat /sys/kernel/debug/gpio | grep -i "\b$label\b")

        # Check if the result is non-empty and contains the GPIO number
        if [[ -n "$result" ]]; then
            gpio_num=$(echo "$result" | sed -E 's/.*gpio-([0-9]+).*/\1/')

            # Store the GPIO number in the associative array
            if [[ -n "$gpio_num" ]]; then
                GPIO["$label"]=$gpio_num
                echo "Label: $label -> $gpio_num"
            else
                echo "Label: $label found, but GPIO number not extracted correctly"
                exit 0
            fi
        else
            echo "Label: $label not found"
            exit 0
        fi
    done

    echo "Configuring GPIOs via sysfs..."

    # Configure all GPIOs: ISP_BS3 as input, others as output low
    for label in "${GPIO_LIST[@]:1}"; do
        gpio=${GPIO[$label]}
        if [ "$label" == "ISP_BS3" ]; then
            setup_gpio "$gpio" "in"
        else
            setup_gpio "$gpio" "out" 0
        fi
    done

    echo "GPIO configuration complete."
    echo "Starting ToF power sequence..."

    # --- Step 1-3: Direction/selection lines ---
    echo 1 > /sys/class/gpio/gpio${GPIO[NET_HOST_IO_SEL]}/value
    echo 1 > /sys/class/gpio/gpio${GPIO[HOST_IO_DIR]}/value
    echo 1 > /sys/class/gpio/gpio${GPIO[FSYNC_DIR]}/value

    # --- Step 4: Pull ADSD3500 reset low ---
    echo 0 > /sys/class/gpio/$GPIO_NAME/value

    # --- Step 5: Disable supply voltages ---
    for pin in EN_1P8 EN_0P8; do
        echo 0 > /sys/class/gpio/gpio${GPIO[$pin]}/value
    done
    sleep 0.2

    # --- Step 6: I2CM_SEL low ---
    echo 0 > /sys/class/gpio/gpio${GPIO[I2CM_SEL]}/value

    # --- Step 7: ISP_BS0/1/4/5 low ---
    for pin in ISP_BS0 ISP_BS1 ISP_BS4 ISP_BS5; do
        echo 0 > /sys/class/gpio/gpio${GPIO[$pin]}/value
    done

    # --- Step 8: Enable supply voltages ---
    for pin in EN_1P8 EN_0P8; do
        echo 1 > /sys/class/gpio/gpio${GPIO[$pin]}/value
        sleep 0.2
    done

    # --- Step 9: Enable EN_SYS, EN_VAUX_LS, EN_VAUX ---
    for pin in EN_SYS EN_VAUX_LS EN_VAUX; do
        echo 1 > /sys/class/gpio/gpio${GPIO[$pin]}/value
    done
    sleep 0.2

    # --- Step 10: Pull ADSD3500 reset high ---
    echo 1 > /sys/class/gpio/$GPIO_NAME/value

    echo "ToF power sequence completed."
}

# ToF power sequence for CONFIG 3 (ADTF3066 + RGB)
run_tof_rgb_over_gmsl_power_sequence() {
    # TODO: power sequence for ADTF3066 + RGB is not yet defined.
    echo "Power sequence for CONFIG 3 (ADTF3066 + RGB) is not yet implemented. Skipping."
}

main() {
    BADGE0_PATH="/proc/device-tree/tegra-camera-platform/modules/module0/badge"
    BADGE1_PATH="/proc/device-tree/tegra-camera-platform/modules/module1/badge"

    BADGE0=""
    BADGE1=""
    [[ -f "$BADGE0_PATH" ]] && BADGE0=$(strings "$BADGE0_PATH")
    [[ -f "$BADGE1_PATH" ]] && BADGE1=$(strings "$BADGE1_PATH")

    # Identify the board configuration from module badges:
    #   CONFIG 1: Dual ADSD3500 only            -> module0=adi_dual_adsd3500_adsd3100
    #   CONFIG 2: RGB + Dual ADSD3500/ADSD3100  -> module0=arducam_ar0234, module1=adi_dual_adsd3500_adsd3100
    #   CONFIG 3: ADSD3500/ADTF3066 + RGB       -> module0=adi_adsd3500_adtf3066, module1=arducam_ar0234
    CONFIG=0
    MODULE=""

    if echo "$BADGE0" | grep -q "adi_dual_adsd3500_adsd3100"; then
        CONFIG=1
        MODULE="$BADGE0"
    elif echo "$BADGE0" | grep -q "arducam_ar0234" && echo "$BADGE1" | grep -q "adi_dual_adsd3500_adsd3100"; then
        CONFIG=2
        MODULE="$BADGE0 + $BADGE1"
    elif echo "$BADGE0" | grep -q "adi_adsd3500_adtf3066" && echo "$BADGE1" | grep -q "arducam_ar0234"; then
        CONFIG=3
        MODULE="$BADGE0 + $BADGE1"
    fi

    case "$CONFIG" in
        0)
            echo "Skipping ToF power sequence: no matching module badge combination found"
            exit 0
            ;;
        1|2)
            echo "Matched MODULE: $MODULE (CONFIG $CONFIG)"
            run_tof_power_sequence
            ;;
        3)
            echo "Matched MODULE: $MODULE (CONFIG $CONFIG)"
            run_tof_rgb_over_gmsl_power_sequence
            ;;
    esac
}

main

