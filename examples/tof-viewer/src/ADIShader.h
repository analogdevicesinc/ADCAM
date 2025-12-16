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
#ifndef ADISHADER_H
#define ADISHADER_H

// clang-format off
// IMPORTANT: glad/gl.h must be included first to avoid conflicts with ImGui OpenGL loader
#include "glad/gl.h"
// clang-format on

#include "backends/imgui_impl_glfw.h"
#include "backends/imgui_impl_opengl3.h"
#include <GLFW/glfw3.h>
#include <fstream>
#include <iostream>
#include <list>
#include <sstream>
#include <string>

namespace adiviewer {

/**
 * @class ADIShader
 * @brief OpenGL shader management class for vertex and fragment shaders
 * 
 * Handles compilation, linking, and management of OpenGL shaders.
 * Supports both vertex and fragment shaders with error checking.
 */
class ADIShader {
  public:
    /**
		* @brief Constructor
		*        Generates a shader type and compiles it
		*/
    ADIShader(GLenum shaderType, const GLchar *source) {
        ID = glCreateShader(shaderType);
        glShaderSource(ID, 1, &source, nullptr);
        glCompileShader(ID);

        GLint success = GL_FALSE;
        char infoLog[512];
        glGetShaderiv(ID, GL_COMPILE_STATUS, &success);
        if (!success) {
            glGetShaderInfoLog(ID, 512, nullptr, infoLog);
            std::stringstream errorBuilder;
            errorBuilder << "Shader compilation error: " << std::endl
                         << infoLog;
            throw std::logic_error(errorBuilder.str().c_str());
        }
    }

    /**
		* @brief Activate Shader Program
		*/
    ADIShader(ADIShader &&other) : ID(other.ID) { other.ID = 0; }

    ADIShader &operator=(ADIShader &&other) {
        if (this != &other) {
            ID = other.ID;
            other.ID = 0;
        }
        return *this;
    }

    GLuint Id() { return ID; }

    ~ADIShader() {
        if (ID != 0) {
            glDeleteShader(ID);
        }
    }

    ADIShader(const ADIShader &) = delete;
    ADIShader &operator=(const ADIShader &) = delete;

    /**
		* @brief Activate Shader Program
		*/
    void useProgram() const { glUseProgram(ID); }

  private:
    GLuint ID = 0;
};

/**
 * @class Program
 * @brief OpenGL shader program management class
 * 
 * Links vertex and fragment shaders into a complete shader program.
 * Provides methods for activation and uniform variable access.
 */
class Program {
  public:
    Program() {}

    void AttachShader(ADIShader &&newShader) {
        glAttachShader(ID, newShader.Id());
        shaders.emplace_back(std::move(newShader));
    }

    void RemoveShaders() { shaders.clear(); }

    void CreateProgram() { ID = glCreateProgram(); }

    void Link() {
        glLinkProgram(ID);
        GLint success = GL_FALSE;
        char infoLog[512];
        std::string read = "";
        glGetProgramiv(ID, GL_LINK_STATUS, &success);
        if (!success) {
            glGetProgramInfoLog(ID, 512, nullptr, infoLog);
            std::stringstream errorBuilder;
            errorBuilder << "Shader program linking error: " << std::endl
                         << infoLog;
            read = infoLog;
            throw std::logic_error(errorBuilder.str().c_str());
        }
    }

    GLint GetUniformLocation(const GLchar *name) {
        return glGetUniformLocation(ID, name);
    }

    GLuint Id() { return ID; }

    ~Program() {
        // Reset the active shader if we're about to delete it
        //
        if (ID != 0) {
            GLint currentProgramId;
            glGetIntegerv(GL_CURRENT_PROGRAM, &currentProgramId);
            if (ID == static_cast<GLuint>(currentProgramId)) {
                glUseProgram(0);
            }

            glDeleteProgram(ID);
        }
    }

    Program(const Program &) = delete;
    Program &operator=(const Program &) = delete;

  private:
    GLuint ID = 0;
    std::list<ADIShader> shaders;
};

} // namespace adiviewer

#endif
