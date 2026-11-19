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

#include "ADIImGUIExtensions.h"
#include "ADIMainWindow.h"
#include "aditof/playback_interface.h"
#include "aditof/utils.h"

#include <aditof/log.h>

#include <cmath>
#include <cstdarg> // for va_list
#include <cstdlib>
#include <ctime>
#include <imgui.h>
#include <iomanip>
#include <random>
#include <sys/stat.h>
#include <sys/types.h>
#ifdef _WIN32
#include <direct.h>
#endif

using namespace adiMainWindow;

inline ImVec2 operator+(const ImVec2 &a, const ImVec2 &b) {
    return ImVec2(a.x + b.x, a.y + b.y);
}
inline ImVec2 operator*(const ImVec2 &v, float f) {
    return ImVec2(v.x * f, v.y * f);
}

static bool folderExists(const std::string &path) {
    struct stat info;
    return (stat(path.c_str(), &info) == 0 && (info.st_mode & S_IFDIR));
}

static bool createFolder(const std::string &path) {
#ifdef _WIN32
    return _mkdir(path.c_str()) == 0 || errno == EEXIST;
#else
    return mkdir(path.c_str(), 0755) == 0 || errno == EEXIST;
#endif
}

static std::string viewerGenerateFileName(const std::string &prefix,
                                          const std::string &extension) {
    // Get current UTC time
    std::time_t now = std::time(nullptr);
    std::tm utc_tm;
#ifdef _WIN32
    gmtime_s(&utc_tm, &now); // Windows
#else
    gmtime_r(&now, &utc_tm); // Linux/macOS
#endif

    std::ostringstream oss;

    // Format time: YYYYMMDD_HHMMSS
    oss << prefix;
    oss << std::put_time(&utc_tm, "%Y%m%d_%H%M%S");

    // Generate random 8-digit hex
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<uint32_t> dis(0, 0xFFFFFFFF);
    uint32_t randNum = dis(gen);
    oss << "_" << std::hex << std::setw(8) << std::setfill('0') << randNum;

    oss << extension;

    return oss.str();
}

static bool
DrawIconButton(const char *id,
               std::function<void(ImDrawList *, ImVec2, ImVec2)> drawIcon,
               ImU32 bgColor = IM_COL32(60, 60, 60, 255)) {
    ImVec2 size(30, 30);
    ImVec2 pos = ImGui::GetCursorScreenPos();
    ImDrawList *drawList = ImGui::GetWindowDrawList();

    bool pressed = ImGui::InvisibleButton(id, size);
    ImVec2 min = pos;
    ImVec2 max = ImVec2(pos.x + size.x, pos.y + size.y);

    if (ImGui::IsItemActive())
        bgColor = IM_COL32(180, 0, 0, 255);
    else if (ImGui::IsItemHovered())
        bgColor = IM_COL32(255, 165, 0, 255);

    drawList->AddRectFilled(min, max, bgColor, 4.0f);

    drawIcon(drawList, min, max);
    return pressed;
}

bool ADIMainWindow::cameraButton(std::string &baseFileName) {
    if (DrawIconButton(
            "Camera",
            [](ImDrawList *dl, ImVec2 min, ImVec2 max) {
                ImVec2 center = (min + max) * 0.5f;
                float w = max.x - min.x;
                float h = max.y - min.y;

                // Camera body
                ImVec2 topLeft(center.x - w * 0.3f, center.y - h * 0.25f);
                ImVec2 bottomRight(center.x + w * 0.3f, center.y + h * 0.25f);
                dl->AddRectFilled(topLeft, bottomRight, IM_COL32_WHITE, 3.0f);

                // Lens circle
                ImVec2 lensCenter = center;
                float lensRadius = h * 0.1f;
                dl->AddCircleFilled(lensCenter, lensRadius,
                                    IM_COL32(50, 50, 50, 255));

                // Viewfinder bump
                ImVec2 bumpTL(center.x - w * 0.15f, center.y - h * 0.35f);
                ImVec2 bumpBR(center.x - w * 0.05f, center.y - h * 0.25f);
                dl->AddRectFilled(bumpTL, bumpBR, IM_COL32_WHITE, 2.0f);
            },
            IM_COL32(80, 80, 80, 255))) {

        std::string folder_path =
            aditof::Utils::getExecutableFolder() + "/captures/";

        if (!folderExists(folder_path)) {
            if (!createFolder(folder_path)) {
                LOG(ERROR) << "Failed to create folder for recordings: "
                           << folder_path;

                baseFileName = "";

                return false;
            }
        }

        std::string base_filename =
            folder_path + viewerGenerateFileName("aditof_", "");
        baseFileName = base_filename;

        if (m_off_line && m_offline_save_all_frames) {
            m_off_line_frame_index = 0;
        }

        return true;
    }
    return false;
}

