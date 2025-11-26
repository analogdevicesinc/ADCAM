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
#ifndef ADIIMGUIEXTENSIONS_H
#define ADIIMGUIEXTENSIONS_H
#include "backends/imgui_impl_glfw.h"
#include "backends/imgui_impl_opengl3.h"
#include "imgui.h"
#include <imgui_internal.h>

// System headers
//
#include <algorithm>
#include <functional>
#include <string>
#include <utility>
#include <vector>

namespace adiMainWindow {
namespace ImGuiExtensions {
enum class ButtonColor { Red, Yellow, Green };

// Sets all future buttons to color until cleared or destroyed.
// Optionally set enabled=false if you don't want to change color under some circumstances
//
class ButtonColorChanger {
  public:
    ButtonColorChanger(ButtonColor color, bool enabled = true)
        : m_active(enabled) {
        if (!m_active) {
            return;
        }

        float hue = 0.0f;
        float sat = 0.6f;
        float val = 0.6f;
        switch (color) {
        case ButtonColor::Green:
            hue = 0.4f;
            break;
        case ButtonColor::Yellow:
            hue = 0.15f;
            break;
        case ButtonColor::Red:
            hue = 0.0f;
            break;
        }

        constexpr float hoveredSvColorOffset = 0.1f;
        constexpr float activeSvColorOffset = 0.2f;
        ImGui::PushStyleColor(ImGuiCol_Button,
                              ImVec4(ImColor::HSV(hue, sat, val)));
        ImGui::PushStyleColor(
            ImGuiCol_ButtonHovered,
            ImVec4(ImColor::HSV(hue, sat + hoveredSvColorOffset,
                                val + hoveredSvColorOffset)));

        ImGui::PushStyleColor(
            ImGuiCol_ButtonActive,
            ImVec4(ImColor::HSV(hue, sat + activeSvColorOffset,
                                val + activeSvColorOffset)));
    }

    /*
			hue has values from 0.0 - 1.0. Value of 0.0 is Red and 1.0 is
			*/
    ButtonColorChanger(float hue, bool enabled = true) : m_active(enabled) {
        if (!m_active) {
            return;
        }
        float sat = 0.6f;
        float val = 0.6f;
        constexpr float hoveredSvColorOffset = 0.1f;
        constexpr float activeSvColorOffset = 0.2f;
        ImGui::PushStyleColor(ImGuiCol_Button,
                              ImVec4(ImColor::HSV(hue, sat, val)));
        ImGui::PushStyleColor(
            ImGuiCol_ButtonHovered,
            ImVec4(ImColor::HSV(hue, sat + hoveredSvColorOffset,
                                val + hoveredSvColorOffset)));

        ImGui::PushStyleColor(
            ImGuiCol_ButtonActive,
            ImVec4(ImColor::HSV(hue, sat + activeSvColorOffset,
                                val + activeSvColorOffset)));
    }

    void Clear() {
        if (m_active) {
            m_active = false;
            ImGui::PopStyleColor(3);
        }
    }

    ~ButtonColorChanger() {
        if (m_active) {
            Clear();
        }
    }

  private:
    bool m_active;
};

enum class TextColor { Normal, Warning };

class TextColorChanger {
  public:
    TextColorChanger(TextColor color, bool enabled = true) : m_active(enabled) {
        if (!m_active) {
            return;
        }

        ImVec4 colorVec(1.0f, 1.0f, 1.0f, 1.0f);
        switch (color) {
        case TextColor::Normal:
            colorVec = ImVec4(1.0f, 1.0f, 1.0f, 1.0f);
            break;
        case TextColor::Warning:
            colorVec = ImVec4(1.0f, 1.0f, 0.0f, 1.0f);
            break;
        }

        ImGui::PushStyleColor(ImGuiCol_Text, colorVec);
    }

    void Clear() {
        if (m_active) {
            m_active = false;
            ImGui::PopStyleColor();
        }
    }

    ~TextColorChanger() {
        if (m_active) {
            Clear();
        }
    }

  private:
    bool m_active;
};

template <typename T>
T ShowDisableableControl(std::function<T()> showControlFunction,
                         const bool enabled) {
    if (!enabled) {
        ImGui::PushStyleVar(ImGuiStyleVar_Alpha,
                            ImGui::GetStyle().Alpha * 0.5f);
        ImGui::PushItemFlag(ImGuiItemFlags_Disabled, true);
    }

    const T result = showControlFunction();

    if (!enabled) {
        ImGui::PopItemFlag();
        ImGui::PopStyleVar();
    }

    return result;
}

// Shows a dear imgui combo box based on a list of value-presentation string pairs,
// updating currentValue if the value was modified
//
template <typename T>
bool ADIComboBox(const char *label, const char *noItemsText,
                 const ImGuiComboFlags flags,
                 const std::vector<std::pair<T, std::string>> &items,
                 T *currentValue, bool enabled = true) {
    return ShowDisableableControl<bool>(
        [label, noItemsText, flags, &items, currentValue]() {
            bool wasUpdated = false;

            auto selector = [currentValue](const std::pair<T, std::string> &a) {
                return a.first == *currentValue;
            };
            auto currentlySelected =
                std::find_if(items.begin(), items.end(), selector);

            const char *message = noItemsText;
            if (currentlySelected != items.end()) {
                message = currentlySelected->second.c_str();
            }

            if (ImGui::BeginCombo(label, message, flags)) {
                for (const auto &item : items) {
                    bool selected = item.first == *currentValue;
                    if (ImGui::Selectable(item.second.c_str(), selected)) {
                        *currentValue = item.first;
                        wasUpdated = true;
                    }
                    if (selected) {
                        ImGui::SetItemDefaultFocus();
                    }
                }

                ImGui::EndCombo();
            }

            return wasUpdated;
        },
        enabled);
}

// Behaves like a normal ImGui::Button, but with support for being disabled
//
bool ADIButton(const char *label, bool enabled = true);
bool ADIButton(const char *label, const ImVec2 &size, bool enabled = true);

// Behaves like a normal ImGui::Checkbox, but with support for being disabled
//
bool ADICheckbox(const char *label, bool *checked, bool enabled = true);

// Behaves like a normal ImGui::RadioButton, but with support for being disabled
//
bool ADIRadioButton(const char *label, bool active, bool enabled = true);
bool ADIRadioButton(const char *label, int *v, int vButton,
                    bool enabled = true);

// Behaves like a normal ImGui::InputScalar, but with support for being disabled
//
bool ADIInputScalar(const char *label, ImGuiDataType dataType, void *dataPtr,
                    const void *step, const void *stepFast, const char *format,
                    bool enabled = true);

// Behaves like a normal ImGui::SliderFloat, but with support for being disabled
//
bool ADISliderFloat(const char *label, float *value, float valueMin,
                    float valueMax, const char *format, float power,
                    bool enabled = true);

// Shows a vertical slider
//
bool ADIVSliderFloat(const char *name, ImVec2 size, float *value,
                     float minValue, float maxValue, const char *label);

// Shows vertical text
//
void ADIVText(const char *str);

// Shows a tooltip if the most recently-drawn control was hovered and show == true
//
void ADIShowTooltip(const char *msg, bool show = true);

} // namespace ImGuiExtensions

} // namespace adiMainWindow
#endif