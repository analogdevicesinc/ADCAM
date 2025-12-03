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

#include "ADIImGUIExtensions.h"

// System headers
//
#include <functional>
#include <sstream>

#include "imgui.h"

namespace {
std::string ConvertToVerticalText(const char *str) {
    std::stringstream ss;
    bool first = true;
    while (*str) {
        if (first) {
            first = false;
        } else {
            ss << "\n";
        }

        ss << *str;
        ++str;
    }
    return ss.str();
}
} // namespace

namespace adiMainWindow {
namespace ImGuiExtensions {

bool ADIButton(const char *label, const bool enabled) {
    return ADIButton(label, ImVec2(0, 0), enabled);
}

bool ADIButton(const char *label, const ImVec2 &size, bool enabled) {
    return ShowDisableableControl<bool>(
        [label, &size]() { return ImGui::Button(label, size); }, enabled);
}

bool ADICheckbox(const char *label, bool *checked, const bool enabled) {
    return ShowDisableableControl<bool>(
        [label, checked]() { return ImGui::Checkbox(label, checked); },
        enabled);
}

bool ADIRadioButton(const char *label, bool active, bool enabled) {
    return ShowDisableableControl<bool>(
        [label, active]() { return ImGui::RadioButton(label, active); },
        enabled);
}

bool ADIRadioButton(const char *label, int *v, int vButton, bool enabled) {
    return ShowDisableableControl<bool>(
        [label, v, vButton]() { return ImGui::RadioButton(label, v, vButton); },
        enabled);
}

bool ADIInputScalar(const char *label, ImGuiDataType dataType, void *dataPtr,
                    const void *step, const void *stepFast, const char *format,
                    bool enabled) {
    return ShowDisableableControl<bool>(
        [&]() {
            return ImGui::InputScalar(label, dataType, dataPtr, step, stepFast,
                                      format);
        },
        enabled);
}

void ADIVText(const char *s) {
    const std::string vLabel = ConvertToVerticalText(s);
    ImGui::Text("%s", vLabel.c_str());
}

void ADIShowTooltip(const char *msg, bool show) {
    if (show && ImGui::IsItemHovered()) {
        ImGui::BeginTooltip();
        ImGui::PushTextWrapPos(ImGui::GetFontSize() * 35.0f);
        ImGui::TextUnformatted(msg);
        ImGui::PopTextWrapPos();
        ImGui::EndTooltip();
    }
}

} // namespace ImGuiExtensions
} // namespace adiMainWindow