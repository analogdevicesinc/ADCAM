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

#include "ADIView.h"
#include <aditof/log.h>
#include <algorithm>
#include <arm_neon.h>
#include <cmath>

using namespace adiviewer;

// ARM NEON optimized AB buffer normalization
void ADIView::normalizeABBuffer_NEON(uint16_t *abBuffer, uint16_t abWidth,
                                     uint16_t abHeight, bool advanceScaling,
                                     bool useLogScaling) {
    size_t imageSize = abHeight * abWidth;
    uint32_t min_value_of_AB_pixel = 0xFFFF;
    uint32_t max_value_of_AB_pixel = 1;
    const size_t neon_width = 8; // NEON: 8 x uint16_t per vector

    // --- Min/Max scan using NEON ---
    if (advanceScaling) {
        uint16x8_t vmin = vdupq_n_u16(0xFFFF);
        uint16x8_t vmax = vdupq_n_u16(0);

        size_t i = 0;
        for (; i + neon_width <= imageSize; i += neon_width) {
            uint16x8_t v = vld1q_u16(abBuffer + i);
            vmin = vminq_u16(vmin, v);
            vmax = vmaxq_u16(vmax, v);
        }

        // Horizontal reduction
        uint16_t min_buf[neon_width], max_buf[neon_width];
        vst1q_u16(min_buf, vmin);
        vst1q_u16(max_buf, vmax);

        for (int j = 0; j < (int)neon_width; ++j) {
            min_value_of_AB_pixel =
                std::min(min_value_of_AB_pixel, (uint32_t)min_buf[j]);
            max_value_of_AB_pixel =
                std::max(max_value_of_AB_pixel, (uint32_t)max_buf[j]);
        }

        // Scalar tail
        for (; i < imageSize; ++i) {
            min_value_of_AB_pixel =
                std::min(min_value_of_AB_pixel, (uint32_t)abBuffer[i]);
            max_value_of_AB_pixel =
                std::max(max_value_of_AB_pixel, (uint32_t)abBuffer[i]);
        }

        max_value_of_AB_pixel -= min_value_of_AB_pixel;
    } else {
        // Get actual AB bit depth from metadata
        aditof::Metadata *metadata = nullptr;
        if (m_capturedFrame) {
            m_capturedFrame->getData("metadata", (uint16_t **)&metadata);
        }
        uint8_t bitsInAb = (metadata != nullptr) ? metadata->bitsInAb : 13;
        uint32_t m_maxABPixelValue = (1 << bitsInAb) - 1;
        max_value_of_AB_pixel = m_maxABPixelValue;
        min_value_of_AB_pixel = 0;
    }

    uint32_t new_max_value_of_AB_pixel = 1;
    uint32_t new_min_value_of_AB_pixel = 0xFFFF;

    // --- NEON normalization: process row by row ---
    float norm_factor = 255.0f / float(max_value_of_AB_pixel);
    float32x4_t normV = vdupq_n_f32(norm_factor);
    uint16x8_t minV = vdupq_n_u16((uint16_t)min_value_of_AB_pixel);
    uint16x8_t global_vmin = vdupq_n_u16(0xFFFF);
    uint16x8_t global_vmax = vdupq_n_u16(0);

    for (uint16_t y = 0; y < abHeight; ++y) {
        size_t row_start = y * abWidth;
        size_t x = 0;

        for (; x + neon_width <= abWidth; x += neon_width) {
            // Load 8 uint16 values
            uint16x8_t pix = vld1q_u16(abBuffer + row_start + x);

            // Subtract minimum (with saturation)
            uint16x8_t pix_sub = vqsubq_u16(pix, minV);

            // Convert to float32 for normalization (process 4 at a time)
            uint16x4_t pix_lo = vget_low_u16(pix_sub);
            uint16x4_t pix_hi = vget_high_u16(pix_sub);

            uint32x4_t pix32_lo = vmovl_u16(pix_lo);
            uint32x4_t pix32_hi = vmovl_u16(pix_hi);

            float32x4_t flo = vcvtq_f32_u32(pix32_lo);
            float32x4_t fhi = vcvtq_f32_u32(pix32_hi);

            // Normalize
            flo = vmulq_f32(flo, normV);
            fhi = vmulq_f32(fhi, normV);

            // Clamp to [0, 255]
            float32x4_t zero = vdupq_n_f32(0.0f);
            float32x4_t max_val = vdupq_n_f32(255.0f);
            flo = vminq_f32(vmaxq_f32(flo, zero), max_val);
            fhi = vminq_f32(vmaxq_f32(fhi, zero), max_val);

            // Convert back to uint16
            uint32x4_t ilo = vcvtq_u32_f32(flo);
            uint32x4_t ihi = vcvtq_u32_f32(fhi);

            uint16x4_t out_lo = vmovn_u32(ilo);
            uint16x4_t out_hi = vmovn_u32(ihi);

            uint16x8_t out = vcombine_u16(out_lo, out_hi);

            // Store result
            vst1q_u16(abBuffer + row_start + x, out);

            // Update min/max
            global_vmin = vminq_u16(global_vmin, out);
            global_vmax = vmaxq_u16(global_vmax, out);
        }

        // Scalar tail for this row
        for (; x < abWidth; ++x) {
            int val = int(abBuffer[row_start + x]) - int(min_value_of_AB_pixel);
            float pix = float(val) * norm_factor;
            if (pix < 0.0f)
                pix = 0.0f;
            if (pix > 255.0f)
                pix = 255.0f;
            abBuffer[row_start + x] = (uint8_t)pix;
        }
    }

    // Scalar reduction for new min/max
    uint16_t min_buf[neon_width], max_buf[neon_width];
    vst1q_u16(min_buf, global_vmin);
    vst1q_u16(max_buf, global_vmax);

    for (int j = 0; j < (int)neon_width; ++j) {
        new_min_value_of_AB_pixel =
            std::min(new_min_value_of_AB_pixel, (uint32_t)min_buf[j]);
        new_max_value_of_AB_pixel =
            std::max(new_max_value_of_AB_pixel, (uint32_t)max_buf[j]);
    }

    // --- Log scaling ---
    if (useLogScaling) {
        max_value_of_AB_pixel = new_max_value_of_AB_pixel;
        min_value_of_AB_pixel = new_min_value_of_AB_pixel;
        double maxLogVal =
            log10(1.0 + double(max_value_of_AB_pixel - min_value_of_AB_pixel));

        for (uint16_t y = 0; y < abHeight; ++y) {
            size_t row_start = y * abWidth;

            // Log scaling is harder to vectorize efficiently, use scalar
            for (size_t x = 0; x < abWidth; ++x) {
                double pix =
                    double(abBuffer[row_start + x]) - min_value_of_AB_pixel;
                double logPix = log10(1.0 + pix);
                pix = (logPix / maxLogVal) * 255.0;
                if (pix < 0.0)
                    pix = 0.0;
                if (pix > 255.0)
                    pix = 255.0;
                abBuffer[row_start + x] = (uint8_t)pix;
            }
        }
    }
}

