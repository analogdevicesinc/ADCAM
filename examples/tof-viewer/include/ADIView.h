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

#ifndef ADIVIEW_H
#define ADIVIEW_H

#include <fstream>
#include <stdio.h>

#include <chrono>
#include <deque>
#include <iostream>
#include <numeric>

#include "ADIController.h"
#include "backends/imgui_impl_glfw.h"
#include "backends/imgui_impl_opengl3.h"
#include "imgui.h"
#include <ADIShader.h>
#include <aditof/frame.h>

#if defined(__ARM_NEON) || defined(__ARM_NEON__)

#define AB_SIMD    /* ARM NEON optimized */
#define DEPTH_SIMD /* ARM NEON optimized */
#define PC_SIMD    /* ARM NEON optimized */

#else

//#define AB_SIMD    /* Much faster, so leave this active */
//#define DEPTH_SIMD /* Much faster, so leave this active */
//#define PC_SIMD

#endif // ARM NEON

#if defined(_WIN32) || defined(__WIN32__) || defined(WIN32)
//#define AB_TIME
//#define DEPTH_TIME
//#define PC_TIME
#endif //defined(_WIN32) || defined(__WIN32__) || defined(WIN32)

namespace adiviewer {
struct ImageDimensions {
    ImageDimensions() = default;
    constexpr ImageDimensions(int w, int h) : Width(w), Height(h) {}
    constexpr ImageDimensions(const std::pair<int, int> &pair)
        : Width(pair.first), Height(pair.second) {}

    int Width;
    int Height;
};

class ADIView {
  public:
    /**
		* @brief Constructor
		*/
    ADIView(std::shared_ptr<adicontroller::ADIController> ctrl,
            const std::string &name, bool enableAB = true,
            bool enableDepth = true, bool enableXYZ = true);

    /**
		* @brief Destructor
		*/
    ~ADIView();

    /**
     * @brief Clean up resources and stop worker threads
     */
    void cleanUp();

    /**
		* @brief Not implemented. Code under development
		*/
    bool startImGUI(bool *success);

    /**
     * @brief Enable or disable logarithmic image scaling
     * @param[in] value True to enable log scaling, false to disable
     */
    void setLogImage(bool value) { m_logImage = value; }

    /**
     * @brief Get current logarithmic image scaling state
     * @return True if log scaling is enabled, false otherwise
     */
    bool getLogImage() { return m_logImage; }

    /**
     * @brief Enable or disable binary format for saved frames
     * @param[in] value True for binary format, false otherwise
     */
    void setSaveBinaryFormat(bool value) { m_saveBinaryFormat = value; }

    /**
     * @brief Get current save format setting
     * @return True if binary format is enabled, false otherwise
     */
    bool getSaveBinaryFormat() { return m_saveBinaryFormat; }

    /**
     * @brief Cap AB width processing
     * @param[in] value True to cap AB width, false otherwise
     */
    void setCapABWidth(bool value) { m_capABWidth = value; }

    /**
     * @brief Get AB width cap state
     * @return True if AB width is capped, false otherwise
     */
    bool getCapABWidth() { return m_capABWidth; }

    /**
     * @brief Enable or disable automatic scaling of image data
     * @param[in] value True to enable auto-scaling, false to disable
     */
    void setAutoScale(bool value) { m_autoScale = value; }

    /**
     * @brief Get auto-scaling state
     * @return True if auto-scaling is enabled, false otherwise
     */
    bool getAutoScale() { return m_autoScale; }

    /**
     * @brief Set maximum range for active brightness (AB) data
     * @param[in] value Maximum range value as string
     */
    void setABMaxRange(std::string value);

    /**
     * @brief Set maximum range for active brightness (AB) data
     * @param[in] value Maximum range value as unsigned integer
     */
    void setABMaxRange(uint32_t value) { m_maxABPixelValue = value; }

    /**
     * @brief Get maximum range for AB data
     * @return Maximum AB pixel value
     */
    uint32_t getABMaxRange() { return m_maxABPixelValue; }

    /**
     * @brief Set minimum range for active brightness (AB) data
     * @param[in] value Minimum range value
     */
    void setABMinRange(uint32_t value) { m_minABPixelValue = value; }

    /**
     * @brief Get minimum range for AB data
     * @return Minimum AB pixel value
     */
    uint32_t getABMinRange() { return m_minABPixelValue; }

    void setUserABMaxState(bool value) { m_maxABPixelValueSet = value; }
    bool getUserABMaxState() { return m_maxABPixelValueSet; }

    void setUserABMinState(bool value) { m_minABPixelValueSet = value; }
    bool getUserABMinState() { return m_minABPixelValueSet; }

    void setPointCloudColour(uint32_t colour) { m_pccolour = colour; }

    std::shared_ptr<adicontroller::ADIController> m_ctrl;
    std::shared_ptr<aditof::Frame> m_capturedFrame = nullptr;
    std::condition_variable m_barrierCv;
    std::mutex m_imshowMutex;
    uint32_t frameHeight = 0;
    uint32_t frameWidth = 0;
    int32_t m_waitKeyBarrier;
    int32_t numOfThreads = 3;
    std::mutex m_frameCapturedMutex;
    bool m_abFrameAvailable;
    bool m_depthFrameAvailable;
    bool m_pcFrameAvailable;
    bool m_stopWorkersFlag = false;
    bool m_saveBinaryFormat = false;
    uint32_t m_pccolour = 0;

    std::thread m_depthImageWorker;
    std::thread m_abImageWorker;
    std::thread m_pointCloudImageWorker;

