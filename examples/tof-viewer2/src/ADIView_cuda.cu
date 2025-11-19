/********************************************************************************/
/*                                                                              */
/* Copyright (c) 2025 Analog Devices Inc.                                       */
/* CUDA GPU-accelerated implementations for ADIView                             */
/*                                                                              */
/********************************************************************************/

#include "ADIViewCuda.cuh"
#include <algorithm>
#include <cmath>
#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <iostream>

// Error checking macro
#define CUDA_CHECK(call)                                                       \
    do {                                                                       \
        cudaError_t error = call;                                              \
        if (error != cudaSuccess) {                                            \
            std::cerr << "CUDA error at " << __FILE__ << ":" << __LINE__       \
                      << " - " << cudaGetErrorString(error) << std::endl;      \
        }                                                                      \
    } while (0)

// CUDA kernel for min/max reduction
__global__ void minMaxKernel(uint16_t *buffer, int size, uint32_t *minVal,
                             uint32_t *maxVal) {
    extern __shared__ uint32_t sdata[];
    uint32_t *smin = sdata;
    uint32_t *smax = &sdata[blockDim.x];

    int tid = threadIdx.x;
    int idx = blockIdx.x * blockDim.x + threadIdx.x;

    uint32_t localMin = 0xFFFF;
    uint32_t localMax = 0;

    if (idx < size) {
        localMin = buffer[idx];
        localMax = buffer[idx];
    }

    smin[tid] = localMin;
    smax[tid] = localMax;
    __syncthreads();

    // Reduction in shared memory
    for (unsigned int s = blockDim.x / 2; s > 0; s >>= 1) {
        if (tid < s) {
            smin[tid] = min(smin[tid], smin[tid + s]);
            smax[tid] = max(smax[tid], smax[tid + s]);
        }
        __syncthreads();
    }

    if (tid == 0) {
        atomicMin(minVal, smin[0]);
        atomicMax(maxVal, smax[0]);
    }
}

// CUDA kernel for AB buffer normalization
__global__ void normalizeKernel(uint16_t *buffer, int width, int height,
                                uint32_t minVal, uint32_t maxVal,
                                float normFactor) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;

    if (x < width && y < height) {
        int idx = y * width + x;
        int val = (int)buffer[idx] - (int)minVal;
        float pix = (float)val * normFactor;
        pix = fminf(fmaxf(pix, 0.0f), 255.0f);
        buffer[idx] = (uint8_t)pix;
    }
}

// CUDA kernel for log scaling
__global__ void logScaleKernel(uint16_t *buffer, int width, int height,
                               uint32_t minVal, double maxLogVal) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;

    if (x < width && y < height) {
        int idx = y * width + x;
        double pix = (double)buffer[idx] - minVal;
        double logPix = log10(1.0 + pix);
        pix = (logPix / maxLogVal) * 255.0;
        pix = fmin(fmax(pix, 0.0), 255.0);
        buffer[idx] = (uint8_t)pix;
    }
}

// CUDA kernel for converting grayscale to BGR
__global__ void convertToBGRKernel(uint16_t *input, uint8_t *output, int width,
                                   int height) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;

    if (x < width && y < height) {
        int idx = y * width + x;
        uint8_t pix = (uint8_t)input[idx];
        int bgrIdx = idx * 3;
        output[bgrIdx + 0] = pix; // B
        output[bgrIdx + 1] = pix; // G
        output[bgrIdx + 2] = pix; // R
    }
}

// Device function for HSV to RGB conversion
__device__ void ColorConvertHSVtoRGB_device(float h, float s, float v,
                                            float &out_r, float &out_g,
                                            float &out_b) {
    if (s == 0.0f) {
        out_r = out_g = out_b = v;
        return;
    }

    h = fmodf(h, 1.0f) / (60.0f / 360.0f);
    int i = (int)h;
    float f = h - (float)i;
    float p = v * (1.0f - s);
    float q = v * (1.0f - s * f);
    float t = v * (1.0f - s * (1.0f - f));

    switch (i) {
    case 0:
        out_r = v;
        out_g = t;
        out_b = p;
        break;
    case 1:
        out_r = q;
        out_g = v;
        out_b = p;
        break;
    case 2:
        out_r = p;
        out_g = v;
        out_b = t;
        break;
    case 3:
        out_r = p;
        out_g = q;
        out_b = v;
        break;
    case 4:
        out_r = t;
        out_g = p;
        out_b = v;
        break;
    case 5:
    default:
        out_r = v;
        out_g = p;
        out_b = q;
        break;
    }
}

