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

#include "ADIImGUIExtensions.h"

// System headers
//
#include <cmath>
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

void ADISpinner(const char *label, float radius, int thickness, ImU32 color) {
    ImGuiWindow *window = ImGui::GetCurrentWindow();
    if (window->SkipItems) {
        return;
    }

    if (label != nullptr && label[0] != '\0') {
        ImGui::PushID(label);
    }

    ImGuiContext &g = *ImGui::GetCurrentContext();
    ImVec2 pos = ImGui::GetCursorScreenPos();
    float t = static_cast<float>(g.Time);
    int num_segments = 30;
    float angle_min = IM_PI * 2.0f * (t * 0.8f);
    float angle_max = IM_PI * 2.0f * ((t * 0.8f) + 1.0f);

    ImDrawList *draw_list = ImGui::GetWindowDrawList();
    draw_list->PathClear();
    for (int i = 0; i < num_segments; i++) {
        float a = angle_min +
                  (static_cast<float>(i) / static_cast<float>(num_segments)) *
                      (angle_max - angle_min);
        draw_list->PathLineTo(ImVec2(pos.x + radius + cosf(a) * radius,
                                     pos.y + radius + sinf(a) * radius));
    }
    draw_list->PathStroke(color, 0, thickness);
    ImGui::Dummy(ImVec2((radius + thickness) * 2, (radius + thickness) * 2));

    if (label != nullptr && label[0] != '\0') {
        ImGui::PopID();
    }
}

} // namespace ImGuiExtensions
} // namespace adiMainWindow