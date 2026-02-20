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
#include "ADIOpenFile.h"
#include "aditof/status_definitions.h"
#include "aditof/version-kit.h"
#include "aditof/version.h"
#include <cmath>
#include <fcntl.h>
#include <fstream>

#include <aditof/log.h>
#include <iostream>
#include <stdio.h>

#include <aditof/system.h>
#include <json.h>

#include "roboto-bold.h"
#include "roboto-regular.h"
#include "roboto-semicondensed-bold.h"

#if defined(_WIN32) || defined(__WIN32__) || defined(WIN32)
#include "psapi.h"
#include <direct.h>
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

#include "backends/imgui_impl_glfw.h"
#include "backends/imgui_impl_opengl3.h"

// [Win32] Our example includes a copy of glfw3.lib pre-compiled with VS2010 to
// maximize ease of testing and compatibility with old VS compilers. To link
// with VS2010-era libraries, VS2015+ requires linking with
// legacy_stdio_definitions.lib, which we do using this pragma. Your own project
// should not be affected, as you are likely to link with a newer binary of GLFW
// that is adequate for your version of Visual Studio.
#if defined(_MSC_VER) && (_MSC_VER >= 1900) &&                                 \
    !defined(IMGUI_DISABLE_WIN32_FUNCTIONS)
#pragma comment(lib, "legacy_stdio_definitions")
#endif

using namespace adiMainWindow;

extern ImFont *g_font_regular;
extern ImFont *g_font_bold;
extern ImFont *g_font_bold_large;