// ARM NEON optimized AB image display
void ADIView::_displayAbImage_NEON() {
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

        normalizeABBuffer_NEON(_ab_video_data, frameWidth, frameHeight,
                               getAutoScale(), getLogImage());

        size_t bgrSize = 0;

        if (ab_video_data_8bit == nullptr) {
            ab_video_data_8bit = new uint8_t[frameHeight * frameWidth * 3];
        }

        // NEON-optimized BGR packing
        const size_t neon_width = 8;
        for (int y = 0; y < (int)frameHeight; ++y) {
            size_t row_start = y * frameWidth;
            size_t x = 0;

            for (; x + neon_width <= frameWidth; x += neon_width) {
                uint16x8_t v = vld1q_u16(_ab_video_data + row_start + x);
                uint8x8_t v8 = vmovn_u16(v);

                uint8_t buf[neon_width];
                vst1_u8(buf, v8);

                // Replicate to BGR
                for (int j = 0; j < (int)neon_width; ++j) {
                    uint8_t pix = buf[j];
                    ab_video_data_8bit[bgrSize++] = pix;
                    ab_video_data_8bit[bgrSize++] = pix;
                    ab_video_data_8bit[bgrSize++] = pix;
                }
            }

            // Scalar tail
            for (; x < frameWidth; ++x) {
                uint8_t pix = (uint8_t)_ab_video_data[row_start + x];
                ab_video_data_8bit[bgrSize++] = pix;
                ab_video_data_8bit[bgrSize++] = pix;
                ab_video_data_8bit[bgrSize++] = pix;
            }
        }

        ab_data_ready = true;
        ab_data_ready_cv.notify_one();

        if (_ab_video_data != nullptr) {
            delete[] _ab_video_data;
        }

#ifdef AB_TIME
        {
            std::ostringstream oss;
            oss << "AB (NEON): " << endTimerAndUpdate(timerStart, &timeABQ)
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

// ARM NEON optimized depth image display
void ADIView::_displayDepthImage_NEON() {
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

        m_capturedFrame->getData("depth", &depth_video_data);

        if (depth_video_data == nullptr) {
            return;
        }

        aditof::FrameDataDetails frameDepthDetails;
        m_capturedFrame->getDataDetails("depth", frameDepthDetails);

        int frameHeight = static_cast<int>(frameDepthDetails.height);
        int frameWidth = static_cast<int>(frameDepthDetails.width);

        constexpr uint8_t PixelMax = std::numeric_limits<uint8_t>::max();
        size_t imageSize = frameHeight * frameWidth;
        size_t bgrSize = 0;

        if (depth_video_data_8bit == nullptr) {
            depth_video_data_8bit = new uint8_t[frameHeight * frameWidth * 3];
        }

        // Process with NEON
        constexpr int PixelBlock = 8;
        size_t i = 0;

        float32x4_t minRangeV = vdupq_n_f32((float)minRange);
        float32x4_t maxRangeV = vdupq_n_f32((float)maxRange);
        float32x4_t rangeV = vdupq_n_f32((2.f / 3.f) / (maxRange - minRange));

        for (; i + PixelBlock <= imageSize; i += PixelBlock) {
            // Load 8 uint16 values
            uint16x8_t vSrc16 = vld1q_u16(&depth_video_data[i]);

            // Process in two batches of 4
            uint16x4_t vSrc16_lo = vget_low_u16(vSrc16);
            uint16x4_t vSrc16_hi = vget_high_u16(vSrc16);

            uint32x4_t vSrc32_lo = vmovl_u16(vSrc16_lo);
            uint32x4_t vSrc32_hi = vmovl_u16(vSrc16_hi);

            float32x4_t vSrcF_lo = vcvtq_f32_u32(vSrc32_lo);
            float32x4_t vSrcF_hi = vcvtq_f32_u32(vSrc32_hi);

            // Clamp and normalize
            vSrcF_lo = vminq_f32(vmaxq_f32(vSrcF_lo, minRangeV), maxRangeV);
            vSrcF_hi = vminq_f32(vmaxq_f32(vSrcF_hi, minRangeV), maxRangeV);

            float32x4_t vHue_lo =
                vmulq_f32(vsubq_f32(vSrcF_lo, minRangeV), rangeV);
            float32x4_t vHue_hi =
                vmulq_f32(vsubq_f32(vSrcF_hi, minRangeV), rangeV);

            // Store and convert to RGB (scalar for now, HSV->RGB is complex to vectorize)
            float hues[PixelBlock];
            vst1q_f32(&hues[0], vHue_lo);
            vst1q_f32(&hues[4], vHue_hi);

            for (int j = 0; j < PixelBlock; ++j) {
                if (depth_video_data[i + j] == 0) {
                    depth_video_data_8bit[bgrSize++] = 0;
                    depth_video_data_8bit[bgrSize++] = 0;
                    depth_video_data_8bit[bgrSize++] = 0;
                } else {
                    float fRed, fGreen, fBlue;
                    ColorConvertHSVtoRGB(hues[j], 1.f, 1.f, fRed, fGreen,
                                         fBlue);
                    depth_video_data_8bit[bgrSize++] =
                        static_cast<uint8_t>(fBlue * PixelMax);
                    depth_video_data_8bit[bgrSize++] =
                        static_cast<uint8_t>(fGreen * PixelMax);
                    depth_video_data_8bit[bgrSize++] =
                        static_cast<uint8_t>(fRed * PixelMax);
                }
            }
        }

        // Tail loop
        for (; i < imageSize; ++i) {
            if (depth_video_data[i] == 0) {
                depth_video_data_8bit[bgrSize++] = 0;
                depth_video_data_8bit[bgrSize++] = 0;
                depth_video_data_8bit[bgrSize++] = 0;
            } else {
                float fRed, fGreen, fBlue;
                hsvColorMap(depth_video_data[i], maxRange, minRange, fRed,
                            fGreen, fBlue);
                depth_video_data_8bit[bgrSize++] =
                    static_cast<uint8_t>(fBlue * PixelMax);
                depth_video_data_8bit[bgrSize++] =
                    static_cast<uint8_t>(fGreen * PixelMax);
                depth_video_data_8bit[bgrSize++] =
                    static_cast<uint8_t>(fRed * PixelMax);
            }
        }

#ifdef DEPTH_TIME
        {
            std::ostringstream oss;
            oss << "Depth (NEON): "
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

// ARM NEON optimized point cloud image display
void ADIView::_displayPointCloudImage_NEON() {
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

        float fRed = 0.f;
        float fGreen = 0.f;
        float fBlue = 0.f;
        size_t bgrSize = 0;
        size_t cntr = 0;
        vertexArraySize = 0;

        bool haveAb = m_capturedFrame->haveDataType("ab");

        if (haveAb) {
            std::unique_lock<std::mutex> lock(ab_data_ready_mtx);
            ab_data_ready_cv.wait(lock, [this] { return ab_data_ready; });
        }

        // NEON-accelerated XYZ conversion
        //float32x4_t maxXV = vdupq_n_f32(Max_X);
        //float32x4_t maxYV = vdupq_n_f32(Max_Y);
        //float32x4_t maxZV = vdupq_n_f32(Max_Z);

        for (uint32_t i = 0; i < pointcloudTableSize; i += 3) {
            // XYZ normalization
            normalized_vertices[bgrSize++] =
                static_cast<float>(pointCloud_video_data[i]) / Max_X;
            normalized_vertices[bgrSize++] =
                static_cast<float>(pointCloud_video_data[i + 1]) / Max_Y;
            normalized_vertices[bgrSize++] =
                static_cast<float>(pointCloud_video_data[i + 2]) / Max_Z;

            // RGB
            if ((int16_t)pointCloud_video_data[i + 2] == 0) {
                fRed = fGreen = fBlue = 0.0f;
                if (m_pccolour == 1) {
                    cntr += 3;
                }
            } else {
                if (m_pccolour == 2) {
                    fRed = fGreen = fBlue = 1.0f;
                } else if (m_pccolour == 1 && haveAb) {
                    fRed = (float)ab_video_data_8bit[cntr] / 255.0f;
                    fGreen = (float)ab_video_data_8bit[cntr + 1] / 255.0f;
                    fBlue = (float)ab_video_data_8bit[cntr + 2] / 255.0f;
                    cntr += 3;
                } else {
                    hsvColorMap((pointCloud_video_data[i + 2]), maxRange,
                                minRange, fRed, fGreen, fBlue);
                }
            }
            normalized_vertices[bgrSize++] = fRed;
            normalized_vertices[bgrSize++] = fGreen;
            normalized_vertices[bgrSize++] = fBlue;
        }

        normalized_vertices[bgrSize++] = 0.0f;
        normalized_vertices[bgrSize++] = 0.0f;
        normalized_vertices[bgrSize++] = 0.0f;
        normalized_vertices[bgrSize++] = 1.0f;
        normalized_vertices[bgrSize++] = 1.0f;
        normalized_vertices[bgrSize++] = 1.0f;

        vertexArraySize = (pointcloudTableSize + 1) * sizeof(float) * 3;

#ifdef PC_TIME
        {
            std::ostringstream oss;
            oss << "PC (NEON): " << endTimerAndUpdate(timerStart, &timePCQ)
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
