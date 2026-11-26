#!/usr/bin/env python3
"""
Host-boot the ADSD3500 over the GMSL3 tunnel (MAX96723A/MAX96726A board):
hold the ToF ISP in reset and powered down, select host-boot mode on
GMSL_TOFISP_BS0, then re-power and release reset.

Mirrors adsd3500_gmsl_self_boot.py, differing only in GMSL_TOFISP_BS0's
level (HIGH = host boot, LOW = self boot).
"""

import os
import time

from smbus2 import SMBus

from config_1_max96723A_max96726A_init import (
    SERIALIZER_ADDR_CANDIDATES,
    _detect_serializer_addr,
    set_serializer_gpio_output,
    get_serializer_gpio_output,
)

# Bump on every edit - logged on every run so a stale copy on the target is obvious.
SCRIPT_VERSION = "2026-11-26.1"

LOW = 0
HIGH = 1

I2C_BUS_NUM = 2

# Jetson GPIO wired to deserializer MFP10, tunneled to serializer
# GMSL_TOFISP_RST_L (tunnel "mfp1" in config_1_max96723A_max96726A_init.py).
TOFISP_RST_L_GPIO = "PP.01"
TOFISP_RST_L_EXPORT_GPIO_NUM = "605"


def export_and_configure_gpio(gpio_dir_name, export_gpio_num):
    gpio_path = "/sys/class/gpio/{}".format(gpio_dir_name)

    if not os.path.isdir(gpio_path):
        with open("/sys/class/gpio/export", "w") as f:
            f.write(export_gpio_num)

        # udev needs a brief moment after export to finish setting up direction/value
        # (sysfs GPIO export race) - retry with a short backoff instead of failing on
        # the very first open()
        direction_path = os.path.join(gpio_path, "direction")
        last_exc = None
        for _ in range(20):
            try:
                with open(direction_path, "w") as f:
                    f.write("out")
                break
            except PermissionError as exc:
                last_exc = exc
                time.sleep(0.05)
        else:
            raise last_exc


def write_gpio_value(gpio_number, value):
    gpio_path = "/sys/class/gpio/{}/value".format(gpio_number)
    with open(gpio_path, "w") as f:
        f.write(str(value))


def read_gpio_value(gpio_number):
    """Read back a sysfs GPIO's current value (0/1); mirrors write_gpio_value()."""
    gpio_path = "/sys/class/gpio/{}/value".format(gpio_number)
    with open(gpio_path, "r") as f:
        return int(f.read().strip())


def run_adsd3500_gmsl_host_boot_sequence():
    """Assumes the GMSL link + ADSD3500/ISP power rails are already up
    (config_1_max96723A_max96726A_init.py's full bring-up already ran) -
    this only re-sequences the ToF ISP reset/enable/boot-mode GPIOs to
    make the ADSD3500 host-boot instead of self-boot."""
    export_and_configure_gpio(TOFISP_RST_L_GPIO, TOFISP_RST_L_EXPORT_GPIO_NUM)

    with SMBus(I2C_BUS_NUM) as bus:
        serializer_addr = _detect_serializer_addr(bus, SERIALIZER_ADDR_CANDIDATES)

        print("Asserting TOFISP_RST_L ({})...".format(TOFISP_RST_L_GPIO))
        write_gpio_value(TOFISP_RST_L_GPIO, LOW)

        print("Disabling GMSL_EN_TOFISP...")
        set_serializer_gpio_output(bus, serializer_addr, "GMSL_EN_TOFISP", LOW)

        print("Disabling GMSL_EN_TOF...")
        set_serializer_gpio_output(bus, serializer_addr, "GMSL_EN_TOF", LOW)

        print("Selecting host-boot mode: GMSL_TOFISP_BS0 = HIGH...")
        set_serializer_gpio_output(bus, serializer_addr, "GMSL_TOFISP_BS0", HIGH)

        # EN_TOFISP = 1 (15ms settle required beforehand)
        time.sleep(0.015)
        print("Enabling GMSL_EN_TOFISP...")
        set_serializer_gpio_output(bus, serializer_addr, "GMSL_EN_TOFISP", HIGH)

        # EN_TOF = 1 (5ms settle required beforehand)
        time.sleep(0.005)
        print("Enabling GMSL_EN_TOF...")
        set_serializer_gpio_output(bus, serializer_addr, "GMSL_EN_TOF", HIGH)

        # TOFISP_RST_L = 1, then settle 3ms before ADSD3500 access
        print("Releasing TOFISP_RST_L ({})...".format(TOFISP_RST_L_GPIO))
        write_gpio_value(TOFISP_RST_L_GPIO, HIGH)
        time.sleep(0.003)

        for name in ("GMSL_EN_TOFISP", "GMSL_TOFISP_BS0", "GMSL_EN_TOF"):
            value = get_serializer_gpio_output(bus, serializer_addr, name)
            print("{} = {}".format(name, "HIGH" if value else "LOW"))

    print("TOFISP_RST_L ({}) = {}".format(
        TOFISP_RST_L_GPIO, read_gpio_value(TOFISP_RST_L_GPIO)))
    print("ADSD3500 GMSL host-boot sequence completed.")


if __name__ == "__main__":
    print("adsd3500_gmsl_host_boot.py version {}".format(SCRIPT_VERSION))
    run_adsd3500_gmsl_host_boot_sequence()
