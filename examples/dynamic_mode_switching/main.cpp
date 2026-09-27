/*
 * MIT License
 *
 * Copyright (c) 2026 Analog Devices, Inc.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#include <aditof/camera.h>
#include <aditof/depth_sensor_interface.h>
#include <aditof/frame.h>
#include <aditof/log.h>
#include <aditof/system.h>
#include <aditof/version-kit.h>
#include <aditof/version.h>
#include <algorithm>
#include <chrono>
#include <command_parser.h>
#include <fstream>
#include <ios>
#include <map>
#include <thread>

using namespace aditof;

static const char Help_Menu[] =
    R"(Dynamic Mode Switching usage:
    dynamic_mode_switching
    dynamic_mode_switching (-h | --help)
    dynamic_mode_switching [-ip | --ip <ip>] [-m0 | --m0 <modeA>] [-m1 | --m1 <modeB>]
                           [-config | --config <config_file.json>] [-fps | --fps <fps>]
                           [-n | --n <pairs>]

    Options:
      -h --help              Show this screen.
      -m0 --m0 <modeA>       First mode in the switching sequence. [default: 0]
      -m1 --m1 <modeB>       Second mode in the switching sequence. [default: 1]
      -fps --fps <fps>       Frame rate to configure. [default: 20]
      -n --n <pairs>         Number of (modeA, modeB) frame pairs to capture. [default: 1]
      -config <config.json>  Optional JSON config file with depth parameters.
      -ip <ip>               Camera IP address (network cameras only).

)";

/**
 * @brief Save a frame's data to a binary file, tagged by the mode it belongs to.
 */
static Status save_frame(aditof::Frame &frame, const std::string &frameType,
                         int mode_num) {
    uint16_t *data1;
    FrameDataDetails fDetails;

    if (!frame.haveDataType(frameType)) {
        LOG(WARNING) << "Frame doesn't have data of type " << frameType;
        return Status::INVALID_ARGUMENT;
    }

    Status status = frame.getData(frameType, &data1);
    if (status != Status::OK || !data1) {
        LOG(ERROR) << "Could not get frame data " << frameType;
        return Status::GENERIC_ERROR;
    }

    frame.getDataDetails(frameType, fDetails);
    std::ofstream out("out_" + frameType + "_mode_" + std::to_string(mode_num) +
                          ".bin",
                      std::ios::binary);
    out.write(reinterpret_cast<char *>(data1), fDetails.bytesCount);
    out.close();

    return Status::OK;
}

