#!/bin/bash

MODULE=$(tr -d '\0' < /proc/device-tree/chosen/overlay-name 2>/dev/null)

adsd3500_power_sequence(){

    # GPIO numbers
    ISP_RST=603
    EN_1P8=623
    EN_0P8=624
    I2CM_SEL=626
    ISP_BS0=629
    ISP_BS1=630
    ISP_BS4=632
    ISP_BS5=633

    # Pull ADSD3500 reset low
    echo 0 > /sys/class/gpio/gpio${ISP_RST}/value

    # Disable the supply voltage
    # EN_1P8
    echo 0 > /sys/class/gpio/gpio${EN_1P8}/value

    # EN_0P8
    echo 0 > /sys/class/gpio/gpio${EN_0P8}/value

    sleep 0.2

    # I2CM_SEL
    echo 0 > /sys/class/gpio/gpio${I2CM_SEL}/value

    # ISP_BS0
    echo 1 > /sys/class/gpio/gpio${ISP_BS0}/value

    # ISP_BS1
    echo 0 > /sys/class/gpio/gpio${ISP_BS1}/value

    # ISP_BS4
    echo 0 > /sys/class/gpio/gpio${ISP_BS4}/value

    # ISP_BS5
    echo 0 > /sys/class/gpio/gpio${ISP_BS5}/value

    # EN_1P8
    echo 1 > /sys/class/gpio/gpio${EN_1P8}/value
    sleep 0.2

    # EN_0P8
    echo 1 > /sys/class/gpio/gpio${EN_0P8}/value
    sleep 0.2

    # Pull ADSD3500 reset high
    echo 1 > /sys/class/gpio/gpio${ISP_RST}/value
}

load_firmware() {

    VALUE=$(v4l2-ctl -d /dev/v4l-subdev2 --get-ctrl load_firmware)
    echo "The read value is $VALUE"

    if [ "$VALUE" = "load_firmware: 0" ]; then
        echo "Send host boot firmware to ADSD3500"
        v4l2-ctl -d /dev/v4l-subdev2 --set-ctrl load_firmware=1
        ret=$?
    elif [ "$VALUE" = "load_firmware: 1" ]; then
        echo "Send host boot firmware to ADSD3500"
        v4l2-ctl -d /dev/v4l-subdev2 --set-ctrl load_firmware=0
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
