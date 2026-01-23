#!/bin/bash

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
    echo "Target module not found"
    exit 0
fi

echo "Matched MODULE: $MODULE"

MEDIA_DEVICE="/dev/media0"
DOT_OUTPUT=$(media-ctl -d "$MEDIA_DEVICE" --print-dot)
DOT_OUTPUT=$(echo "$DOT_OUTPUT" | sed 's/\\n/\n/g')
SUBDEV_PATH=$(echo "$DOT_OUTPUT" | awk '/adsd3500/ {getline; if ($0 ~ /\/dev\/v4l-subdev/) print $1}' | tr -d '",')
VIDEO_PATH=$(echo "$DOT_OUTPUT" | awk '/vi-output, adsd3500/ {getline; if ($0 ~ /\/dev\/video/) print $1}' | tr -d '",')

if [[ -n "$SUBDEV_PATH" && -n "$VIDEO_PATH" ]]; then
    echo "adsd3500 subdev: $SUBDEV_PATH" > /dev/null
    echo "adsd3500 video : $VIDEO_PATH"  > /dev/null
else
    echo "adsd3500 device not found in $MEDIA_DEVICE"
    exit 1
fi

GPIO_NAME="PAC.00"

# Declare GPIO mapping directly
declare -A GPIO=(
    [EN_1P8]=300
    [EN_0P8]=301
    [P2]=302
    [I2CM_SEL]=303
    [ISP_BS3]=304
    [NET_HOST_IO_SEL]=305
    [ISP_BS0]=306
    [ISP_BS1]=307
    [HOST_IO_DIR]=308
    [ISP_BS4]=309
    [ISP_BS5]=310
    [FSYNC_DIR]=311
    [EN_VAUX]=312
    [EN_VAUX_LS]=313
    [EN_SYS]=314
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

enable_host_boot(){

	case $MODULE in
		"adi_dual_adsd3500_adsd3100")
			echo "Running on DUAL ADSD3500 + ADSD3100"
			adsd3500_power_sequence
			load_firmware
			echo "Host boot completed"
			;;
		*)
			echo "Invalid camera module"
			exit 1
			;;
	esac
}

main(){

	enable_host_boot
}

main