ADIMainWindow::ADIMainWindow() : m_skip_network_cameras(true) {
    /********************/
    struct stat info;
    std::string folderName = "log";
    if (stat(folderName.c_str(), &info) !=
        0) { // If no folder named log is found
#ifdef _WIN32
        if (_mkdir("log")) { // Create local folder where all logs will be filed
#elif __linux__
        if (mkdir("log",
                  0777)) { // Create local folder where all logs will be filed
#endif
            LOG(ERROR) << "Could not create folder " << folderName;
        } else {
            LOG(INFO) << "Log folder created with name: " << folderName;
        }
    }
    std::string wholeLogPath;
    char timebuff[100];
    time_t timeNow = time(0);
    struct tm *timeinfo;
    time(&timeNow);
    timeinfo = localtime(&timeNow);
    strftime(timebuff, sizeof(timebuff), "%Y%m%d_%H%M%S", timeinfo);
    // Concatenate the whole path
    wholeLogPath = folderName;
#ifdef _WIN32
    wholeLogPath += "\\"; // Ensure the path ends with a slash
#elif __linux__
    wholeLogPath += "/";   // Ensure the path ends with a slash
#endif
    wholeLogPath += "log_" + std::string(timebuff) + ".txt";

    /********************/
    m_file_stream =
        freopen(wholeLogPath.c_str(), "w", stderr); // Added missing pointer
    setvbuf(m_file_stream, 0, _IONBF, 0);           // No Buffering
    m_file_input = fopen(wholeLogPath.c_str(), "r");

    //Parse config file for this application
    //Parse config.json
    std::ifstream ifs(DEFAULT_TOOLS_CONFIG_FILENAME);
    std::string content((std::istreambuf_iterator<char>(ifs)),
                        (std::istreambuf_iterator<char>()));
    json_object *config_json = json_tokener_parse(content.c_str());

    if (config_json != NULL) {
        // Get option to look or not for network cameras
        json_object *json_skip_network_cameras = NULL;
        if (json_object_object_get_ex(config_json, "skip_network_cameras",
                                      &json_skip_network_cameras)) {
            if (json_object_is_type(json_skip_network_cameras,
                                    json_type_string)) {
                const char *valuestring =
                    json_object_get_string(json_skip_network_cameras);
                if (valuestring != NULL) {
                    std::string value = valuestring;
                    if (value == "on") {
                        m_skip_network_cameras = true;
                    } else if (value == "off") {
                        m_skip_network_cameras = false;
                    } else {
                        LOG(WARNING)
                            << "Invalid value for 'skip_network_cameras'. "
                               "Accepted values: on, off";
                    }
                }
            }
        }

        // Get the IP address of the network camera to which the application should try to connect to
        json_object *json_camera_ip = NULL;
        if (json_object_object_get_ex(config_json, "camera_ip",
                                      &json_camera_ip)) {
            if (json_object_is_type(json_camera_ip, json_type_string)) {
                const char *valuestring =
                    json_object_get_string(json_camera_ip);
                if (valuestring != NULL) {
                    m_cameraIp = valuestring;
                    if (!m_cameraIp.empty()) {
                        m_cameraIp = "ip:" + m_cameraIp;
                    }
                }
            }
        }

        json_object_put(config_json);
    }
    if (!ifs.fail()) {
        ifs.close();
    }
    
    // Read tooltip delay from config
    ifs.open(DEFAULT_TOOLS_CONFIG_FILENAME);
    if (ifs.good()) {
        content.assign((std::istreambuf_iterator<char>(ifs)),
                       (std::istreambuf_iterator<char>()));
        config_json = json_tokener_parse(content.c_str());
        
        if (config_json != NULL) {
            json_object *json_tooltip_delay = NULL;
            if (json_object_object_get_ex(config_json, "tooltip_delay_seconds",
                                          &json_tooltip_delay)) {
                if (json_object_is_type(json_tooltip_delay, json_type_double) ||
                    json_object_is_type(json_tooltip_delay, json_type_int)) {
                    double delay = json_object_get_double(json_tooltip_delay);
                    if (delay >= 0.0) {
                        ImGuiExtensions::ADISetTooltipDelay(static_cast<float>(delay));
                    }
                }
            }

            json_object *json_save_folder = NULL;
            if (json_object_object_get_ex(config_json, "recordings_folder",
                                          &json_save_folder)) {
                if (json_object_is_type(json_save_folder, json_type_string)) {
                    const char *recording_folder = json_object_get_string(json_save_folder);
                    if (recording_folder != NULL) {
                        m_recording_path = recording_folder;
                    } else {
                        m_recording_path = ".";
                    }
                }
            }

            json_object_put(config_json);
        }
        ifs.close();
    }
    
    // Initialize UI tooltips
    InitializeTooltips();
}

void ADIMainWindow::InitializeTooltips() {
    using namespace ImGuiExtensions;
    
    // ============ Wizard: Camera Selection ============
    ADIRegisterTooltip("WizardSavedStream", "Use a saved stream file (.adcam) for playback");
    ADIRegisterTooltip("WizardLiveCamera", "Use a live camera device for real-time capture");
    
    // ============ Wizard: Offline Mode ============
    ADIRegisterTooltip("WizardOfflineOpen", "Open a saved stream file (.adcam) for playback");
    ADIRegisterTooltip("WizardOfflineStartStreaming", "Start playback of the loaded stream file");
    ADIRegisterTooltip("WizardOfflineClose", "Close the current playback file");
    ADIRegisterTooltip("WizardOfflineSaveAllFrames", "When enabled, all frames in the file will be saved when capturing");

    // ============ Wizard: Online Mode ============
    ADIRegisterTooltip("WizardOnlineCamera", "Select which camera device to use");
    ADIRegisterTooltip("WizardOnlineRefresh", "Refresh the list of available camera devices");
    ADIRegisterTooltip("WizardOnlineOpen", "Initialize and open the selected camera device");
    ADIRegisterTooltip("WizardOnlineClose", "Close the current camera device");
    ADIRegisterTooltip("WizardOnlineSelectMode", "Select camera operating mode (resolution and frame format)");
    ADIRegisterTooltip("WizardOnlineLoadConfig", "Load depth processing configuration from JSON file");
    ADIRegisterTooltip("WizardOnlineResetParameters", "Reset all depth processing parameters to factory defaults");
    ADIRegisterTooltip("WizardOnlinePreviewOn", "Enable live preview - reduces frame rate during parameter adjustment");
    ADIRegisterTooltip("WizardOnlinePreviewOff", "Disable preview - full frame rate, but no display during parameter changes");
    ADIRegisterTooltip("WizardOnlineStartStreaming", "Begin capturing and displaying frames from the camera");

    // ============ Control Window: Configuration ============
    ADIRegisterTooltip("ControlLoadConfig", "Load camera depth processing configuration from JSON file");
    ADIRegisterTooltip("ControlSaveConfig", "Save current depth processing configuration to JSON file");
    
    // ============ Control Window: Playback Controls ============
    ADIRegisterTooltip("ControlCapture", "Capture and save the current frame or stream to disk");
    ADIRegisterTooltip("ControlRecord", "Start/stop recording frames to an .adcam file");
    ADIRegisterTooltip("ControlStop", "Stop camera capture and return to wizard");
    ADIRegisterTooltip("ControlJumpToStart", "Jump to the first frame in the recording");
    ADIRegisterTooltip("ControlStepBackward", "Go to the previous frame");
    ADIRegisterTooltip("ControlStepForward", "Go to the next frame");
    ADIRegisterTooltip("ControlJumpToEnd", "Jump to the last frame in the recording");
    ADIRegisterTooltip("ControlFrameSlider", "Seek to a specific frame number");
    ADIRegisterTooltip("ControlSaveAllFrames", "Save all frames when capturing (offline mode only)");
    
    // ============ Control Window: Point Cloud ============
    ADIRegisterTooltip("ControlRotatePlus", "Rotate the point cloud view by 90 degrees clockwise");
    ADIRegisterTooltip("ControlRotationAngle", "Current rotation angle in degrees");
    ADIRegisterTooltip("ControlPCReset", "Reset point cloud view to default position and orientation");
    ADIRegisterTooltip("ControlPCDepthColor", "Color point cloud based on depth values");
    ADIRegisterTooltip("ControlPCABColor", "Color point cloud based on active brightness (AB) values");
    ADIRegisterTooltip("ControlPCSolidColor", "Display point cloud in solid white color");
    
    // ============ Control Window: Active Brightness (AB) ============
    ADIRegisterTooltip("ControlABAutoScale", "Automatically scale AB image brightness based on frame content");
    ADIRegisterTooltip("ControlABLogImage", "Apply logarithmic scaling to AB image (requires auto-scale)");
    
    // ============ Control Window: Configuration Parameters ============
    ADIRegisterTooltip("ControlIniAbThreshMin", "Minimum active brightness threshold (0-65535)");
    ADIRegisterTooltip("ControlIniConfThresh", "Confidence threshold for valid depth measurements (0-255)");
    ADIRegisterTooltip("ControlIniRadialThreshMin", "Minimum radial distance threshold in mm (0-65535)");
    ADIRegisterTooltip("ControlIniRadialThreshMax", "Maximum radial distance threshold in mm (0-65535)");
    ADIRegisterTooltip("ControlIniJblfApplyFlag", "Enable Joint Bilateral Filter for noise reduction");
    ADIRegisterTooltip("ControlIniJblfWindowSize", "Joint Bilateral Filter window size: 3, 5, or 7 pixels");
    ADIRegisterTooltip("ControlIniJblfGaussianSigma", "Gaussian sigma for spatial filtering (0-65535)");
    ADIRegisterTooltip("ControlIniJblfExponentialTerm", "Exponential term for range filtering (0-255)");
    ADIRegisterTooltip("ControlIniJblfMaxEdge", "Maximum edge threshold for filtering (0-64)");
    ADIRegisterTooltip("ControlIniJblfABThreshold", "Active brightness threshold for JBLF (0-131071)");
    ADIRegisterTooltip("ControlIniFps", "Target frames per second (0-60)");
    ADIRegisterTooltip("ControlIniResetParameters", "Reset all depth processing parameters to defaults");
    ADIRegisterTooltip("ControlIniModify", "Apply modified parameters and restart capture");
    
    // ============ Help Window ============
    ADIRegisterTooltip("HelpClose", "Close the help window");
    
    // ============ Modal Dialogs ============
    ADIRegisterTooltip("ModalOK", "Acknowledge and close this message");
    
    // ============ Info Window ============
    ADIRegisterTooltip("InfoDisplayMode", "Current camera mode and resolution");
    ADIRegisterTooltip("InfoFPS", "Actual frames per second being captured");
    ADIRegisterTooltip("InfoFrameCount", "Total number of frames processed");
}

ADIMainWindow::~ADIMainWindow() {

    if (m_is_playing) {
        CameraStop();
    }

    // Clean up persistent OpenGL buffers for Jetson optimization
    if (m_buffers_initialized) {
        glDeleteVertexArrays(1, &m_persistent_vao);
        glDeleteBuffers(1, &m_persistent_vbo);
        m_buffers_initialized = false;
    }

    // imGUI disposing
    //ImGui::GetIO().IniFilename = NULL;
    ImGui_ImplOpenGL3_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImPlot::DestroyContext();
    ImGui::DestroyContext();

    glfwDestroyWindow(window);
    glfwTerminate();
    if (initCameraWorker.joinable()) {
        initCameraWorker.join();
    }
    if (m_modifyWorker.joinable()) {
        m_modifyWorker.join();
    }
    //fclose(stderr);
}

void ADIMainWindow::CustomizeMenus() {
    ImGuiStyle &style = ImGui::GetStyle();

    // Set the color of the border
    style.Colors[ImGuiCol_Border] =
        ImVec4(0.7f, 0.7f, 0.7f, 1.0f); // (R, G, B, A);
}

static void glfw_error_callback(int error, const char *description) {
    fprintf(stderr, "Glfw Error %d: %s\n", error, description);
}

bool ADIMainWindow::StartImGUI(const ADIViewerArgs &args) {
    // Setup window
    glfwSetErrorCallback(glfw_error_callback); //Error Management
    if (!glfwInit()) {
        return false;
    }

    // Decide GL+GLSL versions
    // GL 3.0 + GLSL 130
    const char *glsl_version = "#version 130";
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE); // 3.2+
    // only glfwWindowHint(GLFW_OPENGL_FORWARD_COMPAT, GL_TRUE); // 3.0+ only
    glfwWindowHint(GLFW_DEPTH_BITS, 24);

    std::string version = aditof::getKitVersion();
    std::string _title = "Analog Devices, Inc. Time of Flight Main Window v" +
                         version; //Default name

    // Create window with graphics context
    glfwWindowHint(GLFW_RESIZABLE, GL_TRUE);

    m_dict_win_position["main"].width = 1580.0f;
    m_dict_win_position["main"].height = 1080.0f;

    window = glfwCreateWindow(m_dict_win_position["main"].width,
                              m_dict_win_position["main"].height,
                              _title.c_str(), NULL, NULL);

    if (window == NULL) {
        return false;
    }

    glfwMakeContextCurrent(window);

    glfwSwapInterval(1); // Enable vsync

    // Initialize OpenGL loader
#if defined(IMGUI_IMPL_OPENGL_LOADER_GL3W)
    bool err = gl3wInit() != 0;
#elif defined(IMGUI_IMPL_OPENGL_LOADER_GLEW)
    bool err = glewInit() != GLEW_OK;
#elif defined(IMGUI_IMPL_OPENGL_LOADER_GLAD)
    bool err = gladLoadGL((GLADloadfunc)glfwGetProcAddress) == 0;
#else
    bool err = false; // If you use IMGUI_IMPL_OPENGL_LOADER_CUSTOM, your loader
                      // is likely to requires some form of initialization.
#endif
    if (err) {
        fprintf(stderr, "Failed to initialize OpenGL loader!\n");
        return false;
    }

    // Setup Dear ImGui context
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImPlot::CreateContext(); // ← REQUIRED for ImPlot
    ImGuiIO &io = ImGui::GetIO();
    (void)io;
    io.ConfigFlags |=
        ImGuiConfigFlags_NavEnableKeyboard; // Enable Keyboard Controls
    //io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;			// Enable Docking
    //io.ConfigFlags |= ImGuiConfigFlags_ViewportsEnable;         // Enable Multi-Viewport / Platform Windows
    // Keyboard Controls io.ConfigFlags |= ImGuiConfigFlags_NavEnableGamepad; //
    // Enable Gamepad Controls

    if (args.HighDpi) {
        m_dpi_scale_factor = HIGHDPISCALAR;
    } else {
        m_dpi_scale_factor = NORMALDPISCALAR;
    }
    SetDpi();

    m_dict_win_position["info"].x = 5.0f;
    m_dict_win_position["info"].y = 25.0f;
    m_dict_win_position["info"].width = 300.0f;
    m_dict_win_position["info"].height = 800.0f;

    m_dict_win_position["control"].x = m_dict_win_position["info"].width + 10;
    m_dict_win_position["control"].y = m_dict_win_position["info"].y;
    m_dict_win_position["control"].width = m_dict_win_position["info"].width;
    m_dict_win_position["control"].height = m_dict_win_position["info"].height;

    m_dict_win_position["fr-main"].x =
        WindowCalcX(m_dict_win_position["control"], 10.0f);
    m_dict_win_position["fr-main"].y = m_dict_win_position["info"].y;
    m_dict_win_position["fr-main"].width = 640.0f;
    m_dict_win_position["fr-main"].height = 640.0f;

    m_dict_win_position["fr-sub1"].x =
        WindowCalcX(m_dict_win_position["fr-main"], 10.0f);
    m_dict_win_position["fr-sub1"].y = m_dict_win_position["fr-main"].y;
    m_dict_win_position["fr-sub1"].width = 256.0f;
    m_dict_win_position["fr-sub1"].height = 256.0f;

    m_dict_win_position["fr-sub2"].x = m_dict_win_position["fr-sub1"].x;
    m_dict_win_position["fr-sub2"].y =
        WindowCalcY(m_dict_win_position["fr-sub1"], 10.0f);
    m_dict_win_position["fr-sub2"].width = 256.0f;
    m_dict_win_position["fr-sub2"].height = 256.0f;

    m_dict_win_position["plotA"].x = m_dict_win_position["fr-main"].x;
    m_dict_win_position["plotA"].y =
        WindowCalcY(m_dict_win_position["fr-main"], 10.0f);
    m_dict_win_position["plotA"].width = m_dict_win_position["fr-main"].width;
    m_dict_win_position["plotA"].height = 315.0f;

    m_xyz_position = &m_dict_win_position["fr-main"];
    m_ab_position = &m_dict_win_position["fr-sub1"];
    m_depth_position = &m_dict_win_position["fr-sub2"];

    // Setup Dear ImGui style
    //ImGui::StyleColorsDark();
    //OR
    ImGui::StyleColorsClassic();
    CustomizeMenus();

    // Setup Platform/Renderer bindings
    ImGui_ImplGlfw_InitForOpenGL(window, true);
    ImGui_ImplOpenGL3_Init(glsl_version);

    RefreshDevices();

    /**************/

    return true;
}

