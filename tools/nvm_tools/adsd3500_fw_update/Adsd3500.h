/****************************************************************************
# Copyright (c) 2024 - Analog Devices Inc. All Rights Reserved.
# This software is proprietary & confidential to Analog Devices, Inc.
# and its licensors.
# *****************************************************************************
# *****************************************************************************/

#ifndef FIRMWARE_UPDATE_ADSD3500_H
#define FIRMWARE_UPDATE_ADSD3500_H


#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <getopt.h> /* getopt_long() */

#include <fcntl.h> /* low-level i/o */
#include <malloc.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/types.h>
#include <unistd.h>
#include <errno.h>

#include <asm/types.h> /* for videodev2.h */

#include <linux/videodev2.h>

#include <cstdint>
#include <memory>
#include <string>
#include <iostream>

using namespace std;

bool validate_ext(std::string FileName, std::string Target);

class Adsd3500 {
	public:
		Adsd3500(std::string FileName, std::string Target);

	private:
		int xioctl(int fd, int request, void* arg);

		bool findDevicePathsAtVideo(const std::string &video, std::string &subdev_path, std::string &device_name);

		void open_device();

		void reverse(char *temp);

		int generate_mirror(int ch);

		bool Switch_from_Standard_to_Burst();

		bool Switch_from_Burst_to_Standard();

		bool Current_Firmware_Version(uint8_t cmd);

		bool Read_Chip_ID(uint16_t reg_addr);

		bool updateAdsd3500MasterFirmware(const std::string &filePath);

		bool updateAdsd3500SlaveFirmware(const std::string &filePath);

		bool write_cmd(uint16_t cmd, uint16_t data);

		bool write_payload(uint8_t *payload, uint16_t payload_len);

		bool read_cmd(uint16_t cmd, uint16_t *data);

		bool read_burst_cmd(uint8_t *payload, uint16_t payload_len, uint8_t *data);

		std::string video = "/dev/media0";
		std::string deviceName = "adsd3500";
		std::string subdevPath;
		int sfd = -1;
};


#endif //FIRMWARE_UPDATE_ADSD3500_H
