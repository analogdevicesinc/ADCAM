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

#ifndef ADIPOINTCLOUDSHADERS_H
#define ADIPOINTCLOUDSHADERS_H

#include "ADIPlatformConfig.h"

namespace adiviewer {

/**
 * @brief Point cloud vertex shader for Jetson Orin Nano (OpenGL 3.3 core profile)
 * 
 * Uses modern GLSL features:
 * - layout(location = N) attribute binding
 * - in/out variable syntax
 * - Core profile (no legacy fixed-function pipeline)
 */
constexpr char const POINT_CLOUD_VERTEX_SHADER_JETSON[] = R"(
    #version 330 core
    layout (location = 0) in vec3 aPos;
    layout (location = 1) in vec3 hsvColor;

    uniform mat4 mvp; // Combined model-view-projection
    uniform float uPointSize;

    out vec4 vColor;

    void main()
    {
        // Flip horizontally and compute position in one step
        vec3 pos = vec3(-aPos.x, aPos.y, aPos.z);
        gl_Position = mvp * vec4(pos, 1.0);
        
        // Avoid branching - use smooth step for point size
        float isOrigin = step(length(pos), 0.0001);
        gl_PointSize = mix(uPointSize, 10.0, isOrigin);
        vColor = mix(vec4(hsvColor, 1.0), vec4(1.0, 1.0, 1.0, 1.0), isOrigin);
    }
)";

/**
 * @brief Point cloud fragment shader for Jetson Orin Nano (OpenGL 3.3 core profile)
 */
constexpr char const POINT_CLOUD_FRAGMENT_SHADER_JETSON[] = R"(
    #version 330 core
    in vec4 vColor;
    out vec4 FragColor;
    void main()
    {
        FragColor = vColor;
    }
)";

/**
 * @brief Point cloud vertex shader for Raspberry Pi 5 (OpenGL 3.0 compatibility mode)
 * 
 * Uses legacy GLSL 1.30 features:
 * - attribute/varying keywords (pre GLSL 1.30 syntax)
 * - No layout(location = N) support
 * - Compatibility profile with fixed-function pipeline support
 * 
 * NOTE: GLSL 1.50 is NOT supported on RPi GPU - must use 1.30 or earlier!
 */
constexpr char const POINT_CLOUD_VERTEX_SHADER_RPI[] = R"(
    #version 130
    attribute vec3 aPos;
    attribute vec3 hsvColor;

    uniform mat4 mvp; // Combined model-view-projection
    uniform float uPointSize;

    varying vec4 vColor;

    void main()
    {
        // Flip horizontally and compute position in one step
        vec3 pos = vec3(-aPos.x, aPos.y, aPos.z);
        gl_Position = mvp * vec4(pos, 1.0);
        
        // Avoid branching - use smooth step for point size
        float isOrigin = step(length(pos), 0.0001);
        gl_PointSize = mix(uPointSize, 10.0, isOrigin);
        vColor = mix(vec4(hsvColor, 1.0), vec4(1.0, 1.0, 1.0, 1.0), isOrigin);
    }
)";

/**
 * @brief Point cloud fragment shader for Raspberry Pi 5 (OpenGL 3.0 compatibility mode)
 */
constexpr char const POINT_CLOUD_FRAGMENT_SHADER_RPI[] = R"(
    #version 130
    varying vec4 vColor;
    void main()
    {
        gl_FragColor = vColor;
    }
)";

/**
 * @brief Get vertex shader source code for the current platform
 * @return Pointer to null-terminated shader source string
 * 
 * @note Platform validation is done at compile-time in ADIPlatformConfig.h
 *       This function is guaranteed to return a valid shader for the configured platform.
 */
inline const char *GetPointCloudVertexShader() {
#ifdef NVIDIA
    return POINT_CLOUD_VERTEX_SHADER_JETSON;
#else // RPI
    return POINT_CLOUD_VERTEX_SHADER_RPI;
#endif
}

/**
 * @brief Get fragment shader source code for the current platform
 * @return Pointer to null-terminated shader source string
 * 
 * @note Platform validation is done at compile-time in ADIPlatformConfig.h
 *       This function is guaranteed to return a valid shader for the configured platform.
 */
inline const char *GetPointCloudFragmentShader() {
#ifdef NVIDIA
    return POINT_CLOUD_FRAGMENT_SHADER_JETSON;
#else // RPI
    return POINT_CLOUD_FRAGMENT_SHADER_RPI;
#endif
}

/**
 * @brief Get both shaders for the current platform
 * @param vertexShader Output pointer to vertex shader source
 * @param fragmentShader Output pointer to fragment shader source
 */
inline void GetPointCloudShaders(const char *&vertexShader,
                                 const char *&fragmentShader) {
    vertexShader = GetPointCloudVertexShader();
    fragmentShader = GetPointCloudFragmentShader();
}

} // namespace adiviewer

#endif // ADIPOINTCLOUDSHADERS_H
