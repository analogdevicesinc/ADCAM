/****************************************************************************
# Copyright (c) 2024 - Analog Devices Inc. All Rights Reserved.
# This software is proprietary & confidential to Analog Devices, Inc.
# and its licensors.
# *****************************************************************************
# *****************************************************************************/

#include "Adsd3500.h"
#include "compute_crc.h"
#include <array>
#include <fstream>
#include <iostream>
#include <signal.h>
#include <stdlib.h>
#include <thread>
#include <vector>

#define FLASH_PAGE_SIZE 256
#define ADSD3500_CTRL_PACKET_SIZE 4099
#define WRITE_MASTER_FIRMWARE_COMMAND 0x04
#define WRITE_SLAVE_FIRMWARE_COMMAND 0x2A
#define GET_MASTER_FIRMWARE_COMMAND 0x01
#define GET_SLAVE_FIRMWARE_COMMAND 0x04
#define ADI_STATUS_FIRMWARE_UPDATE 0x000E
#define SET_SWITCH_TO_BURST_MODE 0x0019
#define GET_IMAGER_STATUS_CMD 0x0020
#define RESET_ADSD3500_CMD 0x0024
#define ADI_STATUS_SECOND_FIRMWARE_FLASH_UPDATE 0x0027
#define GET_MASTER_CHIP_ID_CMD 0x0112
#define GET_SLAVE_CHIP_ID_CMD 0x0116
#define USER_TASK _IOW('A', 1, int32_t *)
#define SIGETX 44

#ifdef NVIDIA
#define V4L2_CID_ADSD3500_DEV_CHIP_CONFIG (0x009819d1)
const char *debugfs_name = "/proc/adsd3500/value";
#endif

#ifdef NXP
#define V4L2_CID_ADSD3500_DEV_CHIP_CONFIG (0x009819e1)
const char *debugfs_name = "/sys/kernel/debug/adsd3500/value";
#endif

#ifdef RPI
#define V4L2_CID_ADSD3500_DEV_CHIP_CONFIG (0x009819d1)
const char *debugfs_name = "/proc/adsd3500/value";
#endif

/* Seed value for CRC computation */
#define ADI_ROM_CFG_CRC_SEED_VALUE (0xFFFFFFFFu)

/* CRC32 Polynomial to be used for CRC computation */
#define ADI_ROM_CFG_CRC_POLYNOMIAL (0x04C11DB7u)

typedef union {
    uint8_t cmd_header_byte[16];
    struct __attribute__((__packed__)) {
        uint8_t id8;                // 0xAD
        uint16_t chunk_size16;      // 256 is flash page size
        uint8_t cmd8;               // 0x04 is the CMD for fw upgrade
        uint32_t total_size_fw32;   // 4 bytes (total size of firmware)
        uint32_t header_checksum32; // 4 bytes header checksum
        uint32_t crc_of_fw32;       // 4 bytes CRC of the Firmware Binary
    };
} cmd_header_t;

int debug_fd = -1;
static int handler_done = 0;
int signal_value = 0;
int Update_Complete = 0;

static uint32_t cal_crc32(uint32_t crc, unsigned char *buf, size_t len);
Adsd3500::Adsd3500(std::string FileName, std::string Target) {
    this->open_device();
    if (strcmp(Target.c_str(), "master") == 0) {
        this->updateAdsd3500MasterFirmware(FileName);
    } else if (strcmp(Target.c_str(), "slave") == 0) {
        this->updateAdsd3500SlaveFirmware(FileName);
    }
}

bool validate_ext(std::string FileName, std::string Target) {
    const char *dot = strrchr(FileName.c_str(), '.');
    if (!dot || dot == FileName.c_str()) {
        return false;
    }

    if (strcmp(Target.c_str(), "master") == 0) {
        return strcmp(dot, ".bin") == 0;
    } else if (strcmp(Target.c_str(), "slave") == 0) {
        return strcmp(dot, ".stream") == 0;
    }

    return false;
}

