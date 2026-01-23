#!/bin/bash

GPIO_NAME="PAC.00"

echo 0 > /sys/class/gpio/$GPIO_NAME/value

sleep 1

echo 1 > /sys/class/gpio/$GPIO_NAME/value

