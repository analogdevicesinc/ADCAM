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
#include <aditof/log.h>
#include <aditof/system.h>
#include <aditof/version-kit.h>
#include <aditof/version.h>
#include <algorithm>
#include <cctype>
#include <iostream>

#include "ADIMainWindow.h"

#if defined(__APPLE__) && defined(__MACH__)
class GOOGLE_GLOG_DLL_DECL glogLogSink : public google::LogSink {
  public:
    glogLogSink(AppLog *log) : applog(log) {}
    ~glogLogSink() = default;
    virtual void send(google::LogSeverity severity, const char *full_filename,
                      const char *base_filename, int line,
                      const struct ::tm *tm_time, const char *message,
                      size_t message_len) {
        if (applog) {
            std::string msg(message, message_len);
            msg += "\n";
            applog->AddLog(msg.c_str(), nullptr);
        }
    };

  private:
    AppLog *applog = nullptr;
};
#endif

void ProcessArgs(int argc, char **argv, ADIViewerArgs &args);

void ProcessArgs(int argc, char **argv, ADIViewerArgs &args) {
    // Skip argv[0], which is the path to the executable
    //

    for (int i = 1; i < argc; i++) {
        // Force to uppercase
        //
        std::string arg = argv[i];
        std::transform(arg.begin(), arg.end(), arg.begin(),
                       [](unsigned char c) {
                           return static_cast<unsigned char>(std::toupper(c));
                       });

        if (arg == std::string("--HIGHDPI")) {
            args.HighDpi = true;
        } else if (arg == std::string("--NORMALDPI")) {
            args.HighDpi = false;
        }
    }
}

int main(int argc, char **argv) {
    FLAGS_logtostderr = 1;

    auto view = std::make_shared<
        adiMainWindow::ADIMainWindow>(); //Create a new instance

#if defined(__APPLE__) && defined(__MACH__)
    //forward glog messages to GUI log windows
    glogLogSink *sink = new glogLogSink(view->getLog());
    google::AddLogSink(sink);
#endif

    LOG(INFO) << "ADCAM version: " << aditof::getKitVersion()
              << " | SDK version: " << aditof::getApiVersion()
              << " | branch: " << aditof::getBranchVersion()
              << " | commit: " << aditof::getCommitVersion();

    ADIViewerArgs args;

    ProcessArgs(argc, argv, args);
    if (view->StartImGUI(args)) {
        view->Render();
    }
    return 0;
}
