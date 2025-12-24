/*
 * MIT License
 *
 * Copyright (c) 2025 Analog Devices, Inc.
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

#include "ADIMainWindow.h"
#include "ADIOpenFile.h"
#include "aditof/status_definitions.h"
#include "aditof/system.h"
#include "aditof/version.h"
#include <aditof/log.h>
#include <iostream>

#if defined(_WIN32) || defined(__WIN32__) || defined(WIN32)
#include "psapi.h"
#include <io.h>
#include <windows.h>
/* TODO : Remove <experimental/filesystem> when updating to C++17 or newer */
#define _SILENCE_EXPERIMENTAL_FILESYSTEM_DEPRECATION_WARNING
#include <experimental/filesystem>
namespace fs = std::experimental::filesystem;
#define PATH_SEPARATOR "\\"
#else
#include "filesystem.hpp"
namespace fs = ghc::filesystem;
#include <limits.h>
#define MAX_PATH PATH_MAX
#define PATH_SEPARATOR "/"
#endif

using namespace adiMainWindow;

void ADIMainWindow::InitCamera(std::string filePath) {
    if (m_view_instance != NULL) { //Reset current imager
        LOG(INFO) << "Imager is reseting.";
        m_view_instance.reset();
        LOG(INFO) << "Reset successful.";
    }

    std::string version = aditof::getApiVersion();
    LOG(INFO) << "Preparing camera. Please wait...\n";

    // For offline mode, always enable all display types
    // The viewer threads will check metadata/config per-frame to decide processing
    // For live mode, set enable flags to true initially (will be properly set after mode is configured)
    m_enable_ab_display = true;
    m_enable_depth_display = true;
    m_enable_xyz_display = true;

    // Initially create with all displays enabled (will be updated after mode is set)
    m_view_instance = std::make_shared<adiviewer::ADIView>(
        std::make_shared<adicontroller::ADIController>(m_cameras_list),
        "ToFViewer " + version, m_enable_ab_display, m_enable_depth_display,
        m_enable_xyz_display);

    if (!m_off_line) {
        m_cameras_list.clear();
        _cameraModes.clear();
        m_cameraModesDropDown.clear();
        m_cameraModesLookup.clear();
    }

    aditof::Status status = aditof::Status::OK;
    auto camera = GetActiveCamera(); //already initialized on constructor

    if (!camera) {
        LOG(ERROR) << "No cameras found!";
        return;
    }

    status = camera->initialize("");
    if (status != aditof::Status::OK) {
        LOG(ERROR) << "Could not initialize camera!";
        return;
    }

    if (!m_off_line) {

        aditof::CameraDetails cameraDetails;
        camera->getDetails(cameraDetails);
        camera->getAvailableModes(_cameraModes);
        sort(_cameraModes.begin(), _cameraModes.end());

        for (uint32_t i = 0; i < (uint32_t)_cameraModes.size(); ++i) {
            aditof::DepthSensorModeDetails modeDetails;

            auto sensor = camera->getSensor();
            sensor->getModeDetails(_cameraModes.at(i), modeDetails);

            std::string s = std::to_string(_cameraModes.at(i));
            s = s + ":" + std::to_string(modeDetails.baseResolutionWidth) +
                "x" + std::to_string(modeDetails.baseResolutionHeight) + ",";
            if (!modeDetails.isPCM) {
                std::string append = (modeDetails.numberOfPhases == 2)
                                         ? "Short Range"
                                         : "Long Range";
                s = s + append;
            } else {
                s = s + "PCM";
            }
            m_cameraModesDropDown.emplace_back(modeDetails.modeNumber, s);
            m_cameraModesLookup[modeDetails.modeNumber] = s;
        }

        for (uint32_t i = 0; i < (uint32_t)_cameraModes.size(); i++) {
            m_cameraModes.emplace_back(i, _cameraModes.at(i));
        }
    } else {
        // PRB25
        //camera->setPlaybackFile(filePath);
    }
    m_cameraWorkerDone = true;
    m_is_open_device = true;
}