    // Flags to track which threads are actually created
    bool m_abThreadCreated = false;
    bool m_depthThreadCreated = false;
    bool m_xyzThreadCreated = false;

    std::condition_variable m_frameCapturedCv;
    uint16_t *ab_video_data;
    uint16_t *depth_video_data;
    int16_t *pointCloud_video_data;
    uint8_t *ab_video_data_8bit;
    uint8_t *depth_video_data_8bit;
    float *normalized_vertices = nullptr;
    size_t pointcloudTableSize = 0;

    uint16_t temperature_c;
    uint16_t time_stamp;
    double m_blendValue = 0.5;
    int32_t maxRange = 5000;
    int32_t minRange = 0;
    /**************/
    //OpenCV  here
    /**
		* @brief Deprecated
		*/
    void startCamera();

    //Point Cloud
    GLint viewIndex;
    GLint modelIndex;
    GLint projectionIndex;
    GLint m_pointSizeIndex;
    GLuint vertexArrayObject;
    GLuint vertexBufferObject; //Image Buffer
    adiviewer::Program pcShader;
    uint32_t vertexArraySize = 0;
    float Max_Z = 6000.0;
    float Min_Z = 0.0;
    float Max_Y = 6000.0;
    float Max_X = 6000.0;

  private:
    /**
     * @brief Prepare image buffers for rendering
     */
    void prepareImages();

    /**
		* @brief Creates Depth buffer data
		*/
    void _displayDepthImage();
#ifdef DEPTH_SIMD
    void _displayDepthImage_SIMD();
#endif
#if defined(__aarch64__) || defined(__ARM_NEON)
    void _displayDepthImage_NEON();
#endif
#ifdef USE_CUDA
    void _displayDepthImage_CUDA();
#endif

    /**
		* @brief Creates AB buffer data
		*/
    void _displayAbImage();

    /**
     * @brief Normalize active brightness buffer for display
     * @param[in,out] abBuffer Pointer to AB data buffer
     * @param[in] abWidth Width of AB frame
     * @param[in] abHeight Height of AB frame
     * @param[in] advanceScaling Enable advanced scaling algorithm
     * @param[in] useLogScaling Apply logarithmic scaling
     */
    void normalizeABBuffer(uint16_t *abBuffer, uint16_t abWidth,
                           uint16_t abHeight, bool advanceScaling,
                           bool useLogScaling);
#ifdef AB_SIMD
    void _displayAbImage_SIMD();
    void normalizeABBuffer_SIMD(uint16_t *abBuffer, uint16_t abWidth,
                                uint16_t abHeight, bool advanceScaling,
                                bool useLogScaling);
#endif
#if defined(__aarch64__) || defined(__ARM_NEON)
    void _displayAbImage_NEON();
    void normalizeABBuffer_NEON(uint16_t *abBuffer, uint16_t abWidth,
                                uint16_t abHeight, bool advanceScaling,
                                bool useLogScaling);
#endif
#ifdef USE_CUDA
    void _displayAbImage_CUDA();
#endif

    /**
		* @brief Creates a Point Cloud buffer data
		*/
    void _displayPointCloudImage();
#ifdef PC_SIMD
    void _displayPointCloudImage_SIMD();
#endif
#if defined(__aarch64__) || defined(__ARM_NEON)
    void _displayPointCloudImage_NEON();
#endif
#ifdef USE_CUDA
    void _displayPointCloudImage_CUDA();
#endif

    /**
		* @brief Returns RGB components in
		*        HSV format
		*/
    void hsvColorMap(uint16_t video_data, int max, int min, float &fRed,
                     float &fGreen, float &fBlue);

    void ColorConvertHSVtoRGB(float h, float s, float v, float &out_r,
                              float &out_g, float &out_b);

    std::string m_viewName;
    bool m_center = true;
    int m_distanceVal;
    bool m_smallSignal;
    bool m_crtSmallSignalState;

    //imGUI stuff
    GLFWwindow *window;
    bool showABWindow = true;
    bool showDepthWindow = true;
    bool beginDisplayABImage = false;
    bool beginDisplayDepthImage = false;
    bool beginDisplayPointCloudImage = false;

    uint16_t *video_data;
    const char *vertexShaderSource;
    const char *fragmentShaderSource;
    int shaderProgram;
    uint32_t m_maxABPixelValue;
    uint32_t m_minABPixelValue;
    bool m_maxABPixelValueSet = false;
    bool m_minABPixelValueSet = false;
    bool m_logImage = true;
    bool m_capABWidth = false;
    bool m_autoScale = true;

    std::mutex ab_data_ready_mtx;
    std::condition_variable ab_data_ready_cv;
    bool ab_data_ready = false;

    const size_t N = 50;

    // Call this before your function
    auto startTimer() { return std::chrono::high_resolution_clock::now(); }

    // Call this after your function; updates 'times' and returns running average in ms
    double endTimerAndUpdate(
        std::chrono::time_point<std::chrono::high_resolution_clock> timerStart,
        std::deque<long long> *times) {
        auto end = std::chrono::high_resolution_clock::now();
        long long duration;

        duration = std::chrono::duration_cast<std::chrono::nanoseconds>(
                       end - timerStart)
                       .count();

        times->push_back(duration);
        if (times->size() > N)
            times->pop_front();

        double sum = std::accumulate(times->begin(), times->end(), 0.0);
        return sum / times->size() / 1e6; // Average in milliseconds
    }
};
} //namespace adiviewer

#endif
