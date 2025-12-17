/*
 * BSD 3-Clause License
 *
 * Copyright (c) 2019, Analog Devices, Inc.
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice, this
 *    list of conditions and the following disclaimer.
 *
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 *    this list of conditions and the following disclaimer in the documentation
 *    and/or other materials provided with the distribution.
 *
 * 3. Neither the name of the copyright holder nor the names of its
 *    contributors may be used to endorse or promote products derived from
 *    this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 * DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 * CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
 * OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */
#include "ADIView.h"
#include "ADIViewCuda.cuh"
#include <aditof/log.h>
#include <sstream>

using namespace adiviewer;

#ifdef USE_CUDA

// CUDA-accelerated AB image display
void ADIView::_displayAbImage_CUDA() {
#ifdef AB_TIME
    std::deque<long long> timeABQ;
#endif

    while (!m_stopWorkersFlag) {
        {
            std::unique_lock<std::mutex> lock(m_frameCapturedMutex);
            m_frameCapturedCv.wait(lock, [&]() {
                return m_abFrameAvailable || m_stopWorkersFlag;
            });

            if (m_stopWorkersFlag) {
                break;
            }

            m_abFrameAvailable = false;
            if (m_capturedFrame == nullptr) {
                continue;
            }

            lock.unlock();
        }

#ifdef AB_TIME
        auto timerStart = startTimer();
#endif

        std::lock_guard<std::mutex> lock(ab_data_ready_mtx);

        uint16_t *_ab_video_data = nullptr;
        auto camera = m_ctrl->m_cameras[static_cast<unsigned int>(
            m_ctrl->getCameraInUse())];

        m_capturedFrame->getData("ab", &ab_video_data);

        if (ab_video_data == nullptr) {
            return;
        }

        aditof::FrameDataDetails frameAbDetails;
        frameAbDetails.height = 0;
        frameAbDetails.width = 0;
        m_capturedFrame->getDataDetails("ab", frameAbDetails);

        frameHeight = static_cast<int>(frameAbDetails.height);
        frameWidth = static_cast<int>(frameAbDetails.width);

        if (_ab_video_data == nullptr) {
            _ab_video_data = new uint16_t[frameHeight * frameWidth];
        }
        if (_ab_video_data == nullptr) {
            LOG(ERROR) << __func__ << ": Cannot allocate _ab_video_data.";
            return;
        }
        memcpy(_ab_video_data, ab_video_data,
               frameHeight * frameWidth * sizeof(uint16_t));

        // Get bitsInAb from metadata
        aditof::Metadata *metadata = nullptr;
        uint8_t bitsInAb = 13; // default
        if (m_capturedFrame) {
            m_capturedFrame->getData("metadata", (uint16_t **)&metadata);
            if (metadata != nullptr) {
                bitsInAb = metadata->bitsInAb;
            }
        }

        // Use CUDA for normalization
        normalizeABBuffer_CUDA(nullptr, _ab_video_data, frameWidth, frameHeight,
                               getAutoScale(), getLogImage(), bitsInAb);

        if (ab_video_data_8bit == nullptr) {
            ab_video_data_8bit = new uint8_t[frameHeight * frameWidth * 3];
        }

        // Use CUDA for BGR conversion
        convertABtoBGR_CUDA(_ab_video_data, nullptr, ab_video_data_8bit,
                            frameWidth, frameHeight);

        ab_data_ready = true;
        ab_data_ready_cv.notify_one();

        if (_ab_video_data != nullptr) {
            delete[] _ab_video_data;
        }

#ifdef AB_TIME
        {
            std::ostringstream oss;
            oss << "AB (CUDA): " << endTimerAndUpdate(timerStart, &timeABQ)
                << " ms" << std::endl;
            OutputDebugStringA(oss.str().c_str());
        }
#endif

        std::unique_lock<std::mutex> imshow_lock(m_imshowMutex);
        m_waitKeyBarrier++;
        if (m_waitKeyBarrier == numOfThreads) {
            imshow_lock.unlock();
            m_barrierCv.notify_one();
        }
    }
}

