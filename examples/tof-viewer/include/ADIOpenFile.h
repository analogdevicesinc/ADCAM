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
#ifndef ADI_OPEN_FILE
#define ADI_OPEN_FILE

#include <iostream>
#include <string>
#include <vector>

extern std::string customFilter;
extern std::vector<std::string> customFilters;

/**
* @brief Returns an empty string if cancelled.
*                      Opens a dialog box to fetch a file with a custom file extension
* @param filter        Is assigned a customized filter per camera requirements
* @param owner         Platform specific, typically NULL
* @param FilterIndex   Index of file filter
* @return              Selected file name with its extension
*/
std::string openADIFileName(const char *filter, void *owner, int &FilterIndex);

/**
* @brief Opens a dialog box to save a file
* @param hwndOwner     Platform specific, current handle or NULL
* @param filename      Saved name from user
* @param FilterIndex   Index of chosen filter
* @return              Saved name if successful, empty string otherwise
*/
std::string getADIFileName(void *hwndOwner, const char *customFilter,
                           char *filename, int &FilterIndex);

/**
* @brief Finds a set of files with specified file extension
* @param filePath       User selected file path
* @param extension      File extension to be found
* @param returnFileName Set of files that match the chosen extension
* @param returnFullPath If true: returnFileName is returned with both
                        path and file name, otherwise just the file name
*/
void getFilesList(std::string filePath, std::string extension,
                  std::vector<std::string> &returnFileName,
                  bool returnFullPath);

/**
* @brief Finds a set of files with specified file extension
* @param path           Path to file to delete
* @return               True if the file is deleted
*/
bool deleteFile(const std::string &path);

#endif //ADI_OPEN_FILE