void ctrl_c_handler(int n, siginfo_t *info, void *unused) {
    if (n == SIGINT) {
        std::cout << "recieved ctrl-c" << std::endl;
        handler_done = 1;
    }
}

void sig_event_handler(int n, siginfo_t *info, void *unused) {
    if (n == SIGETX) {

        signal_value = info->si_int;
        /* std::cout << "Received signal from ADSD3500 kernel driver : Value =  " << signal_value << std::endl; */
        Update_Complete = 1;
    }
}

int Adsd3500::xioctl(int fd, int request, void *arg) {
    int r;

    do
        r = ioctl(fd, request, arg);
    while (-1 == r && EINTR == errno);

    return r;
}

std::string Adsd3500::find_media_device_with_entity(const std::string &entity_name)
{
    for (int i = 0; i <= 3; i++)
    {
        std::string media_dev = "/dev/media" + std::to_string(i);
        std::string cmd = "media-ctl -d " + media_dev + " --print-dot 2>/dev/null";

        std::array<char, 256> buffer{};
        std::string dot_output;

        FILE *pipe = popen(cmd.c_str(), "r");
        if (!pipe)
            continue;

        while (fgets(buffer.data(), buffer.size(), pipe))
            dot_output += buffer.data();

        pclose(pipe);

        if (dot_output.empty())
            continue;

        if (dot_output.find(entity_name) != std::string::npos)
            return media_dev;
    }

    return "";
}

std::string Adsd3500::find_subdev_in_media(const std::string &media_dev,
                                 const std::string &entity_name)
{
    std::string cmd = "media-ctl -d " + media_dev + " --print-dot 2>/dev/null";

    std::array<char, 256> buffer{};
    std::string dot;

    FILE *pipe = popen(cmd.c_str(), "r");
    if (!pipe)
        return "";

    while (fgets(buffer.data(), buffer.size(), pipe))
        dot += buffer.data();

    pclose(pipe);

    if (dot.empty())
        return "";

    size_t pos = dot.find(entity_name);
    if (pos == std::string::npos)
        return "";

    size_t dev_pos = dot.find("/dev/v4l-subdev", pos);
    if (dev_pos == std::string::npos)
        return "";

    size_t end = dot.find_first_of(" \"\n", dev_pos);
    return dot.substr(dev_pos, end - dev_pos);
}

bool Adsd3500::findDevicePathsAtVideo(const std::string &video,
                                      std::string &subdev_path,
                                      std::string &device_name) {

    char *buf;
    int size = 0;
    size_t pos;

    /* Run media-ctl to get the video processing pipes */
    char cmd[64];
    sprintf(cmd, "media-ctl -d %s --print-dot", video.c_str());
    FILE *fp = popen(cmd, "r");
    if (!fp) {
        std::cout << "Error running media-ctl";
        return false;
    }

    /* Read the media-ctl output stream */
    buf = (char *)malloc(128 * 1024);
    while (!feof(fp)) {
        auto sz = fread(&buf[size], 1, 1, fp);
        size++;
    }
    pclose(fp);
    buf[size] = '\0';

    /* Search command media-ctl for device/subdevice name */
    string str(buf);
    free(buf);

    if (str.find("adsd3500") != string::npos) {
        device_name = "adsd3500";
        pos = str.find("adsd3500");
        subdev_path = str.substr(pos + strlen("adsd3500") + 9,
                                 strlen("/dev/v4l-subdevX"));
    } else {
        return false;
    }
    return true;
}

