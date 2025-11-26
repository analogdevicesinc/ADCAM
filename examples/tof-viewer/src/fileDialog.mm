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
#import <Cocoa/Cocoa.h>
#import <Foundation/Foundation.h>
#include <string>
#include <vector>

std::vector<std::string>
openFileDialog(char const *const aTitle, char const *const aDefaultPathAndFile,
               const std::vector<std::string> &filters) {

    int i;
    std::vector<std::string> fileList;
    NSOpenPanel *openDlg = [NSOpenPanel openPanel];
    [openDlg setLevel:CGShieldingWindowLevel()];

    // Set array of file types
    NSMutableArray *fileTypesArray = [NSMutableArray array];
    for (i = 0; i < filters.size(); i++) {
        NSString *filt = [NSString stringWithUTF8String:filters[i].c_str()];
        [fileTypesArray addObject:filt];
    }

    // Enable options in the dialog.
    [openDlg setCanChooseFiles:YES];
    [openDlg setCanChooseDirectories:NO];
    [openDlg setAllowedFileTypes:fileTypesArray];
    [openDlg setAllowsMultipleSelection:FALSE];
    [openDlg
        setDirectoryURL:[NSURL
                            URLWithString:[NSString stringWithUTF8String:
                                                        aDefaultPathAndFile]]];

    // Display the dialog box. If the OK pressed return 1 filname
    if ([openDlg runModal] == NSModalResponseOK) {
        NSArray *files = [openDlg URLs];
        for (i = 0; i < [files count]; i++) {
            fileList.push_back(
                std::string([[[files objectAtIndex:i] path] UTF8String]));
        }
    }
    return fileList;
}

std::vector<std::string>
saveFileDialog(char const *const aTitle, char const *const aDefaultPathAndFile,
               const std::vector<std::string> &filters) {

    int i;
    std::vector<std::string> fileList;
    // Create a File Save Dialog class.
    NSSavePanel *saveDlg = [NSSavePanel savePanel];
    [saveDlg setLevel:CGShieldingWindowLevel()];

    NSMutableArray *fileTypesArray = [NSMutableArray array];
    for (i = 0; i < filters.size(); i++) {
        NSString *filt = [NSString stringWithUTF8String:filters[i].c_str()];
        [fileTypesArray addObject:filt];
    }

    // Enable options in the dialog.
    [saveDlg setAllowedFileTypes:fileTypesArray];
    [saveDlg
        setDirectoryURL:[NSURL
                            URLWithString:[NSString stringWithUTF8String:
                                                        aDefaultPathAndFile]]];

    // Display the dialog box. Return filename if OK pressed
    if ([saveDlg runModal] == NSModalResponseOK) {
        NSURL *file = [saveDlg URL];
        if (file) {
            fileList.push_back(std::string([[file path] UTF8String]));
        }
    }
    return fileList;
}
