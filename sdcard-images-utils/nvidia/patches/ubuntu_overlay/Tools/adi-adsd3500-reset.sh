#!/bin/bash

echo 0 > /sys/class/gpio/PAC.00/value

sleep 1

echo 1 > /sys/class/gpio/PAC.00/value