// CUDA-accelerated depth image display
void ADIView::_displayDepthImage_CUDA() {
#ifdef DEPTH_TIME
    std::deque<long long> timeDepthQ;
#endif

    while (!m_stopWorkersFlag) {
        {
            std::unique_lock<std::mutex> lock(m_frameCapturedMutex);
            m_frameCapturedCv.wait(lock, [&]() {
                return m_depthFrameAvailable || m_stopWorkersFlag;
            });

            if (m_stopWorkersFlag) {
                break;
            }

            m_depthFrameAvailable = false;
            if (m_capturedFrame == nullptr) {
                continue;
            }

            lock.unlock();
        }

#ifdef DEPTH_TIME
        auto timerStart = startTimer();
#endif

        uint16_t *data;
        m_capturedFrame->getData("depth", &depth_video_data);

        if (depth_video_data == nullptr) {
            return;
        }

        aditof::FrameDataDetails frameDepthDetails;
        m_capturedFrame->getDataDetails("depth", frameDepthDetails);

        int frameHeight = static_cast<int>(frameDepthDetails.height);
        int frameWidth = static_cast<int>(frameDepthDetails.width);

        if (depth_video_data_8bit == nullptr) {
            depth_video_data_8bit = new uint8_t[frameHeight * frameWidth * 3];
        }

        // Use CUDA for depth processing
        processDepthImage_CUDA(nullptr, depth_video_data, nullptr,
                               depth_video_data_8bit, frameWidth, frameHeight,
                               minRange, maxRange);

#ifdef DEPTH_TIME
        {
            std::ostringstream oss;
            oss << "Depth (CUDA): "
                << endTimerAndUpdate(timerStart, &timeDepthQ) << " ms"
                << std::endl;
            OutputDebugStringA(oss.str().c_str());
        }
#endif

        std::unique_lock<std::mutex> imshow_lock(m_imshowMutex);
        m_waitKeyBarrier++;
        if (m_waitKeyBarrier == numOfThreads) {
            imshow_lock.unlock();
            m_barrierCv.notify_one();
        }
    }
}

// CUDA-accelerated point cloud image display
void ADIView::_displayPointCloudImage_CUDA() {
#ifdef PC_TIME
    std::deque<long long> timePCQ;
#endif

    while (!m_stopWorkersFlag) {
        {
            std::unique_lock<std::mutex> lock(m_frameCapturedMutex);
            m_frameCapturedCv.wait(lock, [&]() {
                return m_pcFrameAvailable || m_stopWorkersFlag;
            });

            if (m_stopWorkersFlag) {
                break;
            }

            m_pcFrameAvailable = false;
            if (m_capturedFrame == nullptr) {
                continue;
            }

            lock.unlock();
        }

#ifdef PC_TIME
        auto timerStart = startTimer();
#endif

        m_capturedFrame->getData("xyz", (uint16_t **)&pointCloud_video_data);

        if (pointCloud_video_data == nullptr) {
            return;
        }

        aditof::FrameDataDetails frameXyzDetails;
        frameXyzDetails.height = 0;
        frameXyzDetails.width = 0;
        m_capturedFrame->getDataDetails("xyz", frameXyzDetails);
        frameHeight = static_cast<int>(frameXyzDetails.height);
        frameWidth = static_cast<int>(frameXyzDetails.width);

        size_t frameSize = frameHeight * frameWidth * 3;
        if (normalized_vertices == nullptr ||
            pointcloudTableSize != frameSize) {
            if (normalized_vertices) {
                delete[] normalized_vertices;
            }
            pointcloudTableSize = frameSize;
            normalized_vertices = new float[(pointcloudTableSize + 1) * 3];
        }

        bool haveAb = m_capturedFrame->haveDataType("ab");

        if (haveAb) {
            std::unique_lock<std::mutex> lock(ab_data_ready_mtx);
            ab_data_ready_cv.wait(lock, [this] { return ab_data_ready; });
        }

        // Use CUDA for point cloud processing
        processPointCloud_CUDA(
            nullptr, pointCloud_video_data, nullptr, normalized_vertices,
            haveAb ? ab_video_data_8bit : nullptr, frameWidth, frameHeight,
            Max_X, Max_Y, Max_Z, minRange, maxRange, m_pccolour, haveAb);

        vertexArraySize = (pointcloudTableSize + 1) * sizeof(float) * 3;

#ifdef PC_TIME
        {
            std::ostringstream oss;
            oss << "PC (CUDA): " << endTimerAndUpdate(timerStart, &timePCQ)
                << " ms" << std::endl;
            OutputDebugStringA(oss.str().c_str());
        }
#endif

        std::unique_lock<std::mutex> imshow_lock(m_imshowMutex);
        m_waitKeyBarrier++;
        if (m_waitKeyBarrier == numOfThreads) {
            imshow_lock.unlock();
            m_barrierCv.notify_one();
        }
    }
}

#endif // USE_CUDA