void ADIMainWindow::OpenGLCleanUp() {
    glDeleteTextures(1, &m_gl_ab_video_texture);
    glDeleteTextures(1, &m_gl_depth_video_texture);
    glDeleteTextures(1, &m_gl_pointcloud_video_texture);
    //glDeleteTextures(1, &m_gl_pc_colourTex); // TODO: Find out why deleting this causes issues.
    //glDeleteTextures(1, &m_gl_pc_depthTex);  // TODO: Find out why deleting this causes issues.
    glDeleteVertexArrays(1, &m_view_instance->vertexArrayObject);
    glDeleteBuffers(1, &m_view_instance->vertexBufferObject);

    // Clean up persistent point cloud buffers
    if (m_buffers_initialized) {
        glDeleteVertexArrays(1, &m_persistent_vao);
        glDeleteBuffers(1, &m_persistent_vbo);
        m_persistent_vao = 0;
        m_persistent_vbo = 0;
        m_last_vertex_size = 0;
        m_buffers_initialized = false;
    }

    glDeleteProgram(m_view_instance->pcShader.Id());
    m_view_instance->pcShader.RemoveShaders();
}

ImFont *ADIMainWindow::LoadFont(const unsigned char *ext_font,
                                const unsigned int ext_font_len,
                                const float size) {
    ImFont *font;
    bool isFontLoaded = false;
    unsigned char *buffer = new (std::nothrow) unsigned char[ext_font_len];
    if (buffer == nullptr) {
        LOG(ERROR) << "Failed to allocate memory for Roboto Regular font!";
    } else {
        std::memcpy(buffer, ext_font, ext_font_len);
        font = ImGui::GetIO().Fonts->AddFontFromMemoryTTF(
            buffer, ext_font_len, size * m_dpi_scale_factor);
        if (!font) {
            LOG(ERROR) << "Failed to load font!";
            delete[] buffer; // Clean up memory if font loading fails
        }
        isFontLoaded = true;
    }
    if (!isFontLoaded) {
        font = ImGui::GetIO().FontDefault;
    }

    return font;
}

