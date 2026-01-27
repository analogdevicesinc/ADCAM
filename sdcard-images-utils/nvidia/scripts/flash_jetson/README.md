Jetson BSP Linux source:

https://developer.nvidia.com/embedded/jetson-linux-r3644

System Prerequisites:

Host PC : Ubuntu 20.04/22.04/24.04

Target  : Jetson Orin nano 8Gb SOM.

A. Flash procedure with only ext4 root partition:

Use flash_nvme.sh to flash external media connected to a frame grabber v2 carrier board with jetson orin nano SoM. This script uses the recovery initial ramdisk to do the flashing, and can flash external media using the same procedure. Because this script uses the kernel for flashing, it is generally faster and creates only one ext4 root partition.

1. Copy the flash_nvme.sh shell script to ADCAM/sdcard-images-utils/nvidia directory

2. Change the permission and execute the shell script.

                $ chmod +x flash_nvme.sh

                $ sudo ./flash_nvme.sh