void Adsd3500::open_device() {
    struct stat st;
    struct sigaction act;
    int32_t number;
    bool status = true;

#if defined(NVIDIA) || defined(NXP)
    status = findDevicePathsAtVideo(video, subdevPath, deviceName);
    if (!status) {
        std::cout << "failed to find device paths at video: " << video;
        return;
    }

#elif defined(RPI)
    const std::string target = "adsd3500";
    std::string media_dev = find_media_device_with_entity(target);

    if (media_dev.empty()) {
	    std::cout << "ADSD3500 not found in /dev/media0..media3" << std::endl;
	    exit(EXIT_FAILURE);
    }

    std::string subdevPath = find_subdev_in_media(media_dev, target);

    if (subdevPath.empty()) {
	    std::cout << "Could not find ADSD3500 v4l-subdev node" << std::endl;
	    exit(EXIT_FAILURE);
    }

#else
    #error "Unsupported platform: define NVIDIA, NXP, or RPI"
#endif

    /* Open V4L2 subdevice */
    if (stat(subdevPath.c_str(), &st) == -1) {
        fprintf(stderr, "1\n");
        return;
    }

    if (!S_ISCHR(st.st_mode)) {
        fprintf(stderr, "1\n");
        return;
    }

    sfd = open(subdevPath.c_str(), O_RDWR | O_NONBLOCK, 0);
    if (sfd == -1) {
        fprintf(stderr, "1\n");
        return;
    }

    /* install ctrl-c interrupt handler to cleanup at exit */
    sigemptyset(&act.sa_mask);
    act.sa_flags = (SA_SIGINFO | SA_RESETHAND);
    act.sa_sigaction = ctrl_c_handler;
    sigaction(SIGINT, &act, NULL);

    /* install custom signal handler */
    sigemptyset(&act.sa_mask);
    act.sa_flags = (SA_SIGINFO | SA_RESTART);
    act.sa_sigaction = sig_event_handler;
    sigaction(SIGETX, &act, NULL);

    std::cout << "Installed signal handler for SIGETX = " << SIGETX
              << std::endl;

    /* Open ADSD3500 debugfs */
    debug_fd = open(debugfs_name, O_RDWR);
    if (debug_fd < 0) {
        std::cout << "Failed to open the debug sysfs " << std::endl;
        exit(EXIT_FAILURE);
    }

    if (ioctl(debug_fd, USER_TASK, (int32_t *)&number)) {
        printf("Failed to send IOCTL\n");
        std::cout << "Failed to send the IOCTL call" << std::endl;
        close(debug_fd);
        close(sfd);
        exit(EXIT_FAILURE);
    }
}

