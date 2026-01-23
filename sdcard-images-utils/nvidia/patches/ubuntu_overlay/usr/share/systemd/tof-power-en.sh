#!/bin/bash
# ToF sensor power/reset sequence using max7327 GPIOs via sysfs

# Scan all camera module badge entries and assign MODULE to the first one matching the ADI ToF sensor
TARGET="adi_dual_adsd3500_adsd3100"
MODULE=""

for badge in \
    /proc/device-tree/tegra-camera-platform/modules/module0/badge \
    /proc/device-tree/tegra-camera-platform/modules/module1/badge
do
    if [[ -f "$badge" ]]; then
        value=$(strings "$badge")
        if echo "$value" | grep -q "$TARGET"; then
            MODULE="$value"
            break
        fi
    fi
done

if [[ -z "$MODULE" ]]; then
    echo "Skipping ToF power sequence: MODULE=$MODULE"
    exit 0
fi

echo "Matched MODULE: $MODULE"

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