// CUDA kernel for depth image processing with HSV color mapping
__global__ void processDepthKernel(uint16_t *depth, uint8_t *bgr, int width,
                                   int height, int minRange, int maxRange) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;

    if (x < width && y < height) {
        int idx = y * width + x;
        uint16_t depthVal = depth[idx];

        if (depthVal == 0) {
            int bgrIdx = idx * 3;
            bgr[bgrIdx + 0] = 0;
            bgr[bgrIdx + 1] = 0;
            bgr[bgrIdx + 2] = 0;
        } else {
            // Clamp value
            int clampedVal = min(max((int)depthVal, minRange), maxRange);

            // Calculate hue
            float hue = (clampedVal - minRange) / (float)(maxRange - minRange);
            hue *= (2.0f / 3.0f); // Map to blue-red range

            // Convert HSV to RGB
            float fRed, fGreen, fBlue;
            ColorConvertHSVtoRGB_device(hue, 1.0f, 1.0f, fRed, fGreen, fBlue);

            int bgrIdx = idx * 3;
            bgr[bgrIdx + 0] = (uint8_t)(fBlue * 255.0f);
            bgr[bgrIdx + 1] = (uint8_t)(fGreen * 255.0f);
            bgr[bgrIdx + 2] = (uint8_t)(fRed * 255.0f);
        }
    }
}

// CUDA kernel for point cloud processing
__global__ void processPointCloudKernel(int16_t *xyz, float *vertices,
                                        uint8_t *abData, int width, int height,
                                        float maxX, float maxY, float maxZ,
                                        int minRange, int maxRange,
                                        int pcColour, bool haveAb) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;

    if (x < width && y < height) {
        int idx = y * width + x;
        int xyzIdx = idx * 3;
        int vertIdx = idx * 6; // XYZ + RGB

        // Normalize XYZ
        vertices[vertIdx + 0] = (float)xyz[xyzIdx + 0] / maxX;
        vertices[vertIdx + 1] = (float)xyz[xyzIdx + 1] / maxY;
        vertices[vertIdx + 2] = (float)xyz[xyzIdx + 2] / maxZ;

        // Process RGB
        if (xyz[xyzIdx + 2] == 0) {
            vertices[vertIdx + 3] = 0.0f;
            vertices[vertIdx + 4] = 0.0f;
            vertices[vertIdx + 5] = 0.0f;
        } else {
            if (pcColour == 2) {
                vertices[vertIdx + 3] = 1.0f;
                vertices[vertIdx + 4] = 1.0f;
                vertices[vertIdx + 5] = 1.0f;
            } else if (pcColour == 1 && haveAb) {
                int abIdx = idx * 3;
                vertices[vertIdx + 3] = (float)abData[abIdx + 0] / 255.0f; // R
                vertices[vertIdx + 4] = (float)abData[abIdx + 1] / 255.0f; // G
                vertices[vertIdx + 5] = (float)abData[abIdx + 2] / 255.0f; // B
            } else {
                // HSV color map based on Z value
                int clampedVal =
                    min(max((int)xyz[xyzIdx + 2], minRange), maxRange);
                float hue =
                    (clampedVal - minRange) / (float)(maxRange - minRange);
                hue *= (2.0f / 3.0f);

                float fRed, fGreen, fBlue;
                ColorConvertHSVtoRGB_device(hue, 1.0f, 1.0f, fRed, fGreen,
                                            fBlue);

                vertices[vertIdx + 3] = fRed;
                vertices[vertIdx + 4] = fGreen;
                vertices[vertIdx + 5] = fBlue;
            }
        }
    }
}

// Host functions implementations

