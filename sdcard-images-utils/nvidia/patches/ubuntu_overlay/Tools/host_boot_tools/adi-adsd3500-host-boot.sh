#!/bin/bash

MEDIA_DEVICE="/dev/media0"

discover_adsd3500_nodes() {
    DOT_OUTPUT=$(media-ctl -d "$MEDIA_DEVICE" --print-dot)
    DOT_OUTPUT=$(echo "$DOT_OUTPUT" | sed 's/\\n/\n/g')
    SUBDEV_PATH=$(echo "$DOT_OUTPUT" | awk '/adsd3500/ {getline; if ($0 ~ /\/dev\/v4l-subdev/) print $1}' | tr -d '\",')
    VIDEO_PATH=$(echo "$DOT_OUTPUT" | awk '/vi-output, adsd3500/ {getline; if ($0 ~ /\/dev\/video/) print $1}' | tr -d '\",')

    if [[ -z "$SUBDEV_PATH" || -z "$VIDEO_PATH" ]]; then
        echo "adsd3500 device not found in $MEDIA_DEVICE"
        exit 1
    fi
}

GPIO_NAME="PAC.00"

# Fixed GPIO mapping from gpiochip2 (max7327)
declare -A GPIO=(
    [EN_1P8]=708
    [EN_0P8]=709
    [P2]=710
    [I2CM_SEL]=711
    [ISP_BS3]=712
    [NET_HOST_IO_SEL]=713
    [ISP_BS0]=714
    [ISP_BS1]=715
    [HOST_IO_DIR]=716
    [ISP_BS4]=717
    [ISP_BS5]=718
    [FSYNC_DIR]=719
    [EN_VAUX]=720
    [EN_VAUX_LS]=721
    [EN_SYS]=722
)

adsd3500_power_sequence() {

    # Pull ADSD3500 reset low
    echo 0 > /sys/class/gpio/$GPIO_NAME/value

    # Disable the supply voltage
    echo 0 > /sys/class/gpio/gpio${GPIO[EN_1P8]}/value
    echo 0 > /sys/class/gpio/gpio${GPIO[EN_0P8]}/value

    sleep 0.2

    # I2CM_SEL
    echo 0 > /sys/class/gpio/gpio${GPIO[I2CM_SEL]}/value

    # ISP_BS0
    echo 1 > /sys/class/gpio/gpio${GPIO[ISP_BS0]}/value

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
    echo 1 > /sys/class/gpio/$GPIO_NAME/value
}

load_firmware() {

    VALUE=$(v4l2-ctl -d $SUBDEV_PATH --get-ctrl load_firmware)
    echo "The read value is $VALUE"

    if [ "$VALUE" = "load_firmware: 0" ]; then
        echo "Send host boot firmware to ADSD3500"
        v4l2-ctl -d $SUBDEV_PATH --set-ctrl load_firmware=1
        ret=$?
    elif [ "$VALUE" = "load_firmware: 1" ]; then
        echo "Send host boot firmware to ADSD3500"
        v4l2-ctl -d $SUBDEV_PATH --set-ctrl load_firmware=0
        ret=$?
    else
        echo "Unexpected value: $VALUE"
        exit 1
    fi

    if [ $ret -eq 0 ]; then
        echo "Firmware load command succeeded."
    else
        echo "Firmware load command FAILED. Return code: $ret"
        exit 1
    fi
}

run_host_boot_sequence() {
    adsd3500_power_sequence
    load_firmware
    echo "Host boot completed"
}

run_host_boot_sequence_config3() {
    # TODO: host boot sequence for ADSD3500/ADTF3066 + RGB is not yet defined.
    echo "Host boot sequence for CONFIG 3 (ADSD3500/ADTF3066 + RGB) is not yet implemented. Skipping."
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
            echo "Skipping host boot: no matching module badge combination found"
            exit 0
            ;;
        1|2)
            echo "Matched MODULE: $MODULE (CONFIG $CONFIG)"
            discover_adsd3500_nodes
            run_host_boot_sequence
            ;;
        3)
            echo "Matched MODULE: $MODULE (CONFIG $CONFIG)"
            run_host_boot_sequence_config3
            ;;
    esac
}

main
