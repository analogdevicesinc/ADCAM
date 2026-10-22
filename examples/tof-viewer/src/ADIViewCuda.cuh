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
#ifndef ADIVIEW_CUDA_H
#define ADIVIEW_CUDA_H

#include <cstddef>
#include <cstdint>

// CUDA kernel declarations for AB buffer processing
void normalizeABBuffer_CUDA(uint16_t *d_abBuffer, uint16_t *h_abBuffer,
                            uint16_t abWidth, uint16_t abHeight,
                            bool advanceScaling, bool useLogScaling,
                            uint8_t bitsInAb);

void convertABtoBGR_CUDA(uint16_t *d_abBuffer, uint8_t *d_bgrBuffer,
                         uint8_t *h_bgrBuffer, int width, int height);

// CUDA kernel declarations for depth buffer processing
void processDepthImage_CUDA(uint16_t *d_depthBuffer, uint16_t *h_depthBuffer,
                            uint8_t *d_bgrBuffer, uint8_t *h_bgrBuffer,
                            int width, int height, int minRange, int maxRange);

// CUDA kernel declarations for point cloud processing
void processPointCloud_CUDA(int16_t *d_xyzBuffer, int16_t *h_xyzBuffer,
                            float *d_vertexBuffer, float *h_vertexBuffer,
                            uint8_t *d_abBuffer, int width, int height,
                            float maxX, float maxY, float maxZ, int minRange,
                            int maxRange, int pcColour, bool haveAb);

#endif // ADIVIEW_CUDA_H