void normalizeABBuffer_CUDA(uint16_t *d_abBuffer, uint16_t *h_abBuffer,
                            uint16_t abWidth, uint16_t abHeight,
                            bool advanceScaling, bool useLogScaling) {
    int imageSize = abWidth * abHeight;

    // Allocate device memory if not already allocated
    static uint16_t *d_buffer = nullptr;
    static int lastSize = 0;

    if (d_buffer == nullptr || lastSize != imageSize) {
        if (d_buffer)
            CUDA_CHECK(cudaFree(d_buffer));
        CUDA_CHECK(cudaMalloc(&d_buffer, imageSize * sizeof(uint16_t)));
        lastSize = imageSize;
    }

    // Copy to device
    CUDA_CHECK(cudaMemcpy(d_buffer, h_abBuffer, imageSize * sizeof(uint16_t),
                          cudaMemcpyHostToDevice));

    uint32_t minVal = 0;
    uint32_t maxVal = 1;

    if (advanceScaling) {
        // Allocate device memory for min/max
        uint32_t *d_min, *d_max;
        CUDA_CHECK(cudaMalloc(&d_min, sizeof(uint32_t)));
        CUDA_CHECK(cudaMalloc(&d_max, sizeof(uint32_t)));

        uint32_t initMin = 0xFFFF;
        uint32_t initMax = 0;
        CUDA_CHECK(cudaMemcpy(d_min, &initMin, sizeof(uint32_t),
                              cudaMemcpyHostToDevice));
        CUDA_CHECK(cudaMemcpy(d_max, &initMax, sizeof(uint32_t),
                              cudaMemcpyHostToDevice));

        // Launch min/max kernel
        int blockSize = 256;
        int numBlocks = (imageSize + blockSize - 1) / blockSize;
        minMaxKernel<<<numBlocks, blockSize,
                       blockSize * 2 * sizeof(uint32_t)>>>(d_buffer, imageSize,
                                                           d_min, d_max);

        CUDA_CHECK(cudaMemcpy(&minVal, d_min, sizeof(uint32_t),
                              cudaMemcpyDeviceToHost));
        CUDA_CHECK(cudaMemcpy(&maxVal, d_max, sizeof(uint32_t),
                              cudaMemcpyDeviceToHost));

        CUDA_CHECK(cudaFree(d_min));
        CUDA_CHECK(cudaFree(d_max));

        maxVal -= minVal;
    } else {
        maxVal = (1 << 13) - 1;
        minVal = 0;
    }

    // Normalize
    float normFactor = 255.0f / (float)maxVal;
    dim3 blockDim(16, 16);
    dim3 gridDim((abWidth + blockDim.x - 1) / blockDim.x,
                 (abHeight + blockDim.y - 1) / blockDim.y);

    normalizeKernel<<<gridDim, blockDim>>>(d_buffer, abWidth, abHeight, minVal,
                                           maxVal, normFactor);

    // Log scaling if requested
    if (useLogScaling) {
        // Recalculate min/max after normalization
        uint32_t *d_min, *d_max;
        CUDA_CHECK(cudaMalloc(&d_min, sizeof(uint32_t)));
        CUDA_CHECK(cudaMalloc(&d_max, sizeof(uint32_t)));

        uint32_t initMin = 0xFFFF;
        uint32_t initMax = 0;
        CUDA_CHECK(cudaMemcpy(d_min, &initMin, sizeof(uint32_t),
                              cudaMemcpyHostToDevice));
        CUDA_CHECK(cudaMemcpy(d_max, &initMax, sizeof(uint32_t),
                              cudaMemcpyHostToDevice));

        int blockSize = 256;
        int numBlocks = (imageSize + blockSize - 1) / blockSize;
        minMaxKernel<<<numBlocks, blockSize,
                       blockSize * 2 * sizeof(uint32_t)>>>(d_buffer, imageSize,
                                                           d_min, d_max);

        CUDA_CHECK(cudaMemcpy(&minVal, d_min, sizeof(uint32_t),
                              cudaMemcpyDeviceToHost));
        CUDA_CHECK(cudaMemcpy(&maxVal, d_max, sizeof(uint32_t),
                              cudaMemcpyDeviceToHost));

        CUDA_CHECK(cudaFree(d_min));
        CUDA_CHECK(cudaFree(d_max));

        double maxLogVal = log10(1.0 + (double)(maxVal - minVal));

        logScaleKernel<<<gridDim, blockDim>>>(d_buffer, abWidth, abHeight,
                                              minVal, maxLogVal);
    }

    // Copy back to host
    CUDA_CHECK(cudaMemcpy(h_abBuffer, d_buffer, imageSize * sizeof(uint16_t),
                          cudaMemcpyDeviceToHost));
}

void convertABtoBGR_CUDA(uint16_t *d_abBuffer, uint8_t *d_bgrBuffer,
                         uint8_t *h_bgrBuffer, int width, int height) {
    int imageSize = width * height;

    static uint16_t *d_input = nullptr;
    static uint8_t *d_output = nullptr;
    static int lastSize = 0;

    if (d_input == nullptr || lastSize != imageSize) {
        if (d_input)
            CUDA_CHECK(cudaFree(d_input));
        if (d_output)
            CUDA_CHECK(cudaFree(d_output));

        CUDA_CHECK(cudaMalloc(&d_input, imageSize * sizeof(uint16_t)));
        CUDA_CHECK(cudaMalloc(&d_output, imageSize * 3 * sizeof(uint8_t)));
        lastSize = imageSize;
    }

    CUDA_CHECK(cudaMemcpy(d_input, d_abBuffer, imageSize * sizeof(uint16_t),
                          cudaMemcpyHostToDevice));

    dim3 blockDim(16, 16);
    dim3 gridDim((width + blockDim.x - 1) / blockDim.x,
                 (height + blockDim.y - 1) / blockDim.y);

    convertToBGRKernel<<<gridDim, blockDim>>>(d_input, d_output, width, height);

    CUDA_CHECK(cudaMemcpy(h_bgrBuffer, d_output,
                          imageSize * 3 * sizeof(uint8_t),
                          cudaMemcpyDeviceToHost));
}