void ADIMainWindow::SetDpi() {
    ImGui::GetStyle().ScaleAllSizes(m_dpi_scale_factor);

    // ImGui doesn't automatically scale fonts, so we have to do that ourselves
    //
    ImFontConfig fontConfig;
    constexpr float defaultFontSize = 13.0f;
    fontConfig.SizePixels = defaultFontSize * m_dpi_scale_factor;
    ImGui::GetIO().Fonts->AddFontDefault(&fontConfig);

    g_font_regular =
        LoadFont(Roboto_Regular_ttf, Roboto_Regular_ttf_len, 12.0f);
    g_font_bold = LoadFont(Roboto_Bold_ttf, Roboto_Bold_ttf_len, 12.0f);
    g_font_bold_large = LoadFont(Roboto_Bold_ttf, Roboto_Bold_ttf_len, 18.0f);

    glfwGetWindowSize(window, &m_main_window_width, &m_main_window_height);
    m_main_window_width =
        static_cast<int>(m_main_window_width * m_dpi_scale_factor);
    m_main_window_height =
        static_cast<int>(m_main_window_height * m_dpi_scale_factor);
    glfwSetWindowSize(window, m_main_window_width, m_main_window_height);
}

void ADIMainWindow::SetWindowPosition(float x, float y) {
    x = x * m_dpi_scale_factor;
    y = y * m_dpi_scale_factor;
    ImVec2 winPos = {x, y};
    ImGui::SetNextWindowPos(winPos);
}

void ADIMainWindow::SetWindowSize(float width, float height) {
    width = width * m_dpi_scale_factor;
    height = height * m_dpi_scale_factor;
    ImVec2 m_size = {width, height};
    ImGui::SetNextWindowSize(m_size);
}

std::shared_ptr<aditof::Camera> ADIMainWindow::GetActiveCamera() {
    if (!m_view_instance || !m_view_instance->m_ctrl ||
        m_view_instance->m_ctrl->m_cameras.empty() ||
        m_selected_device_index < 0 ||
        m_selected_device_index >=
            (int32_t)m_view_instance->m_ctrl->m_cameras.size()) {
        return nullptr;
    }
    return m_view_instance->m_ctrl->m_cameras[m_selected_device_index];
}