void ADIMainWindow::UpdateOfflineFrameTypeAvailability() {
    // For offline mode, check what frame types are actually available
    // by requesting a frame and checking its metadata
    if (!m_off_line || !GetActiveCamera()) {
        return;
    }

    aditof::Frame frame;
    if (GetActiveCamera()->requestFrame(&frame) == aditof::Status::OK) {
        aditof::Metadata *metadata;
        if (frame.getData("metadata", (uint16_t **)&metadata) ==
                aditof::Status::OK &&
            metadata != nullptr) {
            // Check config to determine which displays should be enabled
            // For depth, check if data exists (bitsInDepth may be 0 for ISP-computed modes)
            m_enable_depth_display = frame.haveDataType("depth");
            m_enable_ab_display = (metadata->bitsInAb != 0);
            // XYZ availability is based on xyzEnabled flag in metadata
            m_enable_xyz_display = (metadata->xyzEnabled != 0);

            LOG(INFO) << "Offline frame types available: depth="
                      << m_enable_depth_display << " ab=" << m_enable_ab_display
                      << " xyz=" << m_enable_xyz_display
                      << " (from metadata: bitsInDepth="
                      << (int)metadata->bitsInDepth
                      << " bitsInAb=" << (int)metadata->bitsInAb
                      << " xyzEnabled=" << (int)metadata->xyzEnabled << ")";
        }
    }
}

void ADIMainWindow::PrepareCamera(uint8_t mode) {
    aditof::Status status = aditof::Status::OK;
    std::vector<aditof::FrameDetails> frameTypes;

    status = GetActiveCamera()->setMode(mode);
    if (status != aditof::Status::OK) {
        LOG(ERROR) << "Could not set camera mode!";
        return;
    }
#if 0 //Andre
    if (!m_off_line) {
        status = GetActiveCamera()->adsd3500SetFrameRate(m_user_frame_rate);
        if (status != aditof::Status::OK) {
            LOG(ERROR) << "Could not set user frame rate!";
            return;
        }
    }
#endif
    if (mode == m_last_mode) {
        if (!m_modified_ini_params.empty()) {
            if (m_use_modified_ini_params) {
                status = GetActiveCamera()->setFrameProcessParams(
                    m_modified_ini_params, mode);
                if (status != aditof::Status::OK) {
                    LOG(ERROR) << "Could not set ini params";
                } else {
                    LOG(INFO) << "Using user defined ini parameters.";
                    m_use_modified_ini_params = false;
                    m_modified_ini_params.clear();
                }
            }
        }
    } else {
        m_use_modified_ini_params = false;
        m_ini_params.clear();
        m_modified_ini_params.clear();
        m_last_mode = mode;
    }

    aditof::CameraDetails camDetails;
    status = GetActiveCamera()->getDetails(camDetails);
    //int32_t totalCaptures = camDetails.frameType.totalCaptures;

    // For offline mode, recreate viewer with all frame types enabled
    // The threads will check metadata per-frame to decide if processing is needed
    status = GetActiveCamera()->adsd3500GetFrameRate(m_fps_expected);

    if (m_enable_preview) {
        m_view_instance->m_ctrl->setPreviewRate(m_fps_expected,
                                                PREVIEW_FRAME_RATE);
    } else {
        m_view_instance->m_ctrl->setPreviewRate(m_fps_expected, m_fps_expected);
    }

    if (!m_view_instance->getUserABMaxState()) {
        std::string value;
        GetActiveCamera()->getSensor()->getControl("abBits", value);
        m_view_instance->setABMaxRange(value);
    }

    // Program the camera with cfg passed, set the mode by writing to 0x200 and start the camera
    status = GetActiveCamera()->start();
    if (status != aditof::Status::OK) {
        LOG(ERROR) << "Could not start camera!";
        return;
    }

    // For offline mode, check what frame types are actually available
    if (m_off_line) {
        UpdateOfflineFrameTypeAvailability();
    }

    LOG(INFO) << "Camera ready.";
    m_cameraWorkerDone = true;
    m_tof_image_pos_y = -1.0f;
}