int main(int argc, char *argv[]) {
    std::map<std::string, struct Argument> command_map = {
        {"-h", {"--help", false, "", "", false}},
        {"-ip", {"--ip", false, "", "", true}},
        {"-m0", {"--m0", false, "", "0", true}},
        {"-m1", {"--m1", false, "", "1", true}},
        {"-fps", {"--fps", false, "", "20", true}},
        {"-n", {"--n", false, "", "1", true}},
        {"-config", {"--config", false, "last", "", false}}};

    CommandParser command;
    std::string arg_error;
    google::InitGoogleLogging(argv[0]);
    FLAGS_alsologtostderr = 1;

    command.parseArguments(argc, argv, command_map);
    int result = command.checkArgumentExist(command_map, arg_error);
    if (result != 0) {
        LOG(ERROR) << "Argument " << arg_error << " doesn't exist!";
        std::cout << Help_Menu;
        return -1;
    }

    result = command.helpMenu();
    if (result == 1) {
        std::cout << Help_Menu;
        return 0;
    } else if (result == -1) {
        LOG(ERROR) << "Usage of argument -h/--help"
                   << " is incorrect! Help argument should be used alone!";
        std::cout << Help_Menu;
        return -1;
    }

    result = command.checkValue(command_map, arg_error);
    if (result != 0) {
        LOG(ERROR) << "Argument: " << command_map[arg_error].long_option
                   << " doesn't have assigned or default value!";
        std::cout << Help_Menu;
        return -1;
    }

    LOG(INFO) << "ADCAM version: " << aditof::getKitVersion()
              << " | SDK version: " << aditof::getApiVersion();

    uint8_t modeA = static_cast<uint8_t>(std::stoi(command_map["-m0"].value));
    uint8_t modeB = static_cast<uint8_t>(std::stoi(command_map["-m1"].value));
    uint16_t fps = static_cast<uint16_t>(std::stoi(command_map["-fps"].value));
    int pairsToCapture = std::stoi(command_map["-n"].value);
    std::string configFile = command_map["-config"].value;
    std::string ip;
    if (!command_map["-ip"].value.empty()) {
        ip = "ip:" + command_map["-ip"].value;
    }

    System system;
    std::vector<std::shared_ptr<Camera>> cameras;
    Status status = ip.empty() ? system.getCameraList(cameras)
                               : system.getCameraList(cameras, ip);
    if (status != Status::OK || cameras.empty()) {
        LOG(WARNING) << "No cameras found";
        return 0;
    }
    auto camera = cameras.front();

    status = configFile.empty() ? camera->initialize()
                                : camera->initialize(configFile);
    if (status != Status::OK) {
        LOG(ERROR) << "Could not initialize camera!";
        return 0;
    }

    std::vector<uint8_t> availableModes;
    camera->getAvailableModes(availableModes);
    for (uint8_t m : {modeA, modeB}) {
        if (std::find(availableModes.begin(), availableModes.end(), m) ==
            availableModes.end()) {
            LOG(ERROR) << "Mode " << static_cast<int>(m)
                       << " is not available on this camera!";
            return 0;
        }
    }

    status = camera->setMode(modeA);
    if (status != Status::OK) {
        LOG(ERROR) << "Could not set camera mode!";
        return 0;
    }

    status = camera->adsd3500SetEnableMetadatainAB(1);
    if (status != Status::OK) {
        LOG(ERROR) << "Could not enable embedded metadata in AB frame!";
        return 0;
    }

    status = camera->adsd3500SetFrameRate(fps);
    if (status != Status::OK) {
        LOG(ERROR) << "Could not set frame rate!";
        return 0;
    }

    // The mode-switch chip command in setMode() clears the MIPI transport
    // register (same as a full reset); reapply it before touching DMS registers.
    status = camera->adsd3500SetMIPIOutputSpeed(1);
    if (status != Status::OK) {
        LOG(ERROR) << "Could not reapply MIPI output speed before DMS setup!";
        return 0;
    }

    // Chip bus needs to settle after the mode-switch reset before it will
    // reliably accept the DMS register writes.
    std::this_thread::sleep_for(std::chrono::milliseconds(300));

    status = camera->adsd3500setEnableDynamicModeSwitching(true);
    if (status != Status::OK) {
        LOG(ERROR) << "Could not enable Dynamic Mode Switching!";
        return 0;
    }

    std::vector<std::pair<uint8_t, uint8_t>> sequence = {
        {modeA, 1}, // Mode A, repeat 1 time
        {modeB, 1}, // Mode B, repeat 1 time
    };
    status = camera->adsds3500setDynamicModeSwitchingSequence(sequence);
    if (status != Status::OK) {
        LOG(ERROR) << "Could not set Dynamic Mode Switching sequence!";
        return 0;
    }

    // Chip needs a moment to apply the sequence before the status register
    // reflects it.
    std::this_thread::sleep_for(std::chrono::milliseconds(300));

    // Status readback is diagnostic-only; not all firmware versions support
    // reading it outside of an active stream, so treat failure as non-fatal.
    uint16_t dmsStatus = 0;
    status = camera->adsd3500GetGenericTemplate(0x0085, dmsStatus);
    if (status != Status::OK) {
        LOG(WARNING) << "Could not read Dynamic Mode Status register "
                        "(non-fatal)";
    } else {
        LOG(INFO) << "Dynamic Mode Status: " << dmsStatus;
    }

    status = camera->start();
    if (status != Status::OK) {
        LOG(ERROR) << "Could not start the camera!";
        return 0;
    }

    aditof::Frame frame;
    Metadata metadata;
    const int maxTriesPerPair = 10;

    for (int pair = 0; pair < pairsToCapture; ++pair) {
        bool haveModeA = false;
        bool haveModeB = false;
        int tries = 0;

        while ((!haveModeA || !haveModeB) && tries < maxTriesPerPair) {
            status = camera->requestFrame(&frame);
            if (status != Status::OK) {
                LOG(ERROR) << "Could not request frame!";
                camera->stop();
                return 0;
            }

            status = frame.getMetadataStruct(metadata);
            if (status != Status::OK) {
                LOG(ERROR) << "Could not read frame metadata!";
                camera->stop();
                return 0;
            }

            LOG(INFO) << "Captured frame for mode "
                      << static_cast<int>(metadata.imagerMode)
                      << " | Sensor Temp: " << metadata.sensorTemperature
                      << " C | Laser Temp: " << metadata.laserTemperature
                      << " C";

            if (metadata.imagerMode == modeA && !haveModeA) {
                save_frame(frame, "depth", modeA);
                haveModeA = true;
            } else if (metadata.imagerMode == modeB && !haveModeB) {
                save_frame(frame, "depth", modeB);
                haveModeB = true;
            }

            ++tries;
        }

        if (!haveModeA || !haveModeB) {
            LOG(ERROR) << "Could not get consecutive frames for both modes "
                          "after "
                       << maxTriesPerPair << " tries";
            break;
        }
    }

    status = camera->stop();
    if (status != Status::OK) {
        LOG(ERROR) << "Could not stop the camera!";
        return 0;
    }

    return 0;
}
