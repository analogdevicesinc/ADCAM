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

#include "ADIMainWindow.h"

using namespace adiMainWindow;

void ADIMainWindow::ShowLogWindow(bool *p_open) {
    SetWindowSize(m_main_window_width / m_dpi_scale_factor, 235.0f);
    SetWindowPosition(0, m_main_window_height / m_dpi_scale_factor - 235.0f);
    ImGuiWindowFlags windowFlags =
        ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoCollapse;
    m_log.Draw("Camera: Log", p_open, windowFlags);

#ifdef __linux__
    fseek(m_file_input, ftell(m_file_input), SEEK_SET);
#endif

    while (fgets(m_buffer, 512, m_file_input)) {
        if (m_buffer != INIT_LOG_WARNING)
            m_log.AddLog(m_buffer, nullptr);
    }
}