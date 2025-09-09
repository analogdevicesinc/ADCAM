#!/bin/bash

MODULE=$(strings /proc/device-tree/tegra-camera-platform/modules/module0/badge)

if [[ $MODULE == "adi_adsd3500_adsd3100" ]]; then
	echo "Module name: $MODULE"
	echo "export CAM0_PWDN and set direction as output"

	# export ADSD3500 reset Pin
	if [ ! -d /sys/class/gpio/PH.06 ]
	then
	echo 397 > /sys/class/gpio/export
	echo out > /sys/class/gpio/PH.06/direction
	fi

	#pull ADSD3500 reset low
	sudo echo 0 > /sys/class/gpio/PH.06/value

	#Disable the supply voltage
	#EN_1P8
	sudo gpioset 3 6=0

	sleep 1

	#EN_0P8
	sudo gpioset 3 7=0

	# Boot strap MAX7321
	#OC0
	sudo gpioset 2 0=0

	#OC1
	sudo gpioset 2 1=0

	#OC2
	sudo gpioset 2 2=0

	#OC3
	sudo gpioset 2 3=0

	#OC4
	sudo gpioset 2 4=0

	#OC5
	sudo gpioset 2 5=0

	#OC6
	sudo gpioset 2 6=0

	#FLASH_WP
	sudo gpioset 2 7=1


	# Boot strap MAX7320
	#U0
	sudo gpioset 3 3=0

	#DS2
	sudo gpioset 3 5=1

	#EN_1P8
	sudo gpioset 3 6=1

	sleep 1

	#EN_0P8
	sudo gpioset 3 7=1

	#Pull ADSD3500 reset high
	sudo echo 1 > /sys/class/gpio/PH.06/value
	echo "ToF power sequence completed"
fi

if [[ $MODULE == "adi_dual_adsd3500_adsd3100" ]]; then
	echo "Module name: $MODULE"
	echo "export CAM0_PWDN and set direction as output"

	# export ADSD3500 reset Pin
	if [ ! -d /sys/class/gpio/PH.06 ]
	then
		echo 397 > /sys/class/gpio/export
		echo out > /sys/class/gpio/PH.06/direction
	fi

	# Export ISP_BS3/ISP_INT pin as input
	if [ ! -d /sys/class/gpio/gpio304 ]
	then
		echo 304 > /sys/class/gpio/export
		echo in > /sys/class/gpio/gpio304/direction
	fi

	# Export NET HOST_IO_SEL pin as output
	if [ ! -d /sys/class/gpio/gpio305 ]
	then
		echo 305 > /sys/class/gpio/export
		echo out > /sys/class/gpio/gpio305/direction
	fi

	# Export HOST_IO_DIR pin as output
	if [ ! -d /sys/class/gpio/gpio308 ]
	then
		echo 308 > /sys/class/gpio/export
		echo out > /sys/class/gpio/gpio308/direction
	fi

	# Export FSYNC_DIR pin as output
	if [ ! -d /sys/class/gpio/gpio311 ]
	then
		echo 311 > /sys/class/gpio/export
		echo out > /sys/class/gpio/gpio311/direction
	fi

	# Set NET HOST_IO_SEL: EXT_FSYNC = 0 / ISP_INT = 1
	echo 1 > /sys/class/gpio/gpio305/value

	#Set HOST_IO_DIR: EXT_FSYNC = 0 / ISP_INT = 1
	echo 1 > /sys/class/gpio/gpio308/value

	#Set FSYNC_DIR: External = 0 / Internal = 1
	echo 1 > /sys/class/gpio/gpio311/value

	#Pull ADSD3500 reset low
	sudo echo 0 > /sys/class/gpio/PH.06/value

	#Disable the the supply voltage
	#EN_1P8
	sudo gpioset 2 0=0

	#EN_0P8
	sudo gpioset 2 1=0

	sleep 1

	#I2CM_SET
	sudo gpioset 2 3=0

	#ISP_BS0
	sudo gpioset 2 6=0

	#ISP_BS1
	sudo gpioset 2 7=0

	#ISP_BS4
	sudo gpioset 2 9=0

	#ISP_BS5
	sudo gpioset 2 10=0

	#FSYNC_DIR
	sudo gpioset 2 11=1

	#EN_1P8
	sudo gpioset 2 0=1

	sleep 1

	#EN_0P8
	sudo gpioset 2 1=1

	sleep 1

	#EN_VSYS
	sudo gpioset 2 14=1

	#EN_VAUX_LS
	sudo gpioset 2 13=1

	#EN_VAUX
	sudo gpioset 2 12=1
	sleep 1

	#Pull ADSD3500 reset high
	sudo echo 1 > /sys/class/gpio/PH.06/value

	echo "ToF power sequence completed"
fi