bool Adsd3500::updateAdsd3500MasterFirmware(const std::string &filePath) {
    bool status = true;
    uint8_t Wait_Time = 0;
    uint16_t Status_Command;
    uint32_t nResidualCRC = ADI_ROM_CFG_CRC_SEED_VALUE;
    Read_Chip_ID(GET_MASTER_CHIP_ID_CMD);
    sleep(1);

    std::cout << std::dec;

    Switch_from_Standard_to_Burst();
    sleep(1);

    std::cout << std::endl;
    std::cout << "Before upgrading new firmware ";
    Current_Firmware_Version(GET_MASTER_FIRMWARE_COMMAND);
    sleep(1);

    // Read the firmware binary file
    std::ifstream fw_file(filePath, std::ios::binary);
    // copy all data into buffer
    std::vector<uint8_t> buffer(std::istreambuf_iterator<char>(fw_file), {});

    uint32_t fw_len = buffer.size();
    uint8_t *fw_content = buffer.data();
    char fw_data[fw_len] = {0};

    memcpy(fw_data, buffer.data(), buffer.size());

    cmd_header_t fw_upgrade_header;
    fw_upgrade_header.id8 = 0xAD;
    fw_upgrade_header.chunk_size16 = 0x0100; // 256=0x100
    fw_upgrade_header.cmd8 = WRITE_MASTER_FIRMWARE_COMMAND;
    fw_upgrade_header.total_size_fw32 = fw_len;
    fw_upgrade_header.header_checksum32 = 0;

    for (int i = 1; i < 8; i++) {
        fw_upgrade_header.header_checksum32 +=
            fw_upgrade_header.cmd_header_byte[i];
    }

    crc_parameters_t crc_params;
    crc_params.type = CRC_32bit;
    crc_params.polynomial.polynomial_crc32_bit = ADI_ROM_CFG_CRC_POLYNOMIAL;
    crc_params.initial_crc.crc_32bit = nResidualCRC;
    crc_params.crc_compute_flags = IS_CRC_MIRROR;

    crc_output_t res = compute_crc(&crc_params, buffer.data(), buffer.size());
    nResidualCRC = ~res.crc_32bit;

    fw_upgrade_header.crc_of_fw32 = (uint32_t)nResidualCRC;

    uint8_t *ptr = (uint8_t *)&fw_upgrade_header;

    status = write_payload(fw_upgrade_header.cmd_header_byte, 16);
    if (!status) {
        std::cout << std::endl;
        std::cerr << "Failed to send fw upgrade header" << std::endl;
        return status;
    }

    int packetsToSend;
    if ((fw_len % FLASH_PAGE_SIZE) != 0) {
        packetsToSend = (fw_len / FLASH_PAGE_SIZE + 1);
    } else {
        packetsToSend = (fw_len / FLASH_PAGE_SIZE);
    }

    uint8_t data_out[FLASH_PAGE_SIZE];

    std::cout << std::endl;
    std::cout << "Writing Firmware packets..." << std::endl;
    Update_Complete = 0;
    for (int i = 0; i < packetsToSend; i++) {
        int start = FLASH_PAGE_SIZE * i;
        int end = FLASH_PAGE_SIZE * (i + 1);

        for (int j = start; j < end; j++) {
            if (j < fw_len) {
                data_out[j - start] = fw_content[j];
            } else {
                data_out[j - start] = 0x00;
            }
        }
        status = write_payload(data_out, FLASH_PAGE_SIZE);

        if (!status) {
            std::cerr << "Failed to send packet number " << i << " out of "
                      << packetsToSend << " packets!" << std::endl;
            return status;
        }

        std::cout << "Packet number: " << i + 1 << " / " << packetsToSend
                  << '\r';
        fflush(stdout);
    }
    std::cout << std::endl;
    std::cout << std::endl;
    std::cout << "Adsd3500 firmware updated succesfully!" << std::endl;

    std::cout << std::endl;
    std::cout << "Waiting for the ADSD3500 kernel Driver signal " << std::endl;

    while (1) {
        if (Update_Complete != 0) {
            std::cout << "Received signal from ADSD3500 kernel driver"
                      << std::endl;
            break;
        }
        if (Wait_Time >= 30) {
            std::cout << "ADSD3500 kernel driver signal timeout occured"
                      << std::endl;
            status = read_cmd(GET_IMAGER_STATUS_CMD, &Status_Command);
            std::cout << std::hex;
            std::cout << "Get status Command " << Status_Command << std::endl;

            std::cout << "Firmware update failed" << std::endl;
            close(debug_fd);
            exit(EXIT_FAILURE);
        }
        Wait_Time++;
        sleep(1);
    }

    std::cout << std::endl;
    for (int i = 9; i >= 0; i--) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
        std::cout << "Waiting for " << i << " seconds" << '\r';
        fflush(stdout);
    }
    std::cout << std::endl;

    status = read_cmd(GET_IMAGER_STATUS_CMD, &Status_Command);
    std::cout << std::hex;
    std::cout << "Get status Command " << std::uppercase << Status_Command
              << std::endl;

    if (Status_Command != ADI_STATUS_FIRMWARE_UPDATE) {
        std::cout << "Firmware update failed" << std::endl;
        exit(EXIT_FAILURE);
    }

    sleep(2);

    /*Soft Reset the ADSD3500*/
    status = write_cmd(RESET_ADSD3500_CMD, 0x0000);
    if (!status) {
        std::cout << std::endl;
        std::cerr << "Failed to Soft Reset the ADSD3500!" << std::endl;
        return status;
    } else {
        std::cout << std::endl;
        std::cout << "Firmware soft resetting...";
    }

    std::cout << std::endl;
    for (int i = 9; i >= 0; i--) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
        std::cout << "Waiting for " << i << " seconds" << '\r';
        fflush(stdout);
    }
    std::cout << std::endl;

    Read_Chip_ID(GET_MASTER_CHIP_ID_CMD);
    sleep(1);

    Switch_from_Standard_to_Burst();
    sleep(1);

    std::cout << std::endl;
    std::cout << "After upgrading new firmware ";
    Current_Firmware_Version(GET_MASTER_FIRMWARE_COMMAND);
    sleep(1);

    Switch_from_Burst_to_Standard();
    sleep(1);

    Read_Chip_ID(GET_MASTER_CHIP_ID_CMD);

    close(debug_fd);
    close(sfd);

    return true;
}

