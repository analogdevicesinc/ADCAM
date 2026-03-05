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

#ifndef ADIPLATFORMCONFIG_H
#define ADIPLATFORMCONFIG_H

#include <string>

// Compile-time validation: Ensure exactly one platform is defined
#if !defined(NVIDIA) && !defined(RPI) && !defined(WSL2)
#warning                                                                         \
    "No valid platform defined! CMAKE must define one: -DNVIDIA=ON, -DRPI=ON, or -DWSL2=ON"
#endif

#if (defined(NVIDIA) && defined(RPI)) || (defined(NVIDIA) && defined(WSL2)) || (defined(RPI) && defined(WSL2))
#warning                                                                         \
    "Multiple platforms defined! CMAKE should only define one: -DNVIDIA=ON, -DRPI=ON, or -DWSL2=ON"
#endif

namespace adiviewer {

#if defined(WSL2) && !defined(WSL2_GL_VERSION_MAJOR)
#define WSL2_GL_VERSION_MAJOR 3
#define WSL2_GL_VERSION_MINOR 3
#endif

/**
 * @brief Enum of supported platforms for OpenGL/GLSL configuration
 */
enum class Platform {
    JETSON_ORIN_NANO, /**< NVIDIA Jetson Orin Nano (OpenGL 3.3+ core profile) */
    RASPBERRY_PI_5,   /**< Raspberry Pi 5 (OpenGL 3.0 compatibility profile) */
    WSL2_PLATFORM,    /**< Windows Subsystem for Linux 2 (OpenGL 3.3+ core profile) */
};

/**
 * @brief Platform capabilities and OpenGL/GLSL configuration
 */
struct PlatformConfig {
    Platform platform;
    int glVersionMajor;
    int glVersionMinor;
    bool
        usesCoreProfile; /**< true = core profile, false = compatibility profile */
    int glslVersionMajor;
    int glslVersionMinor;
    bool
        supportsLayoutLocation; /**< true = supports layout(location = N) in shaders */
    const char
        *glslVersionString; /**< e.g., "#version 330 core" or "#version 130" */
    const char *name;       /**< Human-readable platform name */
};

/**
 * @brief Get platform configuration for the current build
 * @return PlatformConfig structure with OpenGL/GLSL settings for this platform
 * 
 * @note Platform is validated at compile time above.
 *       This function is guaranteed to return a valid configuration.
 */
inline PlatformConfig GetCurrentPlatformConfig() {
#ifdef NVIDIA
    // Jetson Orin Nano: Modern OpenGL 3.3+ core profile
    return PlatformConfig{Platform::JETSON_ORIN_NANO,
                          3,    // OpenGL major version
                          3,    // OpenGL minor version
                          true, // uses core profile
                          3,    // GLSL major version
                          30,   // GLSL minor version (330 = version 3.30)
                          true, // supports layout(location = N)
                          "#version 330 core",
                          "Jetson Orin Nano (OpenGL 3.3 core, GLSL 330)"};
#elif defined(WSL2)
    // Windows Subsystem for Linux 2 (WSL2): OpenGL override via CMake option
    // WSL2 with Mesa typically provides OpenGL 3.3; GPU passthrough (4.6+) requires
    // Windows GPU drivers + WSL2 GPU support (wsl.exe --update) and .wslconfig GPU=true
#if WSL2_GL_VERSION_MAJOR == 4
    return PlatformConfig{Platform::WSL2_PLATFORM,
                          4,    // OpenGL major version
                          6,    // OpenGL minor version
                          true, // uses core profile
                          4,    // GLSL major version
                          60,   // GLSL minor version (460 = version 4.60)
                          true, // supports layout(location = N)
                          "#version 460 core",
                          "WSL2 (OpenGL 4.6 core, GLSL 460)"};
#else
    return PlatformConfig{Platform::WSL2_PLATFORM,
                          3,    // OpenGL major version
                          3,    // OpenGL minor version
                          true, // uses core profile
                          3,    // GLSL major version
                          30,   // GLSL minor version (330 = version 3.30)
                          true, // supports layout(location = N)
                          "#version 330 core",
                          "WSL2 (OpenGL 3.3 core, GLSL 330)"};
#endif
#else // RPI
    // Raspberry Pi 5: Limited to OpenGL 3.0 compatibility profile
    // GLSL max is 1.30 (GLSL 1.50 is NOT supported by RPi GPU)
    return PlatformConfig{Platform::RASPBERRY_PI_5,
                          3,     // OpenGL major version
                          0,     // OpenGL minor version
                          false, // uses compatibility profile
                          1,     // GLSL major version
                          30,    // GLSL minor version (130 = version 1.30)
                          false, // does NOT support layout(location = N)
                          "#version 130",
                          "Raspberry Pi 5 (OpenGL 3.0 compat, GLSL 130)"};
#endif
}

/**
 * @brief Helper to get information about a platform
 * @param platform The platform to query
 * @return PlatformConfig structure for that platform
 */
inline PlatformConfig GetPlatformConfig(Platform platform) {
    switch (platform) {
    case Platform::JETSON_ORIN_NANO:
        return PlatformConfig{Platform::JETSON_ORIN_NANO,
                              3,
                              3,
                              true,
                              3,
                              30,
                              true,
                              "#version 330 core",
                              "Jetson Orin Nano (OpenGL 3.3 core, GLSL 330)"};
    case Platform::RASPBERRY_PI_5:
        return PlatformConfig{Platform::RASPBERRY_PI_5,
                              3,
                              0,
                              false,
                              1,
                              30,
                              false,
                              "#version 130",
                              "Raspberry Pi 5 (OpenGL 3.0 compat, GLSL 130)"};
    case Platform::WSL2_PLATFORM:
#if WSL2_GL_VERSION_MAJOR == 4
        return PlatformConfig{Platform::WSL2_PLATFORM,
                              4,
                              6,
                              true,
                              4,
                              60,
                              true,
                              "#version 460 core",
                              "WSL2 (OpenGL 4.6 core, GLSL 460)"};
#else
        return PlatformConfig{Platform::WSL2_PLATFORM,
                              3,
                              3,
                              true,
                              3,
                              30,
                              true,
                              "#version 330 core",
                              "WSL2 (OpenGL 3.3 core, GLSL 330)"};
#endif
    default:
        // Fallback to most conservative settings
        return PlatformConfig{Platform::RASPBERRY_PI_5,
                              3,
                              0,
                              false,
                              1,
                              30,
                              false,
                              "#version 130",
                              "Unknown/Default (OpenGL 3.0 compat, GLSL 130)"};
    }
}

} // namespace adiviewer

#endif // ADIPLATFORMCONFIG_H