void ADIMainWindow::CameraPlay(int modeSelect, int viewSelect) {
    ImGuiWindowFlags
        overlayFlags = /*ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoTitleBar |*/
        ImGuiWindowFlags_NoResize | /*ImGuiWindowFlags_AlwaysAutoResize |*/
        ImGuiWindowFlags_NoSavedSettings | ImGuiWindowFlags_NoFocusOnAppearing |
        ImGuiWindowFlags_NoNav | ImGuiWindowFlags_NoScrollbar |
        ImGuiWindowFlags_NoBringToFrontOnFocus;

    //const bool imageIsHovered = ImGui::IsItemHovered();

    if (m_view_instance == nullptr) {
        return;
    }

    if (m_view_instance->m_ctrl->hasCamera()) {
        // Mode switch or starup
        if (m_mode_select_changed != modeSelect || m_capture_separate_enabled ||
            !m_is_playing) {
            if (m_mode_select_changed != modeSelect) {
                m_view_instance->m_ctrl->StopCapture();
            }

            PrepareCamera(modeSelect);
            OpenGLCleanUp();
            InitOpenGLABTexture();
            InitOpenGLDepthTexture();
            InitOpenGLPointCloudTexture();

            if (!m_off_line) {
                m_view_instance->m_ctrl->StartCapture(m_fps_expected);
                m_view_instance->m_ctrl->requestFrame();
            } else { // Offline: Always get the first frame
                if (m_offline_change_frame) {
                    m_view_instance->m_ctrl->requestFrame();
                    m_view_instance->m_ctrl->requestFrameOffline(
                        m_off_line_frame_index);
                    m_offline_change_frame = false;
                }
            }
            m_capture_separate_enabled = false;
            m_mode_select_changed = modeSelect;

        } else if (m_view_selection_changed != viewSelect) {
            m_view_selection_changed = viewSelect;
            OpenGLCleanUp();
            InitOpenGLABTexture();
            InitOpenGLDepthTexture();
            InitOpenGLPointCloudTexture();
        }
    }

    std::shared_ptr<aditof::Frame> frame;
    if (synchronizeVideo(frame) >= 0) {
        if (frame != nullptr) {

            bool diverging = false;
            aditof::Metadata *metadata;
            aditof::Status status =
                frame->getData("metadata", (uint16_t **)&metadata);
            if (status == aditof::Status::OK && metadata != nullptr) {
                diverging = m_view_instance->m_ctrl->OutputDeltaTime(
                    metadata->frameNumber);

                //LOG(INFO) << "Diverging: " << diverging;
            }

            // Check what frame types are available based on metadata config
            bool haveAB, haveDepth, haveXYZ, haveRGB;
            if (m_off_line) {
                // Offline: use cached availability from UpdateOfflineFrameTypeAvailability()
                haveAB = m_enable_ab_display && frame->haveDataType("ab");
                haveDepth =
                    m_enable_depth_display && frame->haveDataType("depth");
                haveXYZ = m_enable_xyz_display && frame->haveDataType("xyz");
#ifdef WITH_RGB_SUPPORT
                haveRGB = frame->haveDataType("rgb");
#else
                haveRGB = false;
#endif
            } else {
                // Live mode: For AB and XYZ, check config. For depth, always show if data exists
                // (bitsInDepth may be 0 for ISP-computed depth modes)
                if (metadata != nullptr) {
                    haveDepth = frame->haveDataType("depth");
                    haveAB =
                        (metadata->bitsInAb != 0) && frame->haveDataType("ab");
                    haveXYZ = (metadata->xyzEnabled != 0) &&
                              frame->haveDataType("xyz");
                } else {
                    // Fallback if metadata not available
                    haveAB = frame->haveDataType("ab");
                    haveDepth = frame->haveDataType("depth");
                    haveXYZ = frame->haveDataType("xyz");
                }
#ifdef WITH_RGB_SUPPORT
                haveRGB = frame->haveDataType("rgb");
#else
                haveRGB = false;
#endif
            }

            uint32_t numberAvailableDataTypes = 0;

            numberAvailableDataTypes += haveAB ? 1 : 0;
            numberAvailableDataTypes += haveDepth ? 1 : 0;
            numberAvailableDataTypes += haveXYZ ? 1 : 0;
#ifdef WITH_RGB_SUPPORT
            numberAvailableDataTypes += haveRGB ? 1 : 0;
#endif

            ImGuiIO &io = ImGui::GetIO();
            if (io.KeyShift) {

                if (ImGui::IsKeyPressed(ImGuiKey_RightArrow)) {
                    m_depth_line_values.clear();
                    m_depthLine.clear();
                    m_frame_window_position_state++;
                    if (m_frame_window_position_state >
                        numberAvailableDataTypes)
                        m_frame_window_position_state = 0;
                }

                if (ImGui::IsKeyPressed(ImGuiKey_LeftArrow)) {
                    m_depth_line_values.clear();
                    m_depthLine.clear();
                    m_frame_window_position_state--;
                    if (m_frame_window_position_state < 0)
                        m_frame_window_position_state =
                            numberAvailableDataTypes;
                }
            }

            if (numberAvailableDataTypes == 3) {
                if (m_frame_window_position_state == 0) {
                    m_xyz_position = &m_dict_win_position["fr-main"];
                    m_ab_position = &m_dict_win_position["fr-sub1"];
                    m_depth_position = &m_dict_win_position["fr-sub2"];
                } else if (m_frame_window_position_state == 1) {
                    m_xyz_position = &m_dict_win_position["fr-sub2"];
                    m_ab_position = &m_dict_win_position["fr-main"];
                    m_depth_position = &m_dict_win_position["fr-sub1"];
                } else if (m_frame_window_position_state == 2) {
                    m_xyz_position = &m_dict_win_position["fr-sub1"];
                    m_ab_position = &m_dict_win_position["fr-sub2"];
                    m_depth_position = &m_dict_win_position["fr-main"];
                }
            } else if (numberAvailableDataTypes == 2) {

                if (!haveAB) {

                    if (m_frame_window_position_state == 0) {
                        m_xyz_position = &m_dict_win_position["fr-main"];
                        m_depth_position = &m_dict_win_position["fr-sub1"];
                    } else {
                        m_xyz_position = &m_dict_win_position["fr-sub1"];
                        m_depth_position = &m_dict_win_position["fr-main"];
                    }
                } else if (!haveDepth) {

                    if (m_frame_window_position_state == 0) {
                        m_xyz_position = &m_dict_win_position["fr-main"];
                        m_ab_position = &m_dict_win_position["fr-sub1"];
                    } else {
                        m_xyz_position = &m_dict_win_position["fr-sub1"];
                        m_ab_position = &m_dict_win_position["fr-main"];
                    }
                } else if (!haveXYZ) {

                    if (m_frame_window_position_state == 0) {
                        m_depth_position = &m_dict_win_position["fr-main"];
                        m_ab_position = &m_dict_win_position["fr-sub1"];
                    } else {
                        m_depth_position = &m_dict_win_position["fr-sub1"];
                        m_ab_position = &m_dict_win_position["fr-main"];
                    }
                }
            } else {
                if (haveDepth) {
                    m_depth_position = &m_dict_win_position["fr-main"];
                } else if (haveAB) {
                    m_ab_position = &m_dict_win_position["fr-main"];
                } else if (haveXYZ) {
                    m_xyz_position = &m_dict_win_position["fr-main"];
                }
            }

            if (haveXYZ) {
                DisplayPointCloudWindow(overlayFlags);
            }
#ifdef WITH_RGB_SUPPORT
            // Display AB window if either AB or RGB data is available
            if (haveAB || haveRGB) {
                DisplayActiveBrightnessWindow(overlayFlags);
            }
#else
            if (haveAB) {
                DisplayActiveBrightnessWindow(overlayFlags);
            }
#endif
            if (haveDepth) {
                DisplayDepthWindow(overlayFlags);
            }
            DisplayInfoWindow(overlayFlags, diverging);
            DisplayControlWindow(overlayFlags, haveAB, haveDepth, haveXYZ);
            if (haveDepth) {
                DepthLinePlot(overlayFlags);
            }
        }
    }
}

