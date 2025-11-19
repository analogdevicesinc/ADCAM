/********************************************************************************/
/*                                                                              */
/* Copyright (c) 2025 Analog Devices Inc.                                       */
/* CUDA header for ADIView GPU-accelerated implementations                      */
/*                                                                              */
/********************************************************************************/

#ifndef ADIVIEW_CUDA_H
#define ADIVIEW_CUDA_H

#include <cstddef>
#include <cstdint>

// CUDA kernel declarations for AB buffer processing
void normalizeABBuffer_CUDA(uint16_t *d_abBuffer, uint16_t *h_abBuffer,
                            uint16_t abWidth, uint16_t abHeight,
                            bool advanceScaling, bool useLogScaling);

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