void processDepthImage_CUDA(uint16_t *d_depthBuffer, uint16_t *h_depthBuffer,
                            uint8_t *d_bgrBuffer, uint8_t *h_bgrBuffer,
                            int width, int height, int minRange, int maxRange) {
    int imageSize = width * height;

    static uint16_t *d_depth = nullptr;
    static uint8_t *d_bgr = nullptr;
    static int lastSize = 0;

    if (d_depth == nullptr || lastSize != imageSize) {
        if (d_depth)
            CUDA_CHECK(cudaFree(d_depth));
        if (d_bgr)
            CUDA_CHECK(cudaFree(d_bgr));

        CUDA_CHECK(cudaMalloc(&d_depth, imageSize * sizeof(uint16_t)));
        CUDA_CHECK(cudaMalloc(&d_bgr, imageSize * 3 * sizeof(uint8_t)));
        lastSize = imageSize;
    }

    CUDA_CHECK(cudaMemcpy(d_depth, h_depthBuffer, imageSize * sizeof(uint16_t),
                          cudaMemcpyHostToDevice));

    dim3 blockDim(16, 16);
    dim3 gridDim((width + blockDim.x - 1) / blockDim.x,
                 (height + blockDim.y - 1) / blockDim.y);

    processDepthKernel<<<gridDim, blockDim>>>(d_depth, d_bgr, width, height,
                                              minRange, maxRange);

    CUDA_CHECK(cudaMemcpy(h_bgrBuffer, d_bgr, imageSize * 3 * sizeof(uint8_t),
                          cudaMemcpyDeviceToHost));
}

void processPointCloud_CUDA(int16_t *d_xyzBuffer, int16_t *h_xyzBuffer,
                            float *d_vertexBuffer, float *h_vertexBuffer,
                            uint8_t *d_abBuffer, int width, int height,
                            float maxX, float maxY, float maxZ, int minRange,
                            int maxRange, int pcColour, bool haveAb) {
    int imageSize = width * height;

    static int16_t *d_xyz = nullptr;
    static float *d_vertices = nullptr;
    static uint8_t *d_ab = nullptr;
    static int lastSize = 0;

    if (d_xyz == nullptr || lastSize != imageSize) {
        if (d_xyz)
            CUDA_CHECK(cudaFree(d_xyz));
        if (d_vertices)
            CUDA_CHECK(cudaFree(d_vertices));
        if (d_ab)
            CUDA_CHECK(cudaFree(d_ab));

        CUDA_CHECK(cudaMalloc(&d_xyz, imageSize * 3 * sizeof(int16_t)));
        CUDA_CHECK(cudaMalloc(&d_vertices,
                              imageSize * 6 * sizeof(float))); // XYZ + RGB
        CUDA_CHECK(cudaMalloc(&d_ab, imageSize * 3 * sizeof(uint8_t)));
        lastSize = imageSize;
    }

    CUDA_CHECK(cudaMemcpy(d_xyz, h_xyzBuffer, imageSize * 3 * sizeof(int16_t),
                          cudaMemcpyHostToDevice));

    if (haveAb && d_abBuffer != nullptr) {
        CUDA_CHECK(cudaMemcpy(d_ab, d_abBuffer, imageSize * 3 * sizeof(uint8_t),
                              cudaMemcpyHostToDevice));
    }

    dim3 blockDim(16, 16);
    dim3 gridDim((width + blockDim.x - 1) / blockDim.x,
                 (height + blockDim.y - 1) / blockDim.y);

    processPointCloudKernel<<<gridDim, blockDim>>>(
        d_xyz, d_vertices, d_ab, width, height, maxX, maxY, maxZ, minRange,
        maxRange, pcColour, haveAb);

    CUDA_CHECK(cudaMemcpy(h_vertexBuffer, d_vertices,
                          imageSize * 6 * sizeof(float),
                          cudaMemcpyDeviceToHost));
}
