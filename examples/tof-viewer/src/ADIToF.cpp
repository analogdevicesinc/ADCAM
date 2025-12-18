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