void ADIMainWindow::DisplayControlWindow(ImGuiWindowFlags overlayFlags,
                                         bool haveAB, bool haveDepth,
                                         bool haveXYZ) {
    using namespace aditof;

    if ((float)m_view_instance->frameWidth == 0.0 &&
        (float)(m_view_instance->frameHeight == 0.0)) {
        return;
    }

    if (m_set_temp_win_position_once) {
        rotationangleradians = 0;
        rotationangledegrees = 0;
        m_set_temp_win_position_once = false;
    }

    SetWindowPosition(m_dict_win_position["control"].x,
                      m_dict_win_position["control"].y);
    SetWindowSize(m_dict_win_position["control"].width,
                  m_dict_win_position["control"].height);

    if (ImGui::Begin("Control Window", nullptr, overlayFlags)) {

        if (!m_focused_once) {
            ImGui::SetWindowFocus();
            m_focused_once = true;
        }

        if (!m_off_line) {

            DrawBarLabel("Configuration");

            NewLine(5.0f);

            if (ImGuiExtensions::ADIButton("Load Config", true)) {
                ShowLoadAdsdParamsMenu();
            }
            ImGuiExtensions::ADIShowTooltipFor("ControlLoadConfig");

            ImGui::SameLine(0.0f, 10.0f);

            if (ImGuiExtensions::ADIButton("Save Config", true)) {
                ShowSaveAdsdParamsMenu();
            }
            ImGuiExtensions::ADIShowTooltipFor("ControlSaveConfig");
            NewLine(5.0f);
            NewLine(5.0f);

            DrawBarLabel("Control");

            static std::string filePath = m_recording_path;

            cameraButton(m_base_file_name);
            ImGuiExtensions::ADIShowTooltipFor("ControlCapture");

            ImGui::SameLine(0.0f, 10.0f);

            ImU32 recordBgColor = IM_COL32(200, 0, 0, 255);
            if (m_recordingActive) {
                double blinkPhase = std::fmod(ImGui::GetTime(), 1.0);
                bool blinkOn = blinkPhase < 0.5;
                recordBgColor = blinkOn ? IM_COL32(200, 0, 0, 255)
                                        : IM_COL32(80, 0, 0, 255);
            }

            if (DrawIconButton(
                    "Record",
                    [](ImDrawList *dl, ImVec2 min, ImVec2 max) {
                        ImVec2 center = ImVec2((min.x + max.x) * 0.5f,
                                               (min.y + max.y) * 0.5f);
                        float radius = (max.x - min.x) * 0.2f;

                        // Draw a white circle in the center for the record icon
                        dl->AddCircleFilled(center, radius, IM_COL32_WHITE);
                    },
                    recordBgColor)) {

                if (!m_recordingActive) {

                    aditof::Status status =
                        GetActiveCamera()->startRecording(filePath);
                    if (status == aditof::Status::OK) {
                        m_view_instance->m_ctrl->setPreviewRate(
                            m_fps_expected,
                            m_view_instance->m_ctrl->PREVIEW_FRAME_RATE);
                        m_recordingActive = true;
                        LOG(INFO) << "Recording to " << filePath.c_str();
                    } else {
                        m_view_instance->m_ctrl->setPreviewRate(m_fps_expected,
                                                                m_fps_expected);
                        LOG(ERROR) << "Unable to start recording.";
                        filePath = m_recording_path;
                        ;
                        m_recordingActive = false;
                    }
                } else {
                    aditof::Status status = GetActiveCamera()->stopRecording();
                    if (status == aditof::Status::OK) {
                        LOG(INFO) << "Recording stopped.";
                        filePath = m_recording_path;
                        m_recordingActive = false;
                        m_view_instance->m_ctrl->setPreviewRate(m_fps_expected,
                                                                m_fps_expected);
                    } else {
                        LOG(ERROR) << "Unable to stop recording.";
                    }
                }
            }
            ImGuiExtensions::ADIShowTooltipFor("ControlRecord");

            ImGui::SameLine(0.0f, 10.0f);

            if (DrawIconButton("Stop", [](ImDrawList *dl, ImVec2 min,
                                          ImVec2 max) {
                    ImVec2 center = (min + max) * 0.5f;
                    float side = (max.x - min.x) * 0.4f;
                    ImVec2 pMin(center.x - side * 0.5f, center.y - side * 0.5f);
                    ImVec2 pMax(center.x + side * 0.5f, center.y + side * 0.5f);
                    dl->AddRectFilled(pMin, pMax, IM_COL32_WHITE);
                })) {
                if (m_recordingActive) {
                    aditof::Status status = GetActiveCamera()->stopRecording();
                    if (status == aditof::Status::OK) {
                        LOG(INFO) << "Recording stopped.";
                        filePath = m_recording_path;
                        m_recordingActive = false;
                        m_view_instance->m_ctrl->setPreviewRate(m_fps_expected,
                                                                m_fps_expected);
                    } else {
                        LOG(ERROR) << "Unable to stop recording.";
                    }
                }
                setWorkingLabel("Stopping camera...");
                setIsWorking(true);
                m_stop_filepath = filePath;
                m_stop_pending = true;
                m_stop_pending_frames = 1;
            }
            ImGuiExtensions::ADIShowTooltipFor("ControlStop");

            ImGui::SameLine(0.0f, 10.0f);

        } else { // Offline

            uint32_t max_frame_count = 0;
            auto playbackSensor =
                std::dynamic_pointer_cast<aditof::PlaybackInterface>(
                    GetActiveCamera()->getSensor());
            if (playbackSensor) {
                playbackSensor->getFrameCount(max_frame_count);
            }

            DrawBarLabel("Control");

            ImGui::Toggle("Export All Frames", &m_offline_save_all_frames);
            ImGuiExtensions::ADIShowTooltipFor("ControlSaveAllFrames");
            ImGui::NewLine();
            if (cameraButton(m_base_file_name)) {
                if (m_offline_save_all_frames) {
                    setWorkingLabel("Exporting all frames...");
                    setIsWorking(true);
                    m_capture_pending = true;
                    m_capture_pending_frames = 1;
                }
            }
            ImGuiExtensions::ADIShowTooltipFor("ControlCapture");

            ImGui::SameLine(0.0f, 10.0f);

            if (DrawIconButton(
                    "JumpToStart",
                    [](ImDrawList *dl, ImVec2 min, ImVec2 max) {
                        ImVec2 center = (min + max) * 0.5f;
                        float w = max.x - min.x;
                        float h = max.y - min.y;

                        float arrowW = w * 0.2f;
                        float arrowH = h * 0.35f;
                        float spacing = w * 0.05f;

                        // Triangle
                        ImVec2 p1(center.x + spacing + arrowW * 0.5f,
                                  center.y - arrowH);
                        ImVec2 p2(center.x + spacing + arrowW * 0.5f,
                                  center.y + arrowH);
                        ImVec2 p3(center.x + spacing - arrowW * 0.5f, center.y);

                        dl->AddTriangleFilled(p1, p2, p3, IM_COL32_WHITE);

                        // Bar (vertical line to the left of triangle)
                        float barX = center.x - spacing - arrowW * 0.5f;
                        dl->AddRectFilled(
                            ImVec2(barX - 1.0f, center.y - arrowH),
                            ImVec2(barX + 1.0f, center.y + arrowH),
                            IM_COL32_WHITE);
                    },
                    IM_COL32(60, 60, 60, 255))) {

                m_offline_change_frame = true;
                m_off_line_frame_index = 0;
            }
            ImGuiExtensions::ADIShowTooltipFor("ControlJumpToStart");

            ImGui::SameLine(0.0f, 10.0f);

            if (DrawIconButton(
                    "LeftArrow",
                    [](ImDrawList *dl, ImVec2 min, ImVec2 max) {
                        ImVec2 center = (min + max) * 0.5f;
                        float w = max.x - min.x;
                        float h = max.y - min.y;

                        float arrowW = w * 0.25f;
                        float arrowH = h * 0.3f;

                        ImVec2 p1(center.x + arrowW * 0.5f,
                                  center.y - arrowH); // tip top
                        ImVec2 p2(center.x + arrowW * 0.5f,
                                  center.y + arrowH); // tip bottom
                        ImVec2 p3(center.x - arrowW * 0.5f,
                                  center.y); // back center

                        dl->AddTriangleFilled(p1, p2, p3, IM_COL32_WHITE);
                    },
                    IM_COL32(50, 50, 50, 255))) {

                if (m_off_line_frame_index > 0) {
                    m_off_line_frame_index--;
                    m_offline_change_frame = true;
                }
            }

            ImGui::SameLine(0.0f, 10.0f);
#if 0
            if (DrawIconButton(
                "Play", [](ImDrawList* dl, ImVec2 min, ImVec2 max) {
                    ImVec2 center = (min + max) * 0.5f;
                    float w = max.x - min.x, h = max.y - min.y;
                    ImVec2 p1(center.x - w * 0.2f, center.y - h * 0.3f);
                    ImVec2 p2(center.x - w * 0.2f, center.y + h * 0.3f);
                    ImVec2 p3(center.x + w * 0.3f, center.y);
                    dl->AddTriangleFilled(p1, p2, p3, IM_COL32_WHITE);
                })) {

                // TODO: Play button

            }

            ImGui::SameLine(0.0f, 10.0f);

            if (DrawIconButton(
                "Pause",
                [](ImDrawList* dl, ImVec2 min, ImVec2 max) {
                    ImVec2 center = (min + max) * 0.5f;
                    float w = max.x - min.x;
                    float h = max.y - min.y;
                    float barWidth = w * 0.1f;
                    float barHeight = h * 0.5f;
                    float spacing = w * 0.1f;

                    ImVec2 bar1Min(center.x - spacing - barWidth,
                        center.y - barHeight * 0.5f);
                    ImVec2 bar1Max(center.x - spacing,
                        center.y + barHeight * 0.5f);
                    ImVec2 bar2Min(center.x + spacing,
                        center.y - barHeight * 0.5f);
                    ImVec2 bar2Max(center.x + spacing + barWidth,
                        center.y + barHeight * 0.5f);

                    dl->AddRectFilled(bar1Min, bar1Max, IM_COL32_WHITE);
                    dl->AddRectFilled(bar2Min, bar2Max, IM_COL32_WHITE);
                },
                IM_COL32(60, 60, 60, 255))) {

                // TODO
            }
#endif //0

            ImGui::SameLine(0.0f, 10.0f);

            if (DrawIconButton(
                    "RightArrow",
                    [](ImDrawList *dl, ImVec2 min, ImVec2 max) {
                        ImVec2 center = (min + max) * 0.5f;
                        float w = max.x - min.x;
                        float h = max.y - min.y;

                        float arrowW = w * 0.25f;
                        float arrowH = h * 0.3f;

                        ImVec2 p1(center.x - arrowW * 0.5f,
                                  center.y - arrowH); // tip top
                        ImVec2 p2(center.x - arrowW * 0.5f,
                                  center.y + arrowH); // tip bottom
                        ImVec2 p3(center.x + arrowW * 0.5f,
                                  center.y); // back center

                        dl->AddTriangleFilled(p1, p2, p3, IM_COL32_WHITE);
                    },
                    IM_COL32(50, 50, 50, 255))) {

                if (m_off_line_frame_index < max_frame_count - 1) {
                    m_off_line_frame_index++;
                    m_offline_change_frame = true;
                }
            }

            ImGui::SameLine(0.0f, 10.0f);

            if (DrawIconButton(
                    "JumpToEnd",
                    [](ImDrawList *dl, ImVec2 min, ImVec2 max) {
                        ImVec2 center = (min + max) * 0.5f;
                        float w = max.x - min.x;
                        float h = max.y - min.y;

                        float arrowW = w * 0.2f;
                        float arrowH = h * 0.35f;
                        float spacing = w * 0.05f;

                        // Triangle
                        ImVec2 p1(center.x - spacing - arrowW * 0.5f,
                                  center.y - arrowH);
                        ImVec2 p2(center.x - spacing - arrowW * 0.5f,
                                  center.y + arrowH);
                        ImVec2 p3(center.x - spacing + arrowW * 0.5f, center.y);

                        dl->AddTriangleFilled(p1, p2, p3, IM_COL32_WHITE);

                        // Bar (vertical line to the right of triangle)
                        float barX = center.x + spacing + arrowW * 0.5f;
                        dl->AddRectFilled(
                            ImVec2(barX - 1.0f, center.y - arrowH),
                            ImVec2(barX + 1.0f, center.y + arrowH),
                            IM_COL32_WHITE);
                    },
                    IM_COL32(60, 60, 60, 255))) {

                m_off_line_frame_index = max_frame_count - 1;
                m_offline_change_frame = true;
            }
            ImGuiExtensions::ADIShowTooltipFor("ControlJumpToEnd");

            ImGui::SameLine(0.0f, 10.0f);

            if (DrawIconButton("Stop", [](ImDrawList *dl, ImVec2 min,
                                          ImVec2 max) {
                    ImVec2 center = (min + max) * 0.5f;
                    float side = (max.x - min.x) * 0.4f;
                    ImVec2 pMin(center.x - side * 0.5f, center.y - side * 0.5f);
                    ImVec2 pMax(center.x + side * 0.5f, center.y + side * 0.5f);
                    dl->AddRectFilled(pMin, pMax, IM_COL32_WHITE);
                })) {
                setWorkingLabel("Stopping playback...");
                setIsWorking(true);
                m_stop_filepath = "";
                m_stop_pending = true;
                m_stop_pending_frames = 1;
            }
            ImGuiExtensions::ADIShowTooltipFor("ControlStop");

            NewLine(5.0f);
            if (ImGui::SliderInt("Frame #", (int *)&m_off_line_frame_index, 0,
                                 max_frame_count - 1, "#: %d")) {
                m_offline_change_frame = true;
            }
            ImGuiExtensions::ADIShowTooltipFor("ControlFrameSlider");
        }

        NewLine(5.0f);

        DrawBarLabel("Rotate");
        NewLine(5.0f);
        bool rotate = ImGui::Button("+");
        ImGuiExtensions::ADIShowTooltipFor("ControlRotatePlus");
        ImGui::SameLine();
        if (rotate) {
            rotationangleradians += M_PI / 2;
            rotationangledegrees += 90;
            if (rotationangledegrees >= 360) {
                rotationangleradians = 0;
                rotationangledegrees = 0;
            }
        }
        ImGui::Text("%i", rotationangledegrees);
        ImGuiExtensions::ADIShowTooltipFor("ControlRotationAngle");
        NewLine(5.0f);

        if (haveXYZ) {
            DrawBarLabel("Point Cloud");
            NewLine(5.0f);
            if (ImGuiExtensions::ADIButton("Reset", true)) {
                PointCloudReset();
            }
            ImGuiExtensions::ADIShowTooltipFor("ControlPCReset");

            // Temporarily disable point size adjustment given that
            //  point size can impact performance negatively on some systems
            //NewLine(5.0f);
            //ImGui::SliderInt("Point Size", &m_point_size, 1, 10,
            //                 "Point Size: %d px");

            NewLine(5.0f);
        }

        if (haveXYZ) {

            static uint32_t selected;

            ImGui::RadioButton("Depth Colour", selected == 0);
            if (ImGui::IsItemClicked())
                selected = 0;
            ImGuiExtensions::ADIShowTooltipFor("ControlPCDepthColor");
            if (haveAB) {
                ImGui::RadioButton("AB Colour", selected == 1);
                if (ImGui::IsItemClicked())
                    selected = 1;
                ImGuiExtensions::ADIShowTooltipFor("ControlPCABColor");
            }
            ImGui::RadioButton("Solid Colour", selected == 2);
            if (ImGui::IsItemClicked())
                selected = 2;
            ImGuiExtensions::ADIShowTooltipFor("ControlPCSolidColor");
#ifdef WITH_RGB_SUPPORT
            if (m_view_instance->m_rgbThreadCreated) {
                ImGui::RadioButton("RGB Colour", selected == 3);
                if (ImGui::IsItemClicked())
                    selected = 3;
                ImGuiExtensions::ADIShowTooltipFor("ControlPCRGBColor");
            } else if (selected == 3) {
                selected = 0; // Fall back to depth colour if RGB unavailable
            }
#endif // WITH_RGB_SUPPORT

            m_view_instance->setPointCloudColour(selected);

            NewLine(5.0f);
        }

        if (haveDepth) {
            DrawBarLabel("Depth");
            NewLine(5.0f);
            // Numeric entry for the depth range (mm) the depth-window colormap
            // spans; typeable boxes with +/- step buttons, applied live.
            ImGui::TextColored(ImVec4(0.7f, 0.7f, 0.7f, 1.0f),
                               "Min/Max: visualization only");
            int dMin = m_view_instance->minRange;
            int dMax = m_view_instance->maxRange;
            bool changed = false;
            ImGui::PushItemWidth(120.0f);
            if (ImGui::InputInt("Min (mm)", &dMin, 50, 500))
                changed = true;
            if (ImGui::InputInt("Max (mm)", &dMax, 50, 500))
                changed = true;
            ImGui::PopItemWidth();
            if (changed) {
                if (dMin < 0)
                    dMin = 0;
                if (dMax <= dMin)
                    dMax = dMin + 1;
                m_view_instance->minRange = dMin;
                m_view_instance->maxRange = dMax;
            }
            NewLine(5.0f);
        }

        if (haveAB) {
            DrawBarLabel("Active Brightness");
            NewLine(5.0f);
            bool logImage = m_view_instance->getLogImage();
            bool autoScale = m_view_instance->getAutoScale();

            ImGui::Checkbox("Auto-scale", &autoScale);
            ImGuiExtensions::ADIShowTooltipFor("ControlABAutoScale");
            if (autoScale == false) {
                logImage = false;
            }

            NewLine(5.0f);
            if (autoScale == false) {
                ImGui::BeginDisabled();
            }
            ImGui::Checkbox("Log Image", &logImage);
            ImGuiExtensions::ADIShowTooltipFor("ControlABLogImage");
            if (autoScale == false) {
                ImGui::EndDisabled();
            }

            m_view_instance->setLogImage(logImage);
            m_view_instance->setAutoScale(autoScale);
            NewLine(5.0f);
        }

        if (!m_off_line) {
            DrawBarLabel("Configuration Parameters");
            NewLine(5.0f);
            ShowIniWindow();
        }
    }

    ImGui::End();
}

