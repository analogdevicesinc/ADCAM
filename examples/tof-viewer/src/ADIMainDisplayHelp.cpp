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
#include "ADIMainWindow.h"
#include "imgui_md.h"

#ifdef USE_GLOG
#include <glog/logging.h>
#else
#include <aditof/log.h>
#endif

using namespace adiMainWindow;

ImFont *g_font_regular;
ImFont *g_font_bold;
ImFont *g_font_bold_large;

struct help_markdown : public imgui_md {
    ImFont *get_font() const override {
        if (m_is_table_header) {
            return g_font_bold;
        }

        switch (m_hlevel) {
        case 0:
            return m_is_strong ? g_font_bold : g_font_regular;
        case 1:
            return g_font_bold_large;
        default:
            return g_font_bold;
        }
    };

    void open_url() const override {
        //platform dependent code
        //SDL_OpenURL(m_href.c_str());
    }

    bool get_image(image_info &nfo) const override {
        //use m_href to identify images
        //nfo.texture_id = g_texture1;
        nfo.size = {40, 20};
        nfo.uv0 = {0, 0};
        nfo.uv1 = {1, 1};
        nfo.col_tint = {1, 1, 1, 1};
        nfo.col_border = {0, 0, 0, 0};
        return true;
    }

    void html_div(const std::string &dclass, bool e) override {
        if (dclass == "red") {
            if (e) {
                m_table_border = false;
                ImGui::PushStyleColor(ImGuiCol_Text, IM_COL32(255, 0, 0, 255));
            } else {
                ImGui::PopStyleColor();
                m_table_border = true;
            }
        }
    }
};

void ADIMainWindow::DisplayHelp() {

    static std::string help_content = "";

    centreWindow(1000.0f * m_dpi_scale_factor, 1000.0f * m_dpi_scale_factor);

    if (ImGui::BeginPopupModal("Help Window", NULL,
                               ImGuiWindowFlags_AlwaysAutoResize)) {

        if (help_content.empty()) {
            std::ifstream help_file("tof-viewer.md");
            if (help_file) {
                LOG(INFO) << "Loading help content from file.";
                std::string line;
                while (std::getline(help_file, line)) {
                    help_content += line + '\n';
                }
            } else {
                LOG(ERROR) << "Failed to open help file.";
                help_content = "Help content could not be loaded.";
            }
        }

        if (ImGui::Button("Close"))
            ImGui::CloseCurrentPopup();

        static help_markdown s_printer;
        s_printer.print(help_content.c_str(),
                        help_content.c_str() + help_content.size());

        ImGui::EndPopup();
    }
}