bool Adsd3500::updateAdsd3500SlaveFirmware(const std::string &filePath) {

    bool status = true;
    uint8_t Wait_Time = 0;
    uint16_t Status_Command;
    uint32_t nResidualCRC = ADI_ROM_CFG_CRC_SEED_VALUE;

    Read_Chip_ID(GET_SLAVE_CHIP_ID_CMD);
    sleep(1);

    std::cout << std::dec;

    Switch_from_Standard_to_Burst();
    sleep(1);

    std::cout << std::endl;
    std::cout << "Before upgrading new firmware ";
    Current_Firmware_Version(GET_SLAVE_FIRMWARE_COMMAND);
    sleep(1);

    // Read the firmware binary file
    std::ifstream fw_file(filePath, std::ios::binary);
    // copy all data into buffer
    std::vector<uint8_t> buffer(std::istreambuf_iterator<char>(fw_file), {});

    uint32_t fw_len = buffer.size();
    uint8_t *fw_content = buffer.data();
    char fw_data[fw_len] = {0};

    memcpy(fw_data, buffer.data(), buffer.size());

    cmd_header_t fw_upgrade_header;
    fw_upgrade_header.id8 = 0xAD;
    fw_upgrade_header.chunk_size16 = 0x0100; // 256=0x100
    fw_upgrade_header.cmd8 = WRITE_SLAVE_FIRMWARE_COMMAND;
    fw_upgrade_header.total_size_fw32 = fw_len;
    fw_upgrade_header.header_checksum32 = 0;

    for (int i = 1; i < 8; i++) {
        fw_upgrade_header.header_checksum32 +=
            fw_upgrade_header.cmd_header_byte[i];
    }

    crc_parameters_t crc_params;
    crc_params.type = CRC_32bit;
    crc_params.polynomial.polynomial_crc32_bit = ADI_ROM_CFG_CRC_POLYNOMIAL;
    crc_params.initial_crc.crc_32bit = nResidualCRC;
    crc_params.crc_compute_flags = IS_CRC_MIRROR;

    crc_output_t res = compute_crc(&crc_params, buffer.data(), buffer.size());
    nResidualCRC = ~res.crc_32bit;

    fw_upgrade_header.crc_of_fw32 = (uint32_t)nResidualCRC;

    uint8_t *ptr = (uint8_t *)&fw_upgrade_header;

    status = write_payload(fw_upgrade_header.cmd_header_byte, 16);
    if (!status) {
        std::cout << std::endl;
        std::cerr << "Failed to send fw upgrade header" << std::endl;
        return status;
    }

    int packetsToSend;
    if ((fw_len % FLASH_PAGE_SIZE) != 0) {
        packetsToSend = (fw_len / FLASH_PAGE_SIZE + 1);
    } else {
        packetsToSend = (fw_len / FLASH_PAGE_SIZE);
    }

    uint8_t data_out[FLASH_PAGE_SIZE];

    std::cout << std::endl;
    std::cout << "Writing Firmware packets..." << std::endl;
    Update_Complete = 0;
    for (int i = 0; i < packetsToSend; i++) {
        int start = FLASH_PAGE_SIZE * i;
        int end = FLASH_PAGE_SIZE * (i + 1);

        for (int j = start; j < end; j++) {
            if (j < fw_len) {
                data_out[j - start] = fw_content[j];
            } else {
                data_out[j - start] = 0x00;
            }
        }
        status = write_payload(data_out, FLASH_PAGE_SIZE);

        if (!status) {
            std::cerr << "Failed to send packet number " << i << " out of "
                      << packetsToSend << " packets!" << std::endl;
            return status;
        }

        std::cout << "Packet number: " << i + 1 << " / " << packetsToSend
                  << '\r';
        fflush(stdout);
    }
    std::cout << std::endl;
    std::cout << std::endl;
    std::cout << "Adsd3500 firmware updated succesfully!" << std::endl;

    std::cout << std::endl;
    std::cout << "Waiting for the ADSD3500 kernel Driver signal " << std::endl;

    while (1) {
        if (Update_Complete != 0) {
            std::cout << "Received signal from ADSD3500 kernel driver"
                      << std::endl;
            break;
        }
        if (Wait_Time >= 30) {
            std::cout << "ADSD3500 kernel driver signal timeout occured"
                      << std::endl;
            status = read_cmd(0x0020, &Status_Command);
            std::cout << std::hex;
            std::cout << "Get status Command " << Status_Command << std::endl;

            std::cout << "Firmware update failed" << std::endl;
            close(debug_fd);
            exit(EXIT_FAILURE);
        }
        Wait_Time++;
        sleep(1);
    }

    //exit(0);
    sleep(2);

    Switch_from_Burst_to_Standard();
    sleep(1);

    status = read_cmd(GET_IMAGER_STATUS_CMD, &Status_Command);
    std::cout << std::hex;
    std::cout << "Get status Command " << std::uppercase << Status_Command
              << std::endl;

    if (Status_Command != ADI_STATUS_SECOND_FIRMWARE_FLASH_UPDATE) {
        std::cout << "Slave Firmware write failed" << std::endl;
    } else {
        std::cout << "Slave Firmware Flash write completed and is successful."
                  << std::endl;
    }

    /*Soft Reset the ADSD3500*/
    status = write_cmd(RESET_ADSD3500_CMD, 0x0000);
    if (!status) {
        std::cout << std::endl;
        std::cerr << "Failed to Soft Reset the ADSD3500!" << std::endl;
        return status;
    } else {
        std::cout << std::endl;
        std::cout << "Firmware soft resetting..." << std::endl;
    }

    std::cout << std::endl;
    for (int i = 9; i >= 0; i--) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
        std::cout << "Waiting for " << i << " seconds" << '\r';
        fflush(stdout);
    }
    std::cout << std::endl;

    Read_Chip_ID(GET_SLAVE_CHIP_ID_CMD);
    sleep(1);

    Switch_from_Standard_to_Burst();
    sleep(1);

    std::cout << std::endl;
    std::cout << "After upgrading new firmware ";
    Current_Firmware_Version(GET_SLAVE_FIRMWARE_COMMAND);
    sleep(1);

    Switch_from_Burst_to_Standard();
    sleep(1);

    Read_Chip_ID(GET_SLAVE_CHIP_ID_CMD);

    close(debug_fd);
    close(sfd);

    return true;
}