void ADIMainWindow::IniParamWarn(std::string variable, std::string validVal) {

    ImGui::OpenPopup("Ini Error Modal");

    if (ImGui::BeginPopupModal("Ini Error Modal", NULL,
                               ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::TextUnformatted(validVal.c_str());

        if (ImGui::Button("OK")) {
            ImGui::CloseCurrentPopup();
        }
        ImGuiExtensions::ADIShowTooltipFor("ModalOK");

        ImGui::EndPopup(); // Required
    }
}

bool ADIMainWindow::EntryInt32_t(const char *label, int32_t &input,
                                 const int32_t min, const int32_t max) {
    int32_t previous = input;
    if (ImGui::InputInt(label, &input)) {
        if (input < min || input > max) {
            input = previous;
            std::string warn = "Valid values are between " +
                               std::to_string(min) + " and " +
                               std::to_string(max);
            IniParamWarn(label, warn.c_str());
        }
    }

    return previous != input;
}

void ADIMainWindow::LoadIniParamsForMode(uint16_t mode, IniParamState &st) {
    if (st.loaded) {
        return;
    }
    std::map<std::string, std::string> params;
    if (GetActiveCamera()->getDepthParamtersMap(mode, params) !=
        aditof::Status::OK) {
        LOG(ERROR) << "Could not get ini params for mode " << (int)mode;
        return;
    }
    // Mode fusion params are kept apart from the standard ones.
    std::map<std::string, std::string> fusionParams;
    if (GetActiveCamera()->getDepthAlgorithmParams(
            aditof::DepthAlgorithm::ModeFusion, mode, fusionParams) ==
        aditof::Status::OK) {
        params.insert(fusionParams.begin(), fusionParams.end());
    }
    auto getf = [&](const char *k) -> int32_t {
        auto it = params.find(k);
        if (it == params.end() || it->second.empty())
            return 0;
        try {
            return static_cast<int32_t>(std::round(std::stof(it->second)));
        } catch (const std::exception &) {
            return 0;
        }
    };
    st.abThreshMin = getf("abThreshMin");
    st.confThresh = getf("confThresh");
    st.radialThreshMin = getf("radialThreshMin");
    st.radialThreshMax = getf("radialThreshMax");
    st.jblfApplyFlag = (getf("jblfApplyFlag") == 1);
    st.jblfWindowSize = getf("jblfWindowSize");
    st.jblfGaussianSigma = getf("jblfGaussianSigma");
    st.jblfExponentialTerm = getf("jblfExponentialTerm");
    st.jblfMaxEdge = getf("jblfMaxEdge");
    st.jblfABThreshold = getf("jblfABThreshold");
    st.fps = getf("fps");
    st.lrInvalType = getf("lrInvalType");
    st.lrInvalThreshold = getf("lrInvalThreshold");
    st.lrInvalRadialMin = getf("lrInvalRadialMin");
    st.lrInvalRadialMax = getf("lrInvalRadialMax");
    st.edgeConfidenceEnabled = (getf("edgeConfidenceEnabled") == 1);
    st.twoLRFramesThreshold = getf("twoLRFramesThreshold");
    st.frameAOutputEnabled = (getf("frameAOutputEnabled") == 1);
    st.ABFusionEnabled = (getf("ABFusionEnabled") == 1);
    st.loaded = true;
}

void ADIMainWindow::ShowIniParamsForMode(uint16_t mode, IniParamState &st) {
    LoadIniParamsForMode(mode, st);

    ImGui::PushItemWidth(140 * m_dpi_scale_factor);

    EntryInt32_t("abThreshMin", st.abThreshMin, 0, 65535);
    ImGuiExtensions::ADIShowTooltipFor("ControlIniAbThreshMin");
    EntryInt32_t("confThresh", st.confThresh, 0, 255);
    ImGuiExtensions::ADIShowTooltipFor("ControlIniConfThresh");
    EntryInt32_t("radialThreshMin", st.radialThreshMin, 0,
                 65535); // TODO: compare min and max relative sizes
    ImGuiExtensions::ADIShowTooltipFor("ControlIniRadialThreshMin");
    EntryInt32_t("radialThreshMax", st.radialThreshMax, 0, 65535);
    ImGuiExtensions::ADIShowTooltipFor("ControlIniRadialThreshMax");
    ImGui::Checkbox("jblfApplyFlag", &st.jblfApplyFlag);
    ImGuiExtensions::ADIShowTooltipFor("ControlIniJblfApplyFlag");
    EntryInt32_t("jblfWindowSize", st.jblfWindowSize, 3,
                 7); // TODO: Make this a drop down
    ImGuiExtensions::ADIShowTooltipFor("ControlIniJblfWindowSize");
    EntryInt32_t("jblfGaussianSigma", st.jblfGaussianSigma, 0, 65535);
    ImGuiExtensions::ADIShowTooltipFor("ControlIniJblfGaussianSigma");
    EntryInt32_t("jblfExponentialTerm", st.jblfExponentialTerm, 0, 255);
    ImGuiExtensions::ADIShowTooltipFor("ControlIniJblfExponentialTerm");
    EntryInt32_t("jblfMaxEdge", st.jblfMaxEdge, 0, 64);
    ImGuiExtensions::ADIShowTooltipFor("ControlIniJblfMaxEdge");
    EntryInt32_t("jblfABThreshold", st.jblfABThreshold, 0, 131071);
    ImGuiExtensions::ADIShowTooltipFor("ControlIniJblfABThreshold");
    EntryInt32_t("fps", st.fps, 0, 60);
    ImGuiExtensions::ADIShowTooltipFor("ControlIniFps");

    const bool showFusion = !m_off_line && m_dms_enabled;
    const auto method =
        static_cast<aditof::ModeFusionMethod>(m_fusion_method_selection);
    if (showFusion) {
        NewLine(5.0f);
        DrawBarLabel("Mode Fusion");
        ImGuiExtensions::ADIShowTooltipFor("ControlIniModeFusion");
        NewLine(5.0f);
        switch (method) {
        case aditof::ModeFusionMethod::SrLr:
            ImGui::Checkbox("ABFusionEnabled", &st.ABFusionEnabled);
            break;
        case aditof::ModeFusionMethod::LrInvalidation:
            EntryInt32_t("lrInvalType", st.lrInvalType, 1, 4);
            EntryInt32_t("lrInvalThreshold", st.lrInvalThreshold, 0, 65535);
            EntryInt32_t("lrInvalRadialMin", st.lrInvalRadialMin, 0, 65535);
            EntryInt32_t("lrInvalRadialMax", st.lrInvalRadialMax, 0, 65535);
            ImGui::Checkbox("edgeConfidenceEnabled", &st.edgeConfidenceEnabled);
            break;
        case aditof::ModeFusionMethod::TwoLrFrames:
            EntryInt32_t("twoLRFramesThreshold", st.twoLRFramesThreshold, 0,
                         65535);
            ImGui::Checkbox("frameAOutputEnabled", &st.frameAOutputEnabled);
            break;
        default:
            break;
        }
    }

    ImGui::PopItemWidth();

    st.modified["abSumThresh"] =
        std::to_string(1.0f); // Unused, but needed for now.
    st.modified["abThreshMin"] = std::to_string(st.abThreshMin);
    st.modified["confThresh"] = std::to_string(st.confThresh);
    st.modified["radialThreshMin"] = std::to_string(st.radialThreshMin);
    st.modified["radialThreshMax"] = std::to_string(st.radialThreshMax);
    st.modified["jblfApplyFlag"] = std::to_string(st.jblfApplyFlag ? 1 : 0);
    st.modified["jblfWindowSize"] = std::to_string(st.jblfWindowSize);
    st.modified["jblfGaussianSigma"] = std::to_string(st.jblfGaussianSigma);
    st.modified["jblfExponentialTerm"] = std::to_string(st.jblfExponentialTerm);
    st.modified["jblfMaxEdge"] = std::to_string(st.jblfMaxEdge);
    st.modified["jblfABThreshold"] = std::to_string(st.jblfABThreshold);
    st.modified["fps"] = std::to_string(st.fps);

    if (showFusion) {
        switch (method) {
        case aditof::ModeFusionMethod::SrLr:
            st.modified["ABFusionEnabled"] = st.ABFusionEnabled ? "1" : "0";
            break;
        case aditof::ModeFusionMethod::LrInvalidation:
            st.modified["lrInvalType"] = std::to_string(st.lrInvalType);
            st.modified["lrInvalThreshold"] =
                std::to_string(st.lrInvalThreshold);
            st.modified["lrInvalRadialMin"] =
                std::to_string(st.lrInvalRadialMin);
            st.modified["lrInvalRadialMax"] =
                std::to_string(st.lrInvalRadialMax);
            st.modified["edgeConfidenceEnabled"] =
                st.edgeConfidenceEnabled ? "1" : "0";
            break;
        case aditof::ModeFusionMethod::TwoLrFrames:
            st.modified["twoLRFramesThreshold"] =
                std::to_string(st.twoLRFramesThreshold);
            st.modified["frameAOutputEnabled"] =
                st.frameAOutputEnabled ? "1" : "0";
            break;
        default:
            break;
        }
    }

    if (st.loaded && st.original.empty()) {
        st.original = st.modified;
    }
}

void ADIMainWindow::StageFusionParamEdits() {
    if (m_off_line || !m_dms_enabled || !GetActiveCamera()) {
        return;
    }
    static const char *fusionKeys[] = {
        "ABFusionEnabled",      "lrInvalType",        "lrInvalThreshold",
        "lrInvalRadialMin",     "lrInvalRadialMax",   "edgeConfidenceEnabled",
        "twoLRFramesThreshold", "frameAOutputEnabled"};
    for (const auto &entry : m_ini_by_mode) {
        if (!entry.second.loaded) {
            continue;
        }
        std::map<std::string, std::string> config;
        if (GetActiveCamera()->getDepthAlgorithmParams(
                aditof::DepthAlgorithm::ModeFusion, entry.first, config) !=
            aditof::Status::OK) {
            continue;
        }
        // Only values the user changed, so untouched params keep the config.
        for (const char *key : fusionKeys) {
            auto edited = entry.second.modified.find(key);
            if (edited == entry.second.modified.end()) {
                continue;
            }
            auto current = config.find(key);
            if (current != config.end() &&
                std::atof(current->second.c_str()) ==
                    std::atof(edited->second.c_str())) {
                continue;
            }
            m_pending_modified_by_mode[entry.first][key] = edited->second;
        }
    }
}

void ADIMainWindow::ShowIniWindow(bool showModify) {
    auto isLR = [this](uint16_t m) {
        return m_long_range_modes.count(static_cast<uint8_t>(m)) > 0;
    };

    // Build the selectable mode list: both halves during fusion, else the
    // single active/selected mode. Each mode keeps its own edited values.
    std::vector<uint16_t> modes;
    if (!m_off_line && m_dms_enabled) {
        uint16_t primaryMode = static_cast<uint16_t>(m_mode_selection);
        uint16_t secondMode =
            FusionUsesSecondMode()
                ? static_cast<uint16_t>(m_dms_second_mode_selection)
                : primaryMode;
        if (m_is_playing) {
            aditof::CameraDetails d;
            if (GetActiveCamera()->getDetails(d) == aditof::Status::OK &&
                d.mode >= 0) {
                primaryMode = static_cast<uint16_t>(d.mode);
            }
            secondMode = m_dms_active_second_mode;
        }
        modes.push_back(primaryMode);
        if (secondMode != primaryMode) {
            modes.push_back(secondMode);
        }
    } else {
        uint16_t m = static_cast<uint16_t>(m_mode_selection);
        if (m_is_playing) {
            aditof::CameraDetails d;
            if (GetActiveCamera()->getDetails(d) == aditof::Status::OK &&
                d.mode >= 0) {
                m = static_cast<uint16_t>(d.mode);
            }
        }
        modes.push_back(m);
    }

    // Radio buttons choose which mode's params are shown; both modes' edits
    // are retained in m_ini_by_mode across switches.
    if (modes.size() > 1) {
        if (m_ini_radio_sel < 0 || m_ini_radio_sel >= (int)modes.size()) {
            m_ini_radio_sel = 0;
        }
        for (int i = 0; i < (int)modes.size(); ++i) {
            std::string label = "Mode " + std::to_string((int)modes[i]) + " (" +
                                (isLR(modes[i]) ? "LR" : "SR") + ")";
            if (i > 0) {
                ImGui::SameLine();
            }
            ImGui::RadioButton(label.c_str(), &m_ini_radio_sel, i);
        }
        NewLine(5.0f);
    } else {
        m_ini_radio_sel = 0;
    }

    uint16_t selMode = modes[m_ini_radio_sel];
    ShowIniParamsForMode(selMode, m_ini_by_mode[selMode]);

    if (showModify) {
        if (ImGuiExtensions::ADIButton("Reset Parameters", m_is_open_device)) {
            auto camera = GetActiveCamera();
            if (camera) {
                camera->resetDepthProcessParams();
                m_ini_params.clear();
                m_ini_by_mode.clear();
            }
        }
        ImGuiExtensions::ADIShowTooltipFor("ControlIniResetParameters");

        if (ImGui::Button("Modify") && !getIsWorking()) {
            // Stage every mode that has been viewed/edited (both halves if the
            // user switched the radio and tuned each); applied during the next
            // PrepareCamera() (device stopped), then contexts rebuilt from config.
            m_pending_modified_by_mode.clear();
            for (uint16_t mode : modes) {
                auto it = m_ini_by_mode.find(mode);
                if (it != m_ini_by_mode.end() && it->second.loaded) {
                    m_pending_modified_by_mode[mode] = it->second.modified;
                }
            }
            setWorkingLabel("Applying parameters...");
            setIsWorking(true);
            m_modify_pending = true;
            m_modify_pending_frames = 1;
        }
        ImGuiExtensions::ADIShowTooltipFor("ControlIniModify");
    }
}
