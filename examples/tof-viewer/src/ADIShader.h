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