void ADIMainWindow::CameraStop() {
    if (m_view_instance) {
        if (m_view_instance->m_ctrl) {
            OpenGLCleanUp();
            m_view_instance->m_ctrl->StopCapture();
            m_view_instance->m_ctrl->panicStop = false;
        }
    }
    /*if (initCameraWorker.joinable()) {
        initCameraWorker.join();
        m_cameraModes.clear();
        _cameraModes.clear();
    }*/
    m_focused_once = false;
    m_capture_separate_enabled = true;
    m_set_ab_win_position_once = true;
    m_set_depth_win_position_once = true;
    m_set_point_cloud_position_once = true;
    m_is_playing = false;
    m_fps_frame_received = 0;
    m_off_line_frame_index = 0;
}

void ADIMainWindow::RefreshDevices() {

    m_cameraWorkerDone = false;
    m_cameraModes.clear();
    _cameraModes.clear();
    if (initCameraWorker.joinable()) {
        initCameraWorker.join();
    }

    m_selected_device_index = -1;
    m_connected_devices.clear();
    m_configFiles.clear();
    m_cameras_list.clear();

    aditof::Status status;
    if (m_off_line) {
        status = m_system.getCameraList(m_cameras_list, "offline:");
        if (status != aditof::Status::OK) {
            LOG(WARNING) << "Unable to get Offline camera list.";
        } else {
            for (size_t ix = 0; ix < m_cameras_list.size(); ++ix) {
                m_connected_devices.emplace_back(ix, "ToF Camera " +
                                                         std::to_string(ix));
            }
        }
    } else {

        status = m_system.getCameraList(m_cameras_list);
        if (status != aditof::Status::OK) {
            LOG(WARNING) << "Unable to get Camera list.";
        } else {
            if (!m_skip_network_cameras) {
                // Add network camera - reuse the same list instead of calling getCameraList again
                std::vector<std::shared_ptr<aditof::Camera>> networkCameras;
                m_system.getCameraList(networkCameras,
                                       m_cameraIp + m_ip_suffix);
                // Append network cameras to the existing list
                m_cameras_list.insert(m_cameras_list.end(),
                                      networkCameras.begin(),
                                      networkCameras.end());
            }

            // Build the connected devices list once after collecting all cameras
            for (size_t ix = 0; ix < m_cameras_list.size(); ++ix) {
                m_connected_devices.emplace_back(ix, "ToF Camera " +
                                                         std::to_string(ix));
            }
        }
    }

    if (!m_connected_devices.empty()) {
        //Search for configuration files with .json extension
        m_config_selection = -1;
        fs::path _currPath = fs::current_path();
        std::vector<std::string> files;
        getFilesList(_currPath.string(), "*.json", files, false);

        for (size_t fileCnt = 0; fileCnt < files.size(); fileCnt++) {
            m_configFiles.emplace_back(fileCnt, files[fileCnt]);
        }

        if (!m_configFiles.empty() && m_config_selection == -1) {
            m_config_selection = 0;
        }
    }
}

void ADIMainWindow::HandleInterruptCallback() {
    aditof::SensorInterruptCallback cb = [this](aditof::Adsd3500Status status) {
        LOG(WARNING) << "status: " << status;
        ImGui::Begin("Interrupt");
        ImGui::Text("%i", (int32_t)status);
        ImGui::End();
    };
    aditof::Status ret_status = aditof::Status::OK;
    auto camera = GetActiveCamera();
    if (!camera) {
        return;
    }
    ret_status = camera->getSensor()->adsd3500_register_interrupt_callback(cb);
    if (ret_status != aditof::Status::OK) {
        LOG(ERROR) << "Could not register interrupt callback";
        return;
    }
}