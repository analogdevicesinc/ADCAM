#!/bin/bash

RESET_LOW="0"
RESET_HIGH="1"

run_reset_sequence() {
	GPIO_NAME="PAC.00"
	echo "$RESET_LOW" > /sys/class/gpio/$GPIO_NAME/value
	sleep 1
	echo "$RESET_HIGH" > /sys/class/gpio/$GPIO_NAME/value
}

run_reset_sequence_config3() {
	# TODO: reset sequence for ADSD3500/ADTF3066 + RGB is not yet defined.
	echo "Reset sequence for CONFIG 3 (ADSD3500/ADTF3066 + RGB) is not yet implemented. Skipping."
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
			echo "Skipping ADSD3500 reset: no matching module badge combination found"
			exit 0
			;;
		1|2)
			echo "Matched MODULE: $MODULE (CONFIG $CONFIG)"
			run_reset_sequence
			;;
		3)
			echo "Matched MODULE: $MODULE (CONFIG $CONFIG)"
			run_reset_sequence_config3
			;;
	esac
}

main