bool Adsd3500::Read_Chip_ID(uint16_t reg_addr) {
    bool status = true;
    // Read Chip ID in STANDARD mode
    uint16_t chip_id;
    status = read_cmd(reg_addr, &chip_id);
    if (!status) {
        std::cout << std::endl;
        std::cerr << "Failed to read adsd3500 chip id!" << std::endl;
        return status;
    }

    std::cout << std::endl;
    std::cout << "Chip ID is: " << std::hex << chip_id << std::endl;
    return status;
}

bool Adsd3500::Switch_from_Standard_to_Burst() {
    bool status = true;

    // Switch to BURST mode.
    status = write_cmd(SET_SWITCH_TO_BURST_MODE, 0x0000);
    if (!status) {
        std::cout << std::endl;
        std::cerr << "Failed to switch to burst mode!" << std::endl;
        return status;
    } else {
        std::cout << std::endl;
        std::cout << "Switched from standard mode to burst mode" << std::endl;
    }
    return status;
}
bool Adsd3500::Switch_from_Burst_to_Standard() {

    bool status = true;
    /*Commands to switch back to standard mode*/
    uint8_t switchBuf[] = {0xAD, 0x00, 0x00, 0x10, 0x00, 0x00, 0x00, 0x00,
                           0x10, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};
    status = write_payload(switchBuf, sizeof(switchBuf) / sizeof(switchBuf[0]));
    if (!status) {
        std::cout << std::endl;
        std::cerr << "Failed to switch adsd3500 to standard mode!" << std::endl;
        return status;
    } else {
        std::cout << std::endl;
        std::cout << "Switched from burst mode to standard mode" << std::endl;
    }
    return status;
}
bool Adsd3500::Current_Firmware_Version(uint8_t cmd) {

    bool status = true;
    uint8_t Current_FW_Version[44] = {0};
    char version[16];

    // Read Current Firmware version
    uint8_t current_fw_version_command[] = {0xAD, 0x00, 0x2C, 0x05, 0x00, 0x00,
                                            0x00, 0x00, 0x31, 0x00, 0x00, 0x00,
                                            0x01, 0x00, 0x00, 0x00};
    current_fw_version_command[12] = cmd;
    status = read_burst_cmd(current_fw_version_command,
                            sizeof(current_fw_version_command) /
                                sizeof(current_fw_version_command[0]),
                            Current_FW_Version);

    snprintf(version, sizeof(version), "%d.%d.%d.%d", Current_FW_Version[0],
             Current_FW_Version[1], Current_FW_Version[2],
             Current_FW_Version[3]);
    std::cout << "Current firmware version is : " << version << std::endl;

    if (!status) {
        std::cout << std::endl;
        std::cerr << "Failed to Read Current Firmware" << std::endl;
        return status;
    }
    return status;
}