void ADIMainWindow::Render() {
    // Main imGUI loop

    while (!glfwWindowShouldClose(window)) {
        // Poll and handle events (inputs, window resize, etc.)
        // You can read the io.WantCaptureMouse, io.WantCaptureKeyboard flags to
        // tell if dear imgui wants to use your inputs.
        // - When io.WantCaptureMouse is true, do not dispatch mouse input data
        // to your main application.
        // - When io.WantCaptureKeyboard is true, do not dispatch keyboard input
        // data to your main application. Generally you may always pass all
        // inputs to dear imgui, and hide them from your application based on
        // those two flags.
        glfwGetWindowSize(window, &m_main_window_width, &m_main_window_height);
        glfwPollEvents();

        // Start the Dear ImGui frame
        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();
        if (!m_callback_initialized) {
            HandleInterruptCallback();
            m_callback_initialized = true;
        }
        /***************************************************/
        //Create windows here:
        ShowMainMenu();
        DisplayHelp();
        if (m_is_playing) {
            CameraPlay(m_mode_selection, m_view_selection);
            if (m_view_instance != nullptr) {
                if (m_view_instance->m_ctrl->panicStop) {
                    CameraStop();

                    aditof::Status status = aditof::Status::OK;
                    auto camera =
                        GetActiveCamera(); //already initialized on constructor

                    int chipStatus, imagerStatus;
                    status =
                        camera->adsd3500GetStatus(chipStatus, imagerStatus);
                    if (status != aditof::Status::OK) {
                        LOG(ERROR) << "Failed to read chip status!";
                    } else {
                        LOG(WARNING)
                            << "Chip status error code: " << chipStatus;
                        LOG(WARNING)
                            << "Imager status error code: " << imagerStatus;
                    }
                }
            }

        } else if (!m_modify_in_progress) {
            // Show Start Wizard
            ShowStartWizard();
        }

        if (getIsWorking()) {
            const float radius = 20.0f;
            const float thickness = 4.0f;
            const float padding = 12.0f;
            const char *label = getWorkingLabel().empty()
                                    ? "Working..."
                                    : getWorkingLabel().c_str();

            ImVec2 text_size = ImGui::CalcTextSize(label);
            ImVec2 spinner_size((radius + thickness) * 2.0f,
                                (radius + thickness) * 2.0f);
            float box_width =
                std::max(text_size.x, spinner_size.x) + (padding * 2.0f);
            float box_height = text_size.y + spinner_size.y + (padding * 3.0f);

            ImVec2 display_size = ImGui::GetIO().DisplaySize;
            ImVec2 box_pos((display_size.x - box_width) * 0.5f,
                           (display_size.y - box_height) * 0.5f);

            ImGui::SetNextWindowPos(box_pos, ImGuiCond_Always);
            ImGui::SetNextWindowSize(ImVec2(box_width, box_height),
                                     ImGuiCond_Always);
            ImGui::SetNextWindowFocus();
            ImGui::SetNextWindowBgAlpha(1.0f);

            ImGuiWindowFlags overlay_flags =
                ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoResize |
                ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoSavedSettings |
                ImGuiWindowFlags_NoFocusOnAppearing | ImGuiWindowFlags_NoNav |
                ImGuiWindowFlags_NoInputs;

            ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding,
                                ImVec2(0.0f, 0.0f));
            ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 6.0f);
            ImGui::PushStyleVar(ImGuiStyleVar_Alpha, 1.0f);
            ImGui::PushStyleVar(ImGuiStyleVar_WindowBorderSize, 1.0f);
            ImGui::PushStyleColor(ImGuiCol_WindowBg,
                                  ImVec4(0.05f, 0.05f, 0.05f, 0.98f));
            ImGui::PushStyleColor(ImGuiCol_Text,
                                  ImVec4(1.0f, 1.0f, 1.0f, 1.0f));
            ImGui::PushStyleColor(ImGuiCol_Border,
                                  ImVec4(1.0f, 1.0f, 1.0f, 0.2f));

            ImGui::Begin("##working_overlay", nullptr, overlay_flags);

            ImGui::SetCursorPosX((box_width - text_size.x) * 0.5f);
            ImGui::SetCursorPosY(padding);
            ImGui::TextUnformatted(label);

            ImGui::SetCursorPosX((box_width - spinner_size.x) * 0.5f);
            ImGui::SetCursorPosY(padding * 2.0f + text_size.y);
            ImGuiExtensions::ADISpinner(label, radius, thickness,
                                        IM_COL32(255, 255, 255, 255));

            ImGui::End();

            ImGui::PopStyleColor(3);
            ImGui::PopStyleVar(4);
        }

        /***************************************************/
        // Rendering
        static bool flashWindow = false;
        static float flashTimer = 0.0f;
        static const float flashDuration = 0.2f; // seconds
        ImVec4 clear_color = ImVec4(0.0f, 0.0f, 0.00f, 1.00f);

        if (m_flash_main_window) {
            flashWindow = true;
            flashTimer = flashDuration;
            m_flash_main_window = false;
        }

        float deltaTime = ImGui::GetIO().DeltaTime;
        if (flashWindow) {
            flashTimer -= deltaTime;
            if (flashTimer <= 0.0f) {
                flashWindow = false;
            }
        }

        if (flashWindow) {
            clear_color = ImVec4(1.0f, 1.0f, 1.0f, 1.00f);
        } else {
            clear_color = ImVec4(0.0f, 0.0f, 0.00f, 1.00f);
        }

        ImGui::Render();
        int display_w, display_h;
        glfwGetFramebufferSize(window, &display_w, &display_h);
        glViewport(0, 0, display_w, display_h);
        glClearColor(clear_color.x, clear_color.y, clear_color.z,
                     clear_color.w);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        glfwSwapBuffers(window);

        if (m_close_pending) {
            if (m_close_pending_frames > 0) {
                --m_close_pending_frames;
                continue;
            }
            CloseCamera();
            m_close_pending = false;
            setIsWorking(false);
        }

        if (m_start_streaming_pending) {
            if (m_start_streaming_pending_frames > 0) {
                --m_start_streaming_pending_frames;
                continue;
            }

            if (m_start_streaming_offline) {
                // Offline mode: playback from file
                if (m_view_instance) {
                    m_view_instance->cleanUp();
                }

                auto camera = GetActiveCamera();
                if (camera != nullptr) {
                    m_offline_change_frame = true;
                    camera->setPlaybackFile(m_offline_filename);
                    m_off_line_frame_index = 0;
                    m_frame_window_position_state = 0;
                    m_view_selection_changed = m_view_selection;
                    m_is_playing = true;
                    m_ini_params.clear();
                } else {
                    LOG(ERROR) << "Camera not initialized!";
                }
            } else {
                // Online mode: live camera streaming
                if (m_view_instance) {
                    m_view_instance->cleanUp();
                }

                auto camera = GetActiveCamera();
                if (camera && false) {
                    LOG(INFO) << "*** adsd3500setEnableDynamicModeSwitching disabled ***";
                    camera->adsd3500setEnableDynamicModeSwitching(false);
                }

                m_frame_window_position_state = 0;
                m_view_selection_changed = m_view_selection;
                m_last_mode = m_mode_selection;
                m_use_modified_ini_params = true;
                m_is_playing = true;
                m_ini_params.clear();
            }

            m_start_streaming_pending = false;
            setIsWorking(false);
        }

        if (m_stop_pending) {
            if (m_stop_pending_frames > 0) {
                --m_stop_pending_frames;
                continue;
            }

            m_is_playing = false;
            m_fps_frame_received = 0;
            if (!m_stop_filepath.empty()) {
                // Online mode - clear recording file path
                // Note: filePath variable is local to DisplayControlWindow, so we handle this differently
            }
            CameraStop();

            m_stop_pending = false;
            setIsWorking(false);
        }

        if (m_capture_pending) {
            if (m_capture_pending_frames > 0) {
                --m_capture_pending_frames;
                continue;
            }

            // Keep spinner active while saving all frames
            // SaveAllFramesUpdate() will clear m_base_file_name when done
            if (!m_base_file_name.empty()) {
                continue;
            }

            m_capture_pending = false;
            setIsWorking(false);
        }

        if (m_modify_pending) {
            if (m_modify_pending_frames > 0) {
                --m_modify_pending_frames;
                continue;
            }

            if (!m_modify_worker_running) {
                m_modify_in_progress = true;

                if (m_modifyWorker.joinable()) {
                    m_modifyWorker.join();
                }

                m_modify_worker_running = true;
                m_modify_worker_done = false;
                m_modifyWorker = std::thread([this]() {
                    if (m_view_instance && m_view_instance->m_ctrl) {
                        m_view_instance->m_ctrl->StopCapture();
                    }
                    m_modify_worker_done = true;
                });
                continue;
            }

            if (m_modify_worker_done) {
                if (m_modifyWorker.joinable()) {
                    m_modifyWorker.join();
                }

                // Now stop playback and clean up
                m_is_playing = false;
                m_fps_frame_received = 0;

                if (m_view_instance && m_view_instance->m_ctrl) {
                    OpenGLCleanUp();
                    m_view_instance->m_ctrl->panicStop = false;
                }

                m_capture_separate_enabled = true;
                m_set_ab_win_position_once = true;
                m_set_depth_win_position_once = true;
                m_set_point_cloud_position_once = true;
                m_off_line_frame_index = 0;

                m_use_modified_ini_params = true;
                m_view_selection_changed = m_view_selection;
                m_is_playing = true;
                m_modify_worker_running = false;
                m_modify_pending = false;
                m_modify_in_progress = false;
                setIsWorking(false);
            }
        }
    }
}

