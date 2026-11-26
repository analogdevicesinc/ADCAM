#!/bin/bash
# ToF sensor power/reset disable sequence using max7327 GPIOs via sysfs

# GPIO logic levels
GPIO_LOW=0
GPIO_HIGH=1

# Function to export and configure GPIO
setup_gpio() {
    local gpio=$1
    local direction=$2
    local value=${3:-0}

    [ ! -d /sys/class/gpio/gpio$gpio ] && echo "$gpio" > /sys/class/gpio/export
    echo "Waiting 0.05 second..."
    sleep 0.05
    echo "$direction" > /sys/class/gpio/gpio$gpio/direction
    [[ "$direction" == "out" ]] && echo "$value" > /sys/class/gpio/gpio$gpio/value
}

# Export + configure (as output) + drive a sysfs GPIO identified by its board pin label
set_named_gpio() {
    local gpio_name=$1
    local gpio_num=$2
    local gpio_value=$3
    local gpio_path="/sys/class/gpio/${gpio_name}"

    if [ ! -d "$gpio_path" ]; then
        echo "$gpio_num" > /sys/class/gpio/export
        echo "Waiting 1 second..."
        sleep 1
    fi
    [ "$(cat ${gpio_path}/direction 2>/dev/null)" != "out" ] && echo out > "${gpio_path}/direction"
    echo "$gpio_value" > "${gpio_path}/value"
}

# ToF power disable sequence for CONFIG 1 (ADSD3500 only) and CONFIG 2 (RGB + ADSD3500/ADSD3100)
run_tof_power_disable_sequence() {
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
            # Already exported/configured as output by tof-power-en.sh - don't redo it
            # (re-exporting an already-exported GPIO fails with "Device or resource busy").
            if [ ! -d /sys/class/gpio/$GPIO_NAME ]; then
                echo $gpio_num > /sys/class/gpio/export
                echo out > /sys/class/gpio/$GPIO_NAME/direction
            fi
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

    echo "Starting ToF power disable sequence..."

    # --- Step 1: Pull ADSD3500 reset low first (safe state) ---
    echo 0 > /sys/class/gpio/$GPIO_NAME/value

    # --- Step 2: Disable EN_VAUX, EN_VAUX_LS, EN_SYS (reverse of enable step 9) ---
    for pin in EN_VAUX EN_VAUX_LS EN_SYS; do
        echo 0 > /sys/class/gpio/gpio${GPIO[$pin]}/value
    done
    echo "Waiting 0.2 second..."
    sleep 0.2

    # --- Step 3: Disable EN_0P8, EN_1P8 (reverse of enable step 8) ---
    for pin in EN_0P8 EN_1P8; do
        echo 0 > /sys/class/gpio/gpio${GPIO[$pin]}/value
        echo "Waiting 0.2 second..."
        sleep 0.2
    done

    echo "ToF power disable sequence completed."
}

# GPIO names/numbers for CONFIG 3 (RGB + ADSD3500/ADTF3066) GMSL/POC power
GMSL_PWR_EN_GPIO_NAME="PAC.00"
GMSL_PWR_EN_GPIO_NUM="650"
POC_PWR_EN_GPIO_NAME="PH.06"
POC_PWR_EN_GPIO_NUM="561"

# ToF power disable sequence for CONFIG 3 (RGB + ADSD3500/ADTF3066): disable GMSL
# power (PAC.00) then POC power (PH.06), same order as
# GMSL3_SerDes_Bringup_V1.0/scripts/nv_power_disable.py.
run_tof_rgb_over_gmsl_power_disable_sequence() {
    echo "Disabling GMSL power (${GMSL_PWR_EN_GPIO_NAME})..."
    set_named_gpio "$GMSL_PWR_EN_GPIO_NAME" "$GMSL_PWR_EN_GPIO_NUM" $GPIO_LOW

    echo "Waiting 2 seconds..."
    sleep 2

    echo "Disabling POC power (${POC_PWR_EN_GPIO_NAME})..."
    set_named_gpio "$POC_PWR_EN_GPIO_NAME" "$POC_PWR_EN_GPIO_NUM" $GPIO_LOW

    echo "Waiting 2 seconds..."
    sleep 2

    echo "ToF+RGB over GMSL power disable sequence completed."
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
    #   CONFIG 3: RGB + ADSD3500/ADTF3066       -> module0=arducam_ar0234, module1=adi_adsd3500_adtf3066
    CONFIG=0
    MODULE=""

    if echo "$BADGE0" | grep -q "adi_dual_adsd3500_adsd3100"; then
        CONFIG=1
        MODULE="$BADGE0"
    elif echo "$BADGE0" | grep -q "arducam_ar0234" && echo "$BADGE1" | grep -q "adi_dual_adsd3500_adsd3100"; then
        CONFIG=2
        MODULE="$BADGE0 + $BADGE1"
    elif echo "$BADGE0" | grep -q "arducam_ar0234" && echo "$BADGE1" | grep -q "adi_adsd3500_adtf3066"; then
        CONFIG=3
        MODULE="$BADGE0 + $BADGE1"
    fi

    case "$CONFIG" in
        0)
            echo "Skipping ToF power disable sequence: no matching module badge combination found"
            exit 0
            ;;
        1|2)
            echo "Matched MODULE: $MODULE (CONFIG $CONFIG)"
            run_tof_power_disable_sequence
            ;;
        3)
            echo "Matched MODULE: $MODULE (CONFIG $CONFIG)"
            run_tof_rgb_over_gmsl_power_disable_sequence
            ;;
    esac
}

main