bool Adsd3500::write_cmd(uint16_t cmd, uint16_t data) {
    bool status = true;

    static struct v4l2_ext_control extCtrl;
    static struct v4l2_ext_controls extCtrls;
    static uint8_t buf[ADSD3500_CTRL_PACKET_SIZE];

    extCtrl.size = ADSD3500_CTRL_PACKET_SIZE;
    extCtrl.id = V4L2_CID_ADSD3500_DEV_CHIP_CONFIG;
    memset(&extCtrls, 0, sizeof(struct v4l2_ext_controls));
    extCtrls.controls = &extCtrl;
    extCtrls.count = 1;

    buf[0] = 1;
    buf[1] = 0;
    buf[2] = 4;
    buf[3] = uint8_t(cmd >> 8);
    buf[4] = uint8_t(cmd & 0xFF);
    buf[5] = uint8_t(data >> 8);
    buf[6] = uint8_t(data & 0xFF);
    extCtrl.p_u8 = buf;

    if (xioctl(sfd, VIDIOC_S_EXT_CTRLS, &extCtrls) == -1) {
        fprintf(stderr, "Writing Adsd3500: %d error: %s\n", errno,
                strerror(errno));
        exit(EXIT_FAILURE);
    }
    return true;
}

bool Adsd3500::write_payload(uint8_t *payload, uint16_t payload_len) {
    bool status = true;

    static struct v4l2_ext_control extCtrl;
    static struct v4l2_ext_controls extCtrls;
    static uint8_t buf[ADSD3500_CTRL_PACKET_SIZE];

    extCtrl.size = ADSD3500_CTRL_PACKET_SIZE;
    extCtrl.id = V4L2_CID_ADSD3500_DEV_CHIP_CONFIG;
    memset(&extCtrls, 0, sizeof(struct v4l2_ext_controls));
    extCtrls.controls = &extCtrl;
    extCtrls.count = 1;

    buf[0] = 1;
    buf[1] = uint8_t(payload_len >> 8);
    buf[2] = uint8_t(payload_len & 0xFF);

    memcpy(buf + 3, payload, payload_len);
    extCtrl.p_u8 = buf;

    if (xioctl(sfd, VIDIOC_S_EXT_CTRLS, &extCtrls) == -1) {
        std::cout << "Writing Adsd3500 error "
                  << "errno: " << errno << " error: " << strerror(errno)
                  << std::endl;
        return false;
    }

    usleep(100 * 1000);

    return status;
}