void ADIMainWindow::ShowMainMenu() {
    static bool show_app_log = false;
    static bool show_help_window = false;

    if (show_app_log) {
        ShowLogWindow(&show_app_log);
    }

    if (show_help_window) {
        ImGui::OpenPopup("Help Window");
        show_help_window = false;
    }

    if (ImGui::BeginMainMenuBar()) {
        if (ImGui::BeginMenu("?")) {
            if (ImGui::MenuItem("Help")) {
                show_help_window = true;
            }
            ImGui::MenuItem("Debug Log", nullptr, &show_app_log);
            ImGui::Separator();
            if (ImGui::MenuItem("Exit")) {
                glfwSetWindowShouldClose(window, true);
            }
            ImGui::EndMenu();
        }
        ImGui::EndMainMenuBar();
    }
}

void ADIMainWindow::ShowLoadAdsdParamsMenu() {

    int FilterIndex = 0;
    std::string fs =
        openADIFileName("ADI ToF Config Files\0*.json\0", nullptr, FilterIndex);
    LOG(INFO) << "Load File selected: " << fs;

    if (fs.empty()) {
        return;
    }

    bool loadconfigurationFile = false;
    std::string loadconfigurationFileValue = std::string(fs);
    if (!loadconfigurationFileValue.empty()) {
        if (loadconfigurationFileValue.find(".json") == std::string::npos) {
            loadconfigurationFileValue += ".json";
        }
        loadconfigurationFile = true;
    }
    if (loadconfigurationFile && m_view_instance) {
        auto camera =
            m_view_instance->m_ctrl->m_cameras[static_cast<unsigned int>(
                m_view_instance->m_ctrl->getCameraInUse())];

        aditof::Status status =
            camera->loadDepthParamsFromJsonFile(loadconfigurationFileValue);

        if (status != aditof::Status::OK) {
            LOG(INFO) << "Could not load current configuration "
                         "info to "
                      << loadconfigurationFileValue;
        } else {
            LOG(INFO) << "Current configuration info from file "
                      << loadconfigurationFileValue;

            m_ini_params.clear();
        }
    }
}

