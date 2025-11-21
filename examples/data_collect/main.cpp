/********************************************************************************/
/*                                                                              */
/* Copyright (c) 2020 Analog Devices, Inc. All Rights Reserved.                 */
/* This software is proprietary to Analog Devices, Inc. and its licensors.      */
/*                                                                              */
/********************************************************************************/

#include <aditof/camera.h>
#include <aditof/depth_sensor_interface.h>
#include <aditof/frame.h>
#include <aditof/frame_handler.h>
#include <aditof/system.h>
#include <aditof/version.h>
#include <aditof/version-kit.h>
#include <chrono>
#include <command_parser.h>
#include <ctime>
#include <fstream>

#ifdef USE_GLOG
#include <glog/logging.h>
#else
#include <aditof/log.h>
#include <cstring>
#define __STDC_FORMAT_MACROS 1
#include <inttypes.h>
#endif
#include <algorithm>
#include <iostream>
#include <map>
#include <string>
#include <thread>
#include <vector>

#ifdef _WIN32
#include <windows.h>
#else
#include <sys/stat.h>
#endif

enum : uint16_t {
    MAX_FILE_PATH_SIZE = 512,
};

using namespace aditof;

#ifdef _WIN32
int main(int argc, char *argv[]);
#endif

static const char kUsagePublic[] =
    R"(Data Collect.
    Usage:
      data_collect 
      data_collect [--f <folder>] [--fps <frame rate>] [--n <ncapture>] [--m <mode>] [--ccb FILE] [--ip <ip>] [--fw <firmware>] [--ic <imager-configuration>] [-scf <save-configuration-file>] [-lcf <load-configuration-file>]
      data_collect (-h | --help)

    Options:
      -h --help          Show this screen.
      --f <folder>       Output folder (max name 512) [default: ./]
      --fps <frame rate>   Frame rate in frames per second [default: 10]
      --n <ncapture>     Capture frame num. [default: 1]
      --m <mode>         Mode to capture data in. [default: 0]
      --ccb <FILE>       The path to store CCB content
      --ip <ip>          Camera IP
      --fw <firmware>    Adsd3500 fw file
      --ic <imager-configuration>   Select imager configuration: standard, standard-raw,
                         custom, custom-raw. By default is standard.
      --scf <save-configuration-file>    Save current configuration to json file
      --lcf <load-configuration-file>    Load configuration from json file

    Note: --m argument supports index (0, 1, etc.) 

    Valid mode (--m) options are:
        0: short-range native
        1: long-range native
        2: short-range Qnative
        3: long-range Qnative
        4: pcm-native
        5: long-range mixed
        6: short-range mixed
)";

