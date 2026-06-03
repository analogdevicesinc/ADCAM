/****************************************************************************
# Copyright (c) 2024 - Analog Devices Inc. All Rights Reserved.
# This software is proprietary & confidential to Analog Devices, Inc.
# and its licensors.
# *****************************************************************************
# *****************************************************************************/

#include <string>
#include <iostream>
#include <sstream>
#include <fstream>
#include <cstdio>

#include <array>
#include <fcntl.h>
#include <errno.h>
#include <unistd.h>
#include <stdint.h>
#include <malloc.h>
#include <cstring>
#include <stdbool.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <linux/videodev2.h>
#include "../common/include/v4l2_common.h"

using namespace std;

#define IOCTL_TRIES 1
#define CLEAR(x) memset (&(x), 0, sizeof (x))
#define BUF_SIZE 4096
#define CTRL_SIZE 4099




int main(int argc, char **argv)
{

	uint8_t data[CTRL_SIZE] = {0};
	char binbuff[BUF_SIZE] = {0};
	uint32_t chunkSize = 2048u;
	uint32_t sizeOfBinary = 0u;
	uint32_t checksum = 0u;
	uint32_t packetsNeeded = 0u;

	int fd;
	uint8_t *copy_buffer;
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

	fd = open(subdevPath.c_str(), O_RDWR | O_NONBLOCK);
	if (fd == -1)
	{
		std::cout << "Failed to open the camera" << std::endl;
		return -1;
	}

	std::ofstream fp(argv[1], std::ofstream::binary);
	if (!fp)
	{
		std::cout<<"Cannot open file!"<<std::endl;
		return 1;
	}
	
	//Find the binary file size
	fp.seekp(0, fp.beg);
        
	//Go to burst
	data[0] = 1; //WRITE
	data[2] = 4;
	data[3] = 0x00;
	data[4] = 0x19;
	data[5] = 0x00;
	data[6] = 0x00;
	v4l2_ctrl_set(fd, V4L2_CID_ADSD3500_DEV_CHIP_CONFIG, data);
        printf("\nIn burst mode currently \n");
	//Write header and readback response
	memset(data, 0x00, CTRL_SIZE);
    
	data[0] = 1; //WRITE
	data[2] = 16;
	
	data[3] = 0xAD;
	data[6] = 0x2C;
	data[11] = 0x2C;
        data[15] = 1;
	v4l2_ctrl_set(fd, V4L2_CID_ADSD3500_DEV_CHIP_CONFIG, data);
	
	sleep(1);
	data[0] = 0;

        data[2] = 16;
	v4l2_ctrl_set(fd, V4L2_CID_ADSD3500_DEV_CHIP_CONFIG, data);
	v4l2_ctrl_get(fd, V4L2_CID_ADSD3500_DEV_CHIP_CONFIG, data);
           uint8_t crc_complete = data[6];
        int wait_time = 0;
	while(crc_complete != 0x13 && wait_time!=4)
	{
		v4l2_ctrl_get(fd, V4L2_CID_ADSD3500_DEV_CHIP_CONFIG, data);
        crc_complete = data[6];
		wait_time++;
	}
        //printf("\n data = %x, %x\n", data[15], data[16]);
//exit(0);
	if(data[18] == 0x01)
	{
        printf("\nRequesting CCB Data Read ...\n");
memset(data, 0x00, CTRL_SIZE);
	data[0] = 1; //WRITE
	data[2] = 16;
	
	data[3] = 0xAD;
	data[6] = 0x13;
	data[11] = 0x13;
	data[15] = 1;
	v4l2_ctrl_set(fd, V4L2_CID_ADSD3500_DEV_CHIP_CONFIG, data);

	usleep(30);	

	data[0] = 0;
	data[2] = 16;
	v4l2_ctrl_set(fd, V4L2_CID_ADSD3500_DEV_CHIP_CONFIG, data);
        //for(int i =0; i < 5; i++)
        //{
        //}
	v4l2_ctrl_get(fd, V4L2_CID_ADSD3500_DEV_CHIP_CONFIG, data);
	
	std::cout<<"Done reading response header "<<std::endl;


	chunkSize = (data[5] << 8) | data[4];
	sizeOfBinary = (data[10] << 24) | (data[9] << 16) | (data[8] << 8) | data[7];
	copy_buffer = (uint8_t*)malloc(sizeOfBinary);

	for (uint32_t i=3; i<11; i++)
		checksum += data[i];
        sizeOfBinary = sizeOfBinary - 4;
	packetsNeeded = sizeOfBinary / chunkSize;
	uint32_t remBytes = sizeOfBinary % chunkSize;
	if (remBytes != 0)
	{
		packetsNeeded = packetsNeeded+1;
	}
        copy_buffer = (uint8_t*)malloc(packetsNeeded * chunkSize);
	std::cout<<"Size of Binary :: "<<sizeOfBinary<<std::endl;
	std::cout<<"ChunkSize :: "<<chunkSize<<std::endl;
	std::cout<<"Packets Needed: "<<packetsNeeded<<std::endl;

	
	for (uint8_t i=0; i<19; i++)
	{
		printf("0x%.2X\n", data[i]);
	}
        usleep(1000 * 60);
	for (uint32_t i=0; i<(packetsNeeded); i++)
	{
		data[0] = 0;
		data[1] = chunkSize >> 8;
		data[2] = chunkSize & 0xFF;
		
		usleep(1000 * 15);

		bool retval = v4l2_ctrl_set(fd, V4L2_CID_ADSD3500_DEV_CHIP_CONFIG, data);
		v4l2_ctrl_get(fd, V4L2_CID_ADSD3500_DEV_CHIP_CONFIG, data);
		if (retval == false)
		{
			return -1;
		}
		memcpy(copy_buffer+(i*chunkSize), &data[3], chunkSize);
		

		std::cout<<"Packet number : "<<i<<" / "<<packetsNeeded<<"--" <<(i+1)*chunkSize<<std::endl;
	}	std::cout<<"Binary size : "<<sizeOfBinary<<std::endl;
	std::cout<<std::endl;
	//std::cout<<"Binary size : "<<sizeOfBinary<<std::endl;
	std::cout<<std::endl;

	//Exit burst
	memset(data, 0x00, 16);
	data[0] = 1; //WRITE
	data[2] = 16;
	data[3] = 0xAD;
	data[6] = 0x10;
	data[11] = 0x10;
	v4l2_ctrl_set(fd, V4L2_CID_ADSD3500_DEV_CHIP_CONFIG, data);
        fp.write((char*)copy_buffer, sizeOfBinary);
	fp.close();

	}
	else{
        printf(" CRC Mismatch - Calculated CRC differs from File CRC !!\n");
	memset(data, 0x00, 16);
	data[0] = 1; //WRITE
	data[2] = 16;
	data[3] = 0xAD;
	data[6] = 0x10;
	data[11] = 0x10;
	v4l2_ctrl_set(fd, V4L2_CID_ADSD3500_DEV_CHIP_CONFIG, data); 
        
	}
	
return 0;
}