void ADIMainWindow::ShowSaveAdsdParamsMenu() {

    ImGuiExtensions::ButtonColorChanger colorChangerStartRec(
        m_custom_color_play, m_is_playing);

    char filename[MAX_PATH] = "";
    int FilterIndex;
    std::string fs = getADIFileName(
        nullptr, "ADI ToF Config Files\0*.json\0All Files\0*.*\0", filename,
        FilterIndex);
    LOG(INFO) << "Selecting to save configuration the file: " << fs;

    bool saveconfigurationFile = false;
    std::string saveconfigurationFileValue = fs;

    if (!saveconfigurationFileValue.empty()) {
        if (saveconfigurationFileValue.find(".json") == std::string::npos) {
            saveconfigurationFileValue += ".json";
        }
        saveconfigurationFile = true;
    }
    if (saveconfigurationFile && m_view_instance) {
        auto camera =
            m_view_instance->m_ctrl->m_cameras[static_cast<unsigned int>(
                m_view_instance->m_ctrl->getCameraInUse())];

        aditof::Status status =
            camera->saveDepthParamsToJsonFile(saveconfigurationFileValue);

        if (status != aditof::Status::OK) {
            saveconfigurationFile = false;
            LOG(INFO) << "Could not save current configuration info to "
                      << saveconfigurationFileValue << std::endl;
        } else {
            LOG(INFO) << "Current configuration info saved to file "
                      << saveconfigurationFileValue << std::endl;
        }
    }
}

void ADIMainWindow::DrawColoredLabel(const char *fmt, ...) {
    // Format the text
    char buf[512];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    ImVec4 box_color = ImVec4(0.2f, 0.6f, 0.9f, 1.0f); // RGBa

    // Get draw list and cursor position
    ImVec2 textPos = ImGui::GetCursorScreenPos();
    ImVec2 textSize = ImGui::CalcTextSize(buf);
    float padding = 2.0f;

    // Draw background box
    ImDrawList *drawList = ImGui::GetWindowDrawList();
    drawList->AddRectFilled(ImVec2(textPos.x - padding, textPos.y - padding),
                            ImVec2(textPos.x + textSize.x + padding,
                                   textPos.y + textSize.y + padding),
                            ImGui::ColorConvertFloat4ToU32(box_color),
                            4.0f // optional: corner radius
    );

    // Draw the text on top
    ImGui::SetCursorScreenPos(textPos);
    ImGui::TextUnformatted(buf);
}

void ADIMainWindow::DrawBarLabel(const char *fmt, ...) {

    char buf[512];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);

    ImGui::PushStyleColor(
        ImGuiCol_ChildBg,
        IM_COL32(60, 60, 60, 255)); // Optional: dark bar background

    float textHeight = ImGui::GetTextLineHeight();
    ImGui::BeginChild(buf, ImVec2(0, textHeight * 1.1f), false);

    // Center the text
    float windowWidth = ImGui::GetWindowSize().x;
    float textWidth = ImGui::CalcTextSize(buf).x;
    ImGui::SetCursorPosX((windowWidth - textWidth) *
                         0.5f); // center horizontally
    ImGui::TextUnformatted(buf);

    ImGui::EndChild();

    ImGui::PopStyleColor(); // Reset bar color
}

void ADIMainWindow::NewLine(float spacing) {
    ImGui::Dummy(ImVec2(0.0f, spacing));
}

