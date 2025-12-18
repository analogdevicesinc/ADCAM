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
