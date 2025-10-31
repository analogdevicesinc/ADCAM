#!/bin/bash

MODULE=$(strings /proc/device-tree/tegra-camera-platform/modules/module0/badge)

adsd3500_power_sequence(){

	#Pull ADSD3500 reset low
	echo 0 > /sys/class/gpio/PAC.00/value

	#Disable the the supply voltage
	#EN_1P8
	gpioset 2 0=0

	#EN_0P8
	gpioset 2 1=0

	sleep 0.2

	#I2CM_SET
	gpioset 2 3=0

	#ISP_BS0
	gpioset 2 6=1

	#ISP_BS1
	gpioset 2 7=0

	#ISP_BS4
	gpioset 2 9=0

	#ISP_BS5
	gpioset 2 10=0

	#EN_1P8
	gpioset 2 0=1

	sleep 0.2

	#EN_0P8
	gpioset 2 1=1

	sleep 0.2

	#Pull ADSD3500 reset high
	echo 1 > /sys/class/gpio/PAC.00/value

}

load_firmware() {

    VALUE=$(v4l2-ctl -d /dev/v4l-subdev1 --get-ctrl load_firmware)
    echo "The read value is $VALUE"

    if [ "$VALUE" = "load_firmware: 0" ]; then
        echo "Send host boot firmware to ADSD3500"
        v4l2-ctl -d /dev/v4l-subdev1 --set-ctrl load_firmware=1
        ret=$?
    elif [ "$VALUE" = "load_firmware: 1" ]; then
        echo "Send host boot firmware to ADSD3500"
        v4l2-ctl -d /dev/v4l-subdev1 --set-ctrl load_firmware=0
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