void ADIMainWindow::ShowStartWizard() {

    static float wizard_height = 640.0f;

    centreWindow(450.0f * m_dpi_scale_factor,
                 wizard_height * m_dpi_scale_factor);

    ImGui::Begin("Camera Selection Wizard", nullptr,
                 ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoScrollbar);

    static uint32_t selected = 1;
    uint32_t state_change_check = selected;

    ImGui::BeginDisabled(m_is_open_device);

    ImGui::RadioButton("Saved Stream", selected == 0);
    ImGuiExtensions::ADIShowTooltipFor("WizardSavedStream");
    if (ImGui::IsItemClicked()) {
        selected = 0;
        m_off_line = true;
        RefreshDevices();
    }

    ImGui::SameLine();

    ImGui::RadioButton("Live Camera", selected == 1);
    ImGuiExtensions::ADIShowTooltipFor("WizardLiveCamera");
    if (ImGui::IsItemClicked()) {
        selected = 1;
        m_off_line = false;
        RefreshDevices();
    }

    ImGui::EndDisabled();

    if (selected == 1 && selected != state_change_check) {
        if (m_is_open_device) {
        }
    }

    ImGui::NewLine();

    if (selected == 0) {
#pragma region WizardOffline

        const bool openAvailable = !m_connected_devices.empty();

        { // Use block to control the moment when ImGuiExtensions::ButtonColorChanger gets destroyed
            static std::string fileName;
            ImGuiExtensions::ButtonColorChanger colorChanger(
                ImGuiExtensions::ButtonColor::Green, openAvailable);
            if (ImGuiExtensions::ADIButton("Open")) {
                setWorkingLabel("Opening file...");
                setIsWorking(true);

                int FilterIndex = 0;
                std::string fs = openADIFileName(
                    "ADI ToF Config Files\0*.adcam\0", nullptr, FilterIndex);
                LOG(INFO) << "Load File selected: " << fs;

                if (!fs.empty()) {

                    //RefreshDevices();

                    //m_is_open_device = true;
                    m_is_playing = false;
                    m_is_open_device = false;
                    m_selected_device_index = 0;
                    fileName = fs;
                    m_off_line_frame_index = 0;
                    initCameraWorker =
                        std::thread([this, fs]() { InitCamera(fs); });
                } else {
                    setIsWorking(false);
                }
            }
            ImGuiExtensions::ADIShowTooltipFor("WizardOfflineOpen");
            ImGui::SameLine();
            if (ImGuiExtensions::ADIButton("Start Streaming",
                                           m_is_open_device)) {
                setWorkingLabel("Starting playback...");
                setIsWorking(true);
                m_offline_filename = fileName;
                m_start_streaming_offline = true;
                m_start_streaming_pending = true;
                m_start_streaming_pending_frames = 1;
            }
            ImGuiExtensions::ADIShowTooltipFor("WizardOfflineStartStreaming");
            ImGui::SameLine();
            if (ImGuiExtensions::ADIButton("Close", m_is_open_device)) {
                setWorkingLabel("Closing file...");
                setIsWorking(true);
                CameraStop();
                if (initCameraWorker.joinable()) {
                    initCameraWorker.join();
                    m_cameraModes.clear();
                    _cameraModes.clear();
                }
                m_view_instance->cleanUp();
                m_view_instance.reset();

                m_is_open_device = false;
                m_cameraWorkerDone = false;
                setIsWorking(false);
            }
            ImGuiExtensions::ADIShowTooltipFor("WizardOfflineClose");
            if (m_is_open_device) {
                NewLine(5.0f);
                ImGui::Text("File selected");
                ImGui::PushTextWrapPos(ImGui::GetCursorPos().x +
                                       400); // Wrap at 400px
                ImGui::TextWrapped("  %s", fileName.c_str());
                ImGui::PopTextWrapPos();
                NewLine(5.0f);
            }
        }
#pragma endregion // WizardOffline
    } else {
#pragma region WizardOnline
        ImGuiExtensions::ADIComboBox(
            "Camera", "(No available devices)", ImGuiComboFlags_None,
            m_connected_devices, &m_selected_device_index, m_is_open_device);
        //If a device is found, then set the first one found
        if (!m_connected_devices.empty() && m_selected_device_index == -1) {
            m_selected_device_index = 0;
            //m_is_open_device = true;
        }

        NewLine(5.0f);
        if (ImGuiExtensions::ADIButton("Refresh", !m_is_open_device)) {
            m_is_open_device = false;
            m_cameraWorkerDone = false;
            RefreshDevices();
        }
        ImGuiExtensions::ADIShowTooltipFor("WizardOnlineRefresh");

        ImGui::SameLine();

        const bool openAvailable = !m_connected_devices.empty();
        { // Use block to control the moment when ImGuiExtensions::ButtonColorChanger gets destroyed
            ImGuiExtensions::ButtonColorChanger colorChanger(
                ImGuiExtensions::ButtonColor::Green, openAvailable);
            if (ImGuiExtensions::ADIButton("Open", !m_is_open_device &&
                                                       !getIsWorking()) &&
                0 <= m_selected_device_index) {
                setWorkingLabel("Opening camera...");
                setIsWorking(true);
                m_is_open_device = true;
                std::string fs;
                initCameraWorker =
                    std::thread([this, fs]() { InitCamera(fs); });
            }
        }
        ImGuiExtensions::ADIShowTooltipFor("WizardOnlineOpen");

        ImGui::SameLine();
        if (ImGuiExtensions::ADIButton("Close",
                                       m_is_open_device && !getIsWorking())) {
            setWorkingLabel("Closing camera...");
            setIsWorking(true);
            m_cameraWorkerDone = false;
            m_close_pending = true;
            m_close_pending_frames = 1;
        }
        ImGuiExtensions::ADIShowTooltipFor("WizardOnlineClose");
        NewLine(5.0f);

        if (m_cameraWorkerDone) {
            //m_is_open_device = false;
            if (!m_is_playing) {

                NewLine(5.0f);

                DrawBarLabel("Mode Selection");

                NewLine(10.0f);

                if (ImGuiExtensions::ADIComboBox(
                        "select_mode", "Select Mode", ImGuiSelectableFlags_None,
                        m_cameraModesDropDown, &m_mode_selection, true)) {
                    m_ini_params.clear();
                }
                ImGuiExtensions::ADIShowTooltipFor("WizardOnlineSelectMode");

                NewLine(5.0f);

                DrawBarLabel("Configuration");

                NewLine(5.0f);

                if (ImGuiExtensions::ADIButton("Load Config", !m_is_playing)) {

                    ShowLoadAdsdParamsMenu();
                }
                ImGuiExtensions::ADIShowTooltipFor("WizardOnlineLoadConfig");

                ImGui::SameLine();

                if (ImGuiExtensions::ADIButton("Reset Parameters",
                                               m_is_open_device)) {
                    auto camera = GetActiveCamera();
                    if (camera) {
                        camera->resetDepthProcessParams();
                        m_ini_params.clear();
                    }
                }
                ImGuiExtensions::ADIShowTooltipFor("WizardOnlineResetParameters");

                NewLine(5.0f);

                ShowIniWindow(false);

                NewLine(15.0f);

                //Change colour to green
                ImGuiExtensions::ButtonColorChanger colorChangerPlay(
                    m_custom_color_play, !m_is_playing);

                ImGui::Toggle(!m_enable_preview ? "Preview Off" : "Preview On",
                              &m_enable_preview);
                if (m_enable_preview) {
                    ImGuiExtensions::ADIShowTooltipFor("WizardOnlinePreviewOn");
                } else {
                    ImGuiExtensions::ADIShowTooltipFor("WizardOnlinePreviewOff");
                }

                if (ImGuiExtensions::ADIButton("Start Streaming",
                                               !m_is_playing)) {
                    setWorkingLabel("Starting streaming...");
                    setIsWorking(true);
                    m_start_streaming_offline = false;
                    m_start_streaming_pending = true;
                    m_start_streaming_pending_frames = 1;
                }
                ImGuiExtensions::ADIShowTooltipFor("WizardOnlineStartStreaming");
            }
        }
#pragma endregion // WizardOnline
    }
    ImGui::End();
}

void ADIMainWindow::centreWindow(float width, float height) {

    ImGuiIO &io = ImGui::GetIO(); // Get the display size
    ImVec2 center = ImVec2(io.DisplaySize.x * 0.5f, io.DisplaySize.y * 0.5f);
    ImVec2 window_size = ImVec2(width, height); // Your window size

    // Offset to truly center it
    ImVec2 window_pos = ImVec2(center.x - window_size.x * 0.5f,
                               center.y - window_size.y * 0.5f);

    // Set position and size before Begin()
    ImGui::SetNextWindowPos(window_pos, ImGuiCond_Always);
    ImGui::SetNextWindowSize(window_size, ImGuiCond_Always);
}