int main(int argc, char *argv[]) {
    std::map<std::string, struct Argument> command_map = {
        {"-h", {"--help", false, "", "", false}},
        {"-f", {"--f", false, "", ".", true}},
        {"-fps", {"--fps", false, "", "10", true}},
        {"-n", {"--n", false, "", "1", true}},
        {"-m", {"--m", false, "", "0", true}},
        {"-ip", {"--ip", false, "", "", true}},
        {"-fw", {"--fw", false, "", "", true}},
        {"-ccb", {"--ccb", false, "", "", true}},
        {"-ic", {"--ic", false, "", "", true}},
        {"-scf", {"--scf", false, "", "", true}},
        {"-lcf", {"--lcf", false, "", "", true}}};

    CommandParser command;
    std::string arg_error;

    command.parseArguments(argc, argv, command_map);

    if (argc == 1) {
        std::cout << kUsagePublic << std::endl;
        return -1;
    }

    int result = command.checkArgumentExist(command_map, arg_error);
    if (result != 0) {
        LOG(ERROR) << "Argument " << arg_error << " doesn't exist! "
                   << "Please check help menu.";
        return -1;
    }

    result = command.helpMenu();
    if (result == 1) {
        std::cout << kUsagePublic << std::endl;
        return -1;
    } else if (result == -1) {
        LOG(ERROR) << "Usage of argument -h/--help"
                   << " is incorrect! Help argument should be used alone!";
        return -1;
    }

    result = command.checkValue(command_map, arg_error);
    if (result != 0) {
        LOG(ERROR) << "Argument: " << command_map[arg_error].long_option
                   << " doesn't have assigned or default value!";
        LOG(INFO) << kUsagePublic;
        return -1;
    }

    result = command.checkMandatoryArguments(command_map, arg_error);
    if (result != 0) {
        LOG(ERROR) << "Mandatory argument: " << arg_error << " missing";
        LOG(INFO) << kUsagePublic;
        return -1;
    }

    result = command.checkMandatoryPosition(command_map, arg_error);
    if (result != 0) {
        LOG(ERROR) << "Mandatory argument " << arg_error
                   << " is not on its correct position ("
                   << command_map[arg_error].position << ").";
        LOG(INFO) << kUsagePublic;
        return -1;
    }

    std::string folder_path; // Path to store the depth frames
    std::string json_file_path; // Get the .json file from command line

    uint32_t n_frames = 0;
    uint8_t mode = 0;
    std::string ip;
    std::string firmware;
    std::string configuration = "standard";

    google::InitGoogleLogging(argv[0]);
    FLAGS_alsologtostderr = 1;


    LOG(INFO) << "ADCAM version: " << aditof::getKitVersion()
	      << " | SDK version: " << aditof::getApiVersion()
              << " | branch: " << aditof::getBranchVersion()
              << " | commit: " << aditof::getCommitVersion();

    Status status = Status::OK;
    // Parsing the arguments from command line
    json_file_path = std::string(command_map["-lcf"].value.c_str());

    // Parsing output folder
    folder_path = std::string(command_map["-f"].value.c_str());

    // Parsing frame rate
    uint16_t fps = std::stoi(command_map["-fps"].value);
    if (fps == 0 || fps > 60) {
        LOG(ERROR) << "Invalid frame rate: " << fps
                   << ". Valid range is 1 to 30 fps.";
        return -1;
    }

    // Parsing number of frames
    n_frames = std::stoi(command_map["-n"].value);

    if (!command_map["-m"].value.empty()) {
        mode = std::stoi(command_map["-m"].value);
    }

    // Parsing ip
    if (!command_map["-ip"].value.empty()) {
        ip = command_map["-ip"].value;
    }

    // Parsing firmware
    if (!command_map["-fw"].value.empty()) {
        firmware = command_map["-fw"].value;
    }

    //Parsing CCB path
    std::string ccbFilePath;
    if (!command_map["-ccb"].value.empty()) {
        ccbFilePath = command_map["-ccb"].value;
    }

    // Parsing configuration option
    std::vector<std::string> configurationlist = {"standard", "standard-raw",
                                                  "custom", "custom-raw"};

    std::string configurationValue = command_map["-ic"].value;
    if (!configurationValue.empty()) {
        unsigned int pos =
            std::find(configurationlist.begin(), configurationlist.end(),
                      configurationValue) -
            configurationlist.begin();
        if (pos < configurationlist.size()) {
            configuration = configurationValue;
        }
    }

    bool saveconfigurationFile = false;
    std::string saveconfigurationFileValue = command_map["-scf"].value;
    if (!saveconfigurationFileValue.empty()) {
        if (saveconfigurationFileValue.find(".json") == std::string::npos) {
            saveconfigurationFileValue += ".json";
        }
        saveconfigurationFile = true;
        json_file_path = "";
    }

    LOG(INFO) << "Output folder: " << folder_path;
    LOG(INFO) << "Mode: " << command_map["-m"].value;
    LOG(INFO) << "Number of frames: " << n_frames;
    LOG(INFO) << "Json file: " << json_file_path;
    LOG(INFO) << "Configuration is: " << configuration;

    if (!ip.empty()) {
        LOG(INFO) << "Ip address is: " << ip;
    }

    if (!firmware.empty()) {
        LOG(INFO) << "Firmware file is: " << firmware;
    }

    if (!ccbFilePath.empty()) {
        LOG(INFO) << "Path to store CCB content: " << ccbFilePath;
    }

    System system;
    std::vector<std::shared_ptr<Camera>> cameras;

    if (!ip.empty()) {
        ip = "ip:" + ip;
        system.getCameraList(cameras, ip);
    } else {
        system.getCameraList(cameras);
    }

    if (cameras.empty()) {
        LOG(WARNING) << "No cameras found";
        return -1;
    }

    auto camera = cameras.front();

    status = camera->initialize(json_file_path);
    if (status != Status::OK) {
        LOG(ERROR) << "Could not initialize camera!";
        return -1;
    }

    status = camera->setSensorConfiguration(configuration);
    if (status != Status::OK) {
        LOG(INFO) << "Could not configure camera with " << configuration;
    } else {
        LOG(INFO) << "Configure camera with " << configuration;
    }

    if (saveconfigurationFile) {
        status = camera->saveDepthParamsToJsonFile(saveconfigurationFileValue);
        if (status != Status::OK) {
            LOG(INFO) << "Could not save current configuration info to "
                      << saveconfigurationFileValue;
        } else {
            LOG(INFO) << "Current configuration info saved to file "
                      << saveconfigurationFileValue;
        }
    }

    aditof::CameraDetails cameraDetails;
    camera->getDetails(cameraDetails);

    if (!firmware.empty()) {
        std::ifstream file(firmware);
        if (!(file.good() &&
              file.peek() != std::ifstream::traits_type::eof())) {
            LOG(ERROR) << firmware << " not found or is an empty file";
            return -1;
        }

        status = camera->adsd3500UpdateFirmware(firmware);
        if (status != Status::OK) {
            LOG(ERROR) << "Could not update the adsd3500 firmware";
            return -1;
        } else {
            LOG(INFO) << "Please reboot the board!";
            return -1;
        }
    }

    camera->adsd3500GetFrameRate(fps);

    // Get modes
    std::vector<uint8_t> availableModes;
    status = camera->getAvailableModes(availableModes);
    if (status != Status::OK || availableModes.empty()) {
        LOG(ERROR) << "Could not aquire modes";
        return -1;
    }

    std::shared_ptr<DepthSensorInterface> depthSensor = camera->getSensor();
    std::string sensorName;
    status = depthSensor->getName(sensorName);

    status = camera->setMode(mode);
    if (status != Status::OK) {
        LOG(ERROR) << "Could not set camera mode!";
        return -1;
    }

    status = camera->setControl("setFPS", std::to_string(fps));
    if (status != Status::OK) {
        LOG(ERROR) << "Error setting camera FPS to " << fps;
        return -1;
    }

    // Store CCB to file
    if (!ccbFilePath.empty()) {
        status = camera->saveModuleCCB(ccbFilePath);
        if (status != Status::OK) {
            LOG(INFO) << "Failed to store CCB to " << ccbFilePath;
        }
    }

    if (n_frames == 0) {
        LOG(INFO) << n_frames << " frames requested, exiting." << std::endl;
        return -1;
    }

    // Program the camera with cfg passed, set the mode by writing to 0x200 and start the camera
    status = camera->start();
    if (status != Status::OK) {
        LOG(ERROR) << "Could not start camera!";
        return -1;
    }

    aditof::Frame frame;
    FrameDetails fDetails;

    //drop first frame
    status = camera->requestFrame(&frame);
    if (status != Status::OK) {
        LOG(ERROR) << "Could not request frame!";
        return -1;
    }

    auto start_time = std::chrono::high_resolution_clock::now();

    long long runtime_in_ms = ((long long)n_frames / (long long)fps) * 1000;
    long long max_runtime_in_ms = 600000; // 10 minutes

    LOG(INFO) << "Starting capture of " << n_frames << " frames.";
    LOG(INFO) << "Expected capture time (ms): " << runtime_in_ms;
    LOG(INFO) << "Maximum allowed capture time (ms): " << max_runtime_in_ms;
    LOG(INFO) << "FPS: " << fps;

    if (runtime_in_ms > max_runtime_in_ms) {
        runtime_in_ms = max_runtime_in_ms;

        LOG(WARNING) << "The requested number of frames will take more than 10 "
                        "minutes to capture. Limiting the capture time to 10 "
                        "minutes.";
    }

    long long milliseconds = 0;
    uint32_t frames_captured = 0;

    status = camera->startRecording(folder_path);
    if (status != Status::OK) {
        LOG(ERROR) << "Unable to start recording!";
        return -1;
    }

    while(frames_captured < n_frames) {
        auto end_time = std::chrono::high_resolution_clock::now();
        auto total_time_ms_duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time);
        milliseconds = total_time_ms_duration.count();
        if (milliseconds >= runtime_in_ms) {
            LOG(WARNING) << "Maximum capture time reached. Stopping capture.";
            break;
        }
        status = camera->requestFrame(&frame);
        if (status != Status::OK) {
            LOG(ERROR) << "Unable to request frame!";
            break;
        }
        frames_captured++;
        usleep(1000 * 5); // Sleep for 5ms
    }

    LOG(INFO) << "Capture complete. Frames captured: " << frames_captured;
    status = camera->stopRecording();
    if (status != Status::OK) {
        LOG(WARNING) << "Unable to stop recording!";
    }

    if (milliseconds > 0.0 && frames_captured > 0) {
        double measured_fps = (double)frames_captured / ((double)milliseconds / 1000.0);
        LOG(INFO) << "Measured FPS: " << measured_fps;
    }

    status = camera->stop();
    if (status != Status::OK) {
        LOG(ERROR) << "Error stopping camera!";
        return -1;
    }
    return 0;
}
