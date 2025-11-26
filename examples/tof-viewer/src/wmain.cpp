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
#ifdef _WIN32

#include <vector>
#include <windows.h>

int main(int argc, char **argv);

// Boilerplate required to make the app work as a Windows GUI application (rather than
// as a console application); just hands control off to the normal main function.
//
// Needs to be in a separate file because some stuff in windows.h doesn't play nice with
// some stuff in glfw.h.
//
int CALLBACK
WinMain(_In_ HINSTANCE hInstance, _In_ HINSTANCE hPrevInstance,
        _In_ LPSTR lpCmdLine, // NOLINT(readability-non-const-parameter)
        _In_ int nCmdShow) {
    UNREFERENCED_PARAMETER(hInstance);
    UNREFERENCED_PARAMETER(hPrevInstance);
    UNREFERENCED_PARAMETER(lpCmdLine);
    UNREFERENCED_PARAMETER(nCmdShow);

    int argc = __argc;
    std::vector<char *> argv;

    // Add argv[0], which is the path to the executable
    //
    argv.emplace_back(__argv[0]);

    // Windows-specific defaults that are overrideable by command-line
    //

    // Set default DPI
    //
    SetProcessDPIAware();
    constexpr uint16_t NormalDpi = 96;
    uint16_t systemDPI = GetDpiForSystem();
    if (systemDPI > NormalDpi) {
        argc++;
        argv.emplace_back(const_cast<char *>("--HIGHDPI"));
    } else {
        argc++;
        argv.emplace_back(const_cast<char *>("--NORMALDPI"));
    }

    main(argc, &argv[0]);
    fclose(stderr);
}
#endif