bool Adsd3500::read_cmd(uint16_t cmd, uint16_t *data) {
    static struct v4l2_ext_control extCtrl;
    static struct v4l2_ext_controls extCtrls;
    static uint8_t buf[ADSD3500_CTRL_PACKET_SIZE];

    extCtrl.size = ADSD3500_CTRL_PACKET_SIZE;
    extCtrl.id = V4L2_CID_ADSD3500_DEV_CHIP_CONFIG;
    memset(&extCtrls, 0, sizeof(struct v4l2_ext_controls));
    extCtrls.controls = &extCtrl;
    extCtrls.count = 1;

    buf[0] = 1;
    buf[1] = 0;
    buf[2] = 2;
    buf[3] = uint8_t(cmd >> 8);
    buf[4] = uint8_t(cmd & 0xFF);
    extCtrl.p_u8 = buf;

    if (xioctl(sfd, VIDIOC_S_EXT_CTRLS, &extCtrls) == -1) {
        fprintf(stderr, "0. Reading Adsd3500: %d error: %s\n", errno,
                strerror(errno));
        return false;
    }

    buf[0] = 0;
    buf[1] = 0;
    buf[2] = 2;

    extCtrl.p_u8 = buf;

    // wait for the last frame processing time, needed for adsd3500
    usleep(double(1.0) / 30 * 1000000);

    if (xioctl(sfd, VIDIOC_S_EXT_CTRLS, &extCtrls) == -1) {
        fprintf(stderr, "1. Reading Adsd3500: %d error: %s\n", errno,
                strerror(errno));
        return false;
    }

    if (xioctl(sfd, VIDIOC_G_EXT_CTRLS, &extCtrls) == -1) {
        fprintf(stderr, "2. Reading Adsd3500: %d error: %s\n", errno,
                strerror(errno));
        return false;
    }

    *data = (uint16_t)(extCtrl.p_u8[3] << 8) + (uint16_t)(extCtrl.p_u8[4]);
    return true;
}

bool Adsd3500::read_burst_cmd(uint8_t *payload, uint16_t payload_len,
                              uint8_t *data) {
    static struct v4l2_ext_control extCtrl;
    static struct v4l2_ext_controls extCtrls;
    static uint8_t buf[ADSD3500_CTRL_PACKET_SIZE];

    extCtrl.size = ADSD3500_CTRL_PACKET_SIZE;
    extCtrl.id = V4L2_CID_ADSD3500_DEV_CHIP_CONFIG;
    memset(&extCtrls, 0, sizeof(struct v4l2_ext_controls));
    extCtrls.controls = &extCtrl;
    extCtrls.count = 1;

    buf[0] = 1;
    buf[1] = uint8_t(payload_len >> 8);
    buf[2] = uint8_t(payload_len & 0xFF);

    memcpy(buf + 3, payload, payload_len);
    extCtrl.p_u8 = buf;

    std::cout << std::dec;
    if (xioctl(sfd, VIDIOC_S_EXT_CTRLS, &extCtrls) == -1) {
        fprintf(stderr, "0. Reading Adsd3500: %d error: %s\n", errno,
                strerror(errno));
        return false;
    }

    buf[0] = 0;
    buf[1] = buf[4];
    buf[2] = buf[5];

    extCtrl.p_u8 = buf;

    // wait for the last frame processing time, needed for adsd3500
    usleep(double(1.0) / 30 * 1000000);

    if (xioctl(sfd, VIDIOC_S_EXT_CTRLS, &extCtrls) == -1) {
        fprintf(stderr, "1. Reading Adsd3500: %d error: %s\n", errno,
                strerror(errno));
        return false;
    }

    usleep(double(1.0) / 30 * 1000000);
    if (xioctl(sfd, VIDIOC_G_EXT_CTRLS, &extCtrls) == -1) {
        fprintf(stderr, "2. Reading Adsd3500: %d error: %s\n", errno,
                strerror(errno));
        return false;
    }

    for (int i = 0; i < 44; i++) {
        data[i] = extCtrl.p_u8[i + 3];
    }
    printf("\n");
    return true;
}
