#!/bin/bash

ISP_RST=gpio603

echo 0 > /sys/class/gpio/$ISP_RST/value

sleep 1

echo 1 > /sys/class/gpio/$ISP_RST/value

