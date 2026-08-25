#!/bin/bash

# Fixed GPIO mapping from gpiochip2 (max7327)
NET_HOST_IO_SEL_GPIO="713"
HOST_IO_DIR_GPIO="716"
LOW_LEVEL="0"
MODE_EXT_FSYNC="0"
MEDIA_DEVICE="/dev/media0"

discover_adsd3500_nodes() {
    DOT_OUTPUT=$(media-ctl -d "$MEDIA_DEVICE" --print-dot)
    DOT_OUTPUT=$(echo "$DOT_OUTPUT" | sed 's/\\n/\n/g')
    SUBDEV_PATH=$(echo "$DOT_OUTPUT" | awk '/adsd3500/ {getline; if ($0 ~ /\/dev\/v4l-subdev/) print $1}' | tr -d '",')
    VIDEO_PATH=$(echo "$DOT_OUTPUT" | awk '/vi-output, adsd3500/ {getline; if ($0 ~ /\/dev\/video/) print $1}' | tr -d '",')

    if [[ -z "$SUBDEV_PATH" || -z "$VIDEO_PATH" ]]; then
        echo "adsd3500 device not found in $MEDIA_DEVICE"
        exit 1
    fi
}

run_external_fsync_sequence() {
    # Set 0: EXT_FSYNC / 1: ISP_INT
    echo "$LOW_LEVEL" > "/sys/class/gpio/gpio${NET_HOST_IO_SEL_GPIO}/value"

    # Set 0: EXT_FSYNC / 1: ISP_INT
    echo "$LOW_LEVEL" > "/sys/class/gpio/gpio${HOST_IO_DIR_GPIO}/value"

    # Enable external fsync
    v4l2-ctl --set-ctrl="fsync_trigger=${MODE_EXT_FSYNC}" -d "$SUBDEV_PATH"
}

run_external_fsync_sequence_config3() {
    # TODO: external fsync sequence for ADSD3500/ADTF3066 + RGB is not yet defined.
    echo "External fsync sequence for CONFIG 3 (ADSD3500/ADTF3066 + RGB) is not yet implemented. Skipping."
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
            echo "Skipping external fsync: no matching module badge combination found"
            exit 0
            ;;
        1|2)
            echo "Matched MODULE: $MODULE (CONFIG $CONFIG)"
            discover_adsd3500_nodes
            run_external_fsync_sequence
            ;;
        3)
            echo "Matched MODULE: $MODULE (CONFIG $CONFIG)"
            run_external_fsync_sequence_config3
            ;;
    esac
}

main
