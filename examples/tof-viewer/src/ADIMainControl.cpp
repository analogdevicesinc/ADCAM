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
#include "aditof/utils.h"

#include <aditof/log.h>

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

            static std::string filePath = "";

            cameraButton(m_base_file_name);
            ImGuiExtensions::ADIShowTooltipFor("ControlCapture");

            ImGui::SameLine(0.0f, 10.0f);

            if (DrawIconButton(
                    "Record",
                    [](ImDrawList *dl, ImVec2 min, ImVec2 max) {
                        ImVec2 center = ImVec2((min.x + max.x) * 0.5f,
                                               (min.y + max.y) * 0.5f);
                        float radius = (max.x - min.x) * 0.2f;

                        // Draw a white circle in the center for the record icon
                        dl->AddCircleFilled(center, radius, IM_COL32_WHITE);
                    },
                    (!m_recordingActive) ? IM_COL32(200, 0, 0, 255)
                                         : IM_COL32(0, 200, 0, 255))) {

                if (!m_recordingActive) {

                    aditof::Status status =
                        GetActiveCamera()->startRecording(filePath);
                    if (status == aditof::Status::OK) {
                        m_view_instance->m_ctrl->setPreviewRate(
                            m_fps_expected, PREVIEW_FRAME_RATE);
                        m_recordingActive = true;
                        LOG(INFO) << "Recording to " << filePath.c_str();
                    } else {
                        m_view_instance->m_ctrl->setPreviewRate(m_fps_expected,
                                                                m_fps_expected);
                        LOG(ERROR) << "Unable to start recording.";
                        filePath = "";
                        m_recordingActive = false;
                    }
                } else {
                    aditof::Status status = GetActiveCamera()->stopRecording();
                    if (status == aditof::Status::OK) {
                        LOG(INFO) << "Recording stopped.";
                        filePath = "";
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
                setWorkingLabel("Stopping camera...");
                setIsWorking(true);
                m_stop_filepath = filePath;
                m_stop_pending = true;
                m_stop_pending_frames = 1;
            }
            ImGuiExtensions::ADIShowTooltipFor("ControlStop");

            ImGui::SameLine(0.0f, 10.0f);

        } else { // Offline

            uint32_t max_frame_count;
            GetActiveCamera()->getSensor()->getFrameCount(max_frame_count);

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

            m_view_instance->setPointCloudColour(selected);

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

void ADIMainWindow::ShowIniWindow(bool showModify) {
    aditof::Status status;

    static int32_t abThreshMin = 0;
    static int32_t confThresh = 0;
    static int32_t radialThreshMin = 0;
    static int32_t radialThreshMax = 0;
    static bool jblfApplyFlag = false;
    static int32_t jblfWindowSize = 0;
    static int32_t jblfGaussianSigma = 0;
    static int32_t jblfExponentialTerm = 0;
    static int32_t jblfMaxEdge = 0;
    static int32_t jblfABThreshold = 0;
    static int32_t fps = 0;

    if (m_ini_params.empty()) {
        status = GetActiveCamera()->getDepthParamtersMap(m_mode_selection,
                                                         m_ini_params);
        if (status != aditof::Status::OK) {
            LOG(ERROR) << "Could not get ini params";
        } else {
            abThreshMin = std::stof(m_ini_params["abThreshMin"]);
            confThresh = std::stof(m_ini_params["confThresh"]);
            radialThreshMin = std::stof(m_ini_params["radialThreshMin"]);
            radialThreshMax = std::stof(m_ini_params["radialThreshMax"]);
            jblfApplyFlag = (static_cast<int>(std::round(std::stof(
                                 m_ini_params["jblfApplyFlag"]))) == 1);
            jblfWindowSize = static_cast<int>(
                std::round(std::stof(m_ini_params["jblfWindowSize"])));
            jblfGaussianSigma = std::stof(m_ini_params["jblfGaussianSigma"]);
            jblfExponentialTerm =
                std::stof(m_ini_params["jblfExponentialTerm"]);
            jblfMaxEdge = std::stof(m_ini_params["jblfMaxEdge"]);
            jblfABThreshold = std::stof(m_ini_params["jblfABThreshold"]);
            fps = static_cast<int>(std::round(std::stof(m_ini_params["fps"])));
        }
    }

    ImGui::PushItemWidth(140 * m_dpi_scale_factor);

    EntryInt32_t("abThreshMin", abThreshMin, 0, 65535);
    ImGuiExtensions::ADIShowTooltipFor("ControlIniAbThreshMin");
    EntryInt32_t("confThresh", confThresh, 0, 255);
    ImGuiExtensions::ADIShowTooltipFor("ControlIniConfThresh");
    EntryInt32_t("radialThreshMin", radialThreshMin, 0,
                 65535); // TODO: compare min and max relative sizes
    ImGuiExtensions::ADIShowTooltipFor("ControlIniRadialThreshMin");
    EntryInt32_t("radialThreshMax", radialThreshMax, 0, 65535);
    ImGuiExtensions::ADIShowTooltipFor("ControlIniRadialThreshMax");
    ImGui::Checkbox("jblfApplyFlag", &jblfApplyFlag);
    ImGuiExtensions::ADIShowTooltipFor("ControlIniJblfApplyFlag");
    EntryInt32_t("jblfWindowSize", jblfWindowSize, 3,
                 7); // TODO: Make this a drop down
    ImGuiExtensions::ADIShowTooltipFor("ControlIniJblfWindowSize");
    EntryInt32_t("jblfGaussianSigma", jblfGaussianSigma, 0, 65535);
    ImGuiExtensions::ADIShowTooltipFor("ControlIniJblfGaussianSigma");
    EntryInt32_t("jblfExponentialTerm", jblfExponentialTerm, 0, 255);
    ImGuiExtensions::ADIShowTooltipFor("ControlIniJblfExponentialTerm");
    EntryInt32_t("jblfMaxEdge", jblfMaxEdge, 0, 64);
    ImGuiExtensions::ADIShowTooltipFor("ControlIniJblfMaxEdge");
    EntryInt32_t("jblfABThreshold", jblfABThreshold, 0, 131071);
    ImGuiExtensions::ADIShowTooltipFor("ControlIniJblfABThreshold");
    EntryInt32_t("fps", fps, 0, 60);
    ImGuiExtensions::ADIShowTooltipFor("ControlIniFps");

    // modify ini params
    m_modified_ini_params["abSumThresh"] =
        std::to_string(1.0f); // Unused, but needed for now.
    m_modified_ini_params["abThreshMin"] = std::to_string(abThreshMin);
    m_modified_ini_params["confThresh"] = std::to_string(confThresh);
    m_modified_ini_params["radialThreshMin"] = std::to_string(radialThreshMin);
    m_modified_ini_params["radialThreshMax"] = std::to_string(radialThreshMax);
    if (jblfApplyFlag) {
        m_modified_ini_params["jblfApplyFlag"] = std::to_string(1);
    } else {
        m_modified_ini_params["jblfApplyFlag"] = std::to_string(0);
    }
    m_modified_ini_params["jblfWindowSize"] = std::to_string(jblfWindowSize);
    m_modified_ini_params["jblfGaussianSigma"] =
        std::to_string(jblfGaussianSigma);
    m_modified_ini_params["jblfExponentialTerm"] =
        std::to_string(jblfExponentialTerm);
    m_modified_ini_params["jblfMaxEdge"] = std::to_string(jblfMaxEdge);
    m_modified_ini_params["jblfABThreshold"] = std::to_string(jblfABThreshold);
    m_modified_ini_params["fps"] = std::to_string(fps);

    if (showModify) {
        if (ImGuiExtensions::ADIButton("Reset Parameters", m_is_open_device)) {
            auto camera = GetActiveCamera();
            if (camera) {
                camera->resetDepthProcessParams();
                m_ini_params.clear();
            }
        }
        ImGuiExtensions::ADIShowTooltipFor("ControlIniResetParameters");

        if (ImGui::Button("Modify") && !getIsWorking()) {
            setWorkingLabel("Applying parameters...");
            setIsWorking(true);
            m_modify_pending = true;
            m_modify_pending_frames = 1;
        }
        ImGuiExtensions::ADIShowTooltipFor("ControlIniModify");
    }
}