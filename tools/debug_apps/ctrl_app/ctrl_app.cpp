/****************************************************************************
# Copyright (c) 2024 - Analog Devices Inc. All Rights Reserved.
# This software is proprietary & confidential to Analog Devices, Inc.
# and its licensors.
# *****************************************************************************
# *****************************************************************************/

#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <array>

#include <cstring>
#include <errno.h>
#include <fcntl.h>
#include <linux/videodev2.h>
#include <malloc.h>
#include <stdbool.h>
#include <stdint.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include "../common/include/v4l2_common.h"

using namespace std;

#define IOCTL_TRIES 3
#define CLEAR(x) memset (&(x), 0, sizeof (x))
#define CTRL_SIZE 4099
#define VER_MAJ 1
#define VER_MIN 2
#define VER_PATCH 0


int main(int argc, char **argv) {
    uint8_t data[CTRL_SIZE] = {0};
    int status;

#if defined(NVIDIA) || defined(NXP)
    std::string video = "/dev/media0";
    std::string deviceName = "adsd3500";
    std::string subdevPath;

    status = findDevicePathsAtVideo(video, subdevPath, deviceName);
    if (!status) {
        std::cout << "failed to find device paths at video: " << video;
        return status;
    }

#elif defined(RPI)
    const std::string target = "adsd3500";
    std::string media_dev = find_media_device_with_entity(target);

    if (media_dev.empty()) {
	    std::cout << "ADSD3500 not found in /dev/media0..media3" << std::endl;
	    return 1;
    }

    std::string subdevPath = find_subdev_in_media(media_dev, target);

    if (subdevPath.empty()) {
	    std::cout << "Could not find ADSD3500 v4l-subdev node" << std::endl;
	    return 1;
    }

#else
    #error "Unsupported platform: define NVIDIA, NXP, or RPI"
#endif

    int fd = open(subdevPath.c_str(), O_RDWR | O_NONBLOCK);
    if (fd == -1) {
        std::cout << "Failed to open the camera" << std::endl;
        return -1;
    }

    std::ifstream infile(argv[1]);
    std::string line;

    if (!infile.is_open()) {
        std::cout << "File infile.txt not found\n";
        return -1;
    }

    printf("Burst Control app version: %d.%d.%d\n", VER_MAJ, VER_MIN,
           VER_PATCH);

    while (std::getline(infile, line)) {
        std::stringstream lineStream(line);
        std::string token;
        std::string r_w;
        int i = 0;
        lineStream >> r_w;
        while (lineStream >> token) {
            try {
                data[i + 3] = stoi(token, 0, 16);
            } catch (std::invalid_argument &e) {
            }
            i++;
            if (i > 4096) {
                std::cout << "Command line has to many bytes\n";
                return -1;
            }
        }

        data[0] = 1;
        data[1] = i >> 8;
        data[2] = i & 0xFF;

        v4l2_ctrl_set(fd, V4L2_CID_ADSD3500_DEV_CHIP_CONFIG, data);
        usleep(110 * 1000);
        if ((r_w == "R") && (i > 4)) {
            data[0] = 0;
            data[1] = data[4];
            data[2] = data[5];
            v4l2_ctrl_set(fd, V4L2_CID_ADSD3500_DEV_CHIP_CONFIG, data);
            usleep(110 * 1000);
            v4l2_ctrl_get(fd, V4L2_CID_ADSD3500_DEV_CHIP_CONFIG, data);

            int read_len = (data[1] << 8) | data[2];
            for (int j = 0; j < read_len; j++)
                printf("%02X ", data[j + 3]);
            printf("\n");
        } else if ((r_w == "R") && ((i == 2) || (i == 4))) {
            data[0] = 0;
            data[1] = 0;
            data[2] = 2;
            v4l2_ctrl_set(fd, V4L2_CID_ADSD3500_DEV_CHIP_CONFIG, data);
            usleep(110 * 1000);
            v4l2_ctrl_get(fd, V4L2_CID_ADSD3500_DEV_CHIP_CONFIG, data);

            int read_len = 2;

            for (int j = 0; j < read_len; j++)
                printf("%02X ", data[j + 3]);
            printf("\n");
        }
    }

    return 0;
}
