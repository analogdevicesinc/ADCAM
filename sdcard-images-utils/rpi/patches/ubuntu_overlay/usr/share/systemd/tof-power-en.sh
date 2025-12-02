#!/bin/bash
#ToF sensor power/reset sequence using max7327 GPIOs via sysfs

# --- GPIO mapping ---
declare -A GPIO=(
    [ISP_RST]=603
    [EN_1P8]=623
    [EN_0P8]=624
    [P2]=625
    [I2CM_SEL]=626
    [ISP_BS3]=627
    [NET_HOST_IO_SEL]=628
    [ISP_BS0]=629
    [ISP_BS1]=630
    [HOST_IO_DIR]=631
    [ISP_BS4]=632
    [ISP_BS5]=633
    [FSYNC_DIR]=634
    [EN_VAUX]=635
    [EN_VAUX_LS]=636
    [EN_SYS]=637
)

# --- GPIO list for export ---
GPIO_LIST=(603 623 624 625 626 627 628 629 630 631 632 633 634 635 636 637)

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
for gpio in "${GPIO_LIST[@]}"; do
    if [ "$gpio" -eq "${GPIO[ISP_BS3]}" ]; then
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
echo 0 > /sys/class/gpio/gpio${GPIO[ISP_RST]}/value

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
echo 1 > /sys/class/gpio/gpio${GPIO[ISP_RST]}/value

echo "ToF power sequence completed."

