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

#include "ADIOpenFile.h"

const char filter[] = "Bin Files (*.bin)\0*.bin*\0All Files (*.*)\0*.*\0";
std::string customFilter(filter, sizeof(filter));
std::vector<std::string> customFilters = {"bin"};

// Include necessary headers for path resolution
#ifdef _WIN32
#include <codecvt>
#include <windows.h>
#include <Commdlg.h>
#define PATH_MAX MAX_PATH
#elif defined(__APPLE__) && defined(__MACH__)
#include <mach-o/dyld.h>
#include <sys/syslimits.h>
#include <climits>
#elif defined(linux) || defined(__linux) || defined(__linux__)
#include <climits>
#include <unistd.h>
#endif

// Shared static variable for dialog path tracking
static std::string& getLastUsedPathRef() {
    static std::string lastUsedPath;
    return lastUsedPath;
}

// Helper function to get and remember the dialog starting path
static std::string getDialogStartPath() {
    static bool isFirstCall = true;
    std::string& lastUsedPath = getLastUsedPathRef();
    
    if (isFirstCall) {
        isFirstCall = false;
        // Get executable directory on first call
#ifdef _WIN32
        char exePath[PATH_MAX];
        if (GetModuleFileNameA(NULL, exePath, PATH_MAX)) {
            std::string fullPath(exePath);
            size_t pos = fullPath.find_last_of("\\\\");
            if (pos != std::string::npos) {
                lastUsedPath = fullPath.substr(0, pos);
            }
        }
#elif defined(__APPLE__) && defined(__MACH__)
        char exePath[PATH_MAX];
        uint32_t size = sizeof(exePath);
        if (_NSGetExecutablePath(exePath, &size) == 0) {
            char realPath[PATH_MAX];
            if (realpath(exePath, realPath)) {
                std::string fullPath(realPath);
                size_t pos = fullPath.find_last_of("/");
                if (pos != std::string::npos) {
                    lastUsedPath = fullPath.substr(0, pos);
                }
            }
        }
#elif defined(linux) || defined(__linux) || defined(__linux__)
        char exePath[PATH_MAX];
        ssize_t len = readlink("/proc/self/exe", exePath, sizeof(exePath) - 1);
        if (len != -1) {
            exePath[len] = '\0';
            std::string fullPath(exePath);
            size_t pos = fullPath.find_last_of("/");
            if (pos != std::string::npos) {
                lastUsedPath = fullPath.substr(0, pos);
            }
        }
#endif
    }
    
    return lastUsedPath;
}

// Helper function to update the last used path from a file path
static void updateLastUsedPath(const std::string& filePath) {
    std::string& lastUsedPath = getLastUsedPathRef();
    if (!filePath.empty()) {
#ifdef _WIN32
        size_t pos = filePath.find_last_of("\\\\");
#else
        size_t pos = filePath.find_last_of("/");
#endif
        if (pos != std::string::npos) {
            lastUsedPath = filePath.substr(0, pos);
        }
    }
}

#ifdef _WIN32

using namespace std;

/**
* @brief		Returns an empty string if cancelled.
*				Opens a dialog box to fetch a file with
*				a custom file extension
* @param filter	Is assigned a customized filter per
*				camera requirements
* @param owner	NULL
* @return		Selected file name with its extension
*/
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

std::string openADIFileName(const char *filter, void *owner, int &FilterIndex) {
    // Initialize variables
    OPENFILENAME ofn = {0};
    char fileName[MAX_PATH] = "";
    std::string startPath = getDialogStartPath();
    
    ofn.lStructSize = sizeof(ofn);
    ofn.hwndOwner = reinterpret_cast<HWND>(owner);
    ofn.lpstrFilter = filter; // Filter string
    ofn.lpstrFile = fileName; // File name buffer
    ofn.nMaxFile = MAX_PATH;
    ofn.Flags = OFN_EXPLORER | OFN_FILEMUSTEXIST | OFN_HIDEREADONLY;
    ofn.lpstrDefExt = "json"; // Default extension
    
    // Set initial directory if we have one
    if (!startPath.empty()) {
        ofn.lpstrInitialDir = startPath.c_str();
    }

    // Display the dialog and get the result
    if (GetOpenFileName(&ofn)) {
        FilterIndex = ofn.nFilterIndex; // Get the selected filter index
        std::string result(fileName);
        updateLastUsedPath(result);
        return result;   // Return the selected file path
    }

    // If the user cancels or an error occurs
    DWORD error = CommDlgExtendedError();
    if (error != 0) {
        std::cerr << "GetOpenFileName failed with error: " << error
                  << std::endl;
    }

    FilterIndex = 0; // Reset filter index
    return "";       // Return empty string if canceled or failed
}

/**
* @brief Opens a dialog box to save a file
* @param hwndOwner		Current handle
* @param filename		Saved name from user
* @param FilterIndex	Index of chosen filter
* @return				Saved name if successful,
*						empty string otherwise
*/
std::string getADIFileName(void *hwndOwner, const char *customFilter,
                           char *filename, int &FilterIndex) {
    // Initialize the OPENFILENAME structure
    OPENFILENAME ofn = {0};
    ofn.lStructSize = sizeof(ofn);
    ofn.hwndOwner = reinterpret_cast<HWND>(hwndOwner);
    ofn.hInstance = GetModuleHandle(0);
    ofn.nMaxFile = MAX_PATH;
    ofn.lpstrFile = filename;
    ofn.lpstrFile[0] = '\0';        // Ensure the filename buffer is empty
    ofn.lpstrFilter = customFilter; // Use the passed filter
    ofn.lpstrDefExt = "json"; // Default file extension if none is provided
    ofn.Flags = OFN_EXPLORER | OFN_OVERWRITEPROMPT;
    ofn.nFilterIndex = 1; // Default to the first filter

    // Show the Save File dialog
    if (GetSaveFileName(&ofn)) {
        // Get the selected filter index
        FilterIndex = static_cast<int>(ofn.nFilterIndex);

        bool fileExists = false;
        std::ifstream tmpFile(filename);
        fileExists = tmpFile.good();
        tmpFile.close();

        if (fileExists) {
            if (deleteFile(std::string(filename))) {
                return std::string(filename);
            }
        } else {
            return std::string(filename);
        }
    }

    // If the user cancels or an error occurs
    DWORD error = CommDlgExtendedError();
    if (error != 0) {
        std::cerr << "GetSaveFileName failed with error: " << error
                  << std::endl;
    }

    FilterIndex = 0;
    return ""; // Return an empty string to indicate failure
}

/**
* @brief					Finds a set of files with specified file extension
* @param filePath			User selected file path
* @param extension			File extension to be found
* @param returnFullPath     If true: returnFileName is returned with both
							path and file name, otherwise just the file name
* @return returnFileName	Set of files that match the chosen extension
*/
void getFilesList(string filePath, string extension,
                  vector<string> &returnFileName, bool returnFullPath) {
    WIN32_FIND_DATA fileInfo;
    HANDLE hFind;
    //if "filePath" does not end with "\\" then we need to add it
    if (filePath.back() != ('\\')) {
        filePath += "\\";
    }
    string fullPath = filePath + extension;
    hFind = FindFirstFile(fullPath.c_str(), &fileInfo);
    if (hFind != INVALID_HANDLE_VALUE) {
        if (returnFullPath) {
            returnFileName.push_back(filePath + fileInfo.cFileName);
        } else {
            returnFileName.push_back(fileInfo.cFileName);
        }
        while (FindNextFile(hFind, &fileInfo) != 0) {
            if (returnFullPath) {
                returnFileName.push_back(filePath + fileInfo.cFileName);
            } else {
                returnFileName.push_back(fileInfo.cFileName);
            }
        }
    }
}

bool deleteFile(const std::string &path) {
    if (SetFileAttributes(path.c_str(), FILE_ATTRIBUTE_NORMAL)) {
        if (DeleteFile(path.c_str())) {
            return true;
        }
    }
    return false;
}

#elif defined(__APPLE__) && defined(__MACH__)

#include "filesystem.hpp"
#include <cstdio>
#include <dirent.h>

namespace fs = ghc::filesystem;
#define MAX_PATH PATH_MAX

extern std::vector<std::string>
openFileDialog(char const *const aTitle, char const *const aDefaultPathAndFile,
               const std::vector<std::string> &filters);

extern std::vector<std::string>
saveFileDialog(char const *const aTitle, char const *const aDefaultPathAndFile,
               const std::vector<std::string> &filters);

/**
* @brief Opens a dialog box to save a file
* @param hwndOwner		urrent handle
* @param filename		Saved name from user
* @param FilterIndex	Index of chosen filter
* @return				Saved name if successful,
*						empty string otherwise
*/
std::string getADIFileName(void *hwndOwner, const char *customFilter,
                           char *filename, int &FilterIndex) {
    std::vector<std::string> filters;
    std::copy(std::begin(customFilters), std::end(customFilters),
              std::back_inserter(filters));
    std::vector<std::string> files =
        saveFileDialog("Select filename", filename, filters);

    if (files.size() == 0) {
        return "";
    }

    for (int ix = 0; ix < filters.size(); ix++) {
        if (files[0].substr(files[0].find_last_of(".") + 1) == filters[ix]) {
            FilterIndex = ix + 1;
            break;
        }
    }
    FilterIndex = 0;
    return files[0].substr(0,
                           files[0].find_last_of(".")); //strip file extension
}

std::string openADIFileName(const char *filter, void *owner, int &FilterIndex) {

    std::vector<std::string> filters;
    std::copy(std::begin(customFilters), std::end(customFilters),
              std::back_inserter(filters));
    
    // Use remembered path instead of current working directory
    std::string startPath = getDialogStartPath();
    if (startPath.empty()) {
        startPath = fs::current_path().string();
    }
    
    std::vector<std::string> files =
        openFileDialog("Select filename", startPath.c_str(), filters);

    if (files.size() == 0) {
        return "";
    }

    for (int ix = 0; ix < filters.size(); ix++) {
        if (files[0].substr(files[0].find_last_of(".") + 1) == filters[ix]) {
            FilterIndex = ix + 1;
            break;
        }
    }
    FilterIndex = 0;
    updateLastUsedPath(files[0]);
    return files[0].substr(0,
                           files[0].find_last_of(".")); //strip file extension

    return files[0];
}

void getFilesList(std::string filePath, std::string extension,
                  std::vector<std::string> &returnFileName,
                  bool returnFullPath) {

    returnFileName.clear();

    DIR *dir = opendir(filePath.c_str());
    if (NULL == dir) {
        return;
    }

    //strip off '*' used in WIN32 APIs
    extension = extension.substr(1);

    struct dirent *entry = readdir(dir);
    while (NULL != entry) {

        std::string file(entry->d_name);
        std::size_t pos = file.find_last_of('.');
        if (pos != std::string::npos && extension == file.substr(pos)) {
            if (returnFullPath) {
                returnFileName.push_back(filePath + "/" + file);
            } else {
                returnFileName.push_back(file);
            }
        }

        entry = readdir(dir);
    }

    closedir(dir);
}

#elif defined(linux) || defined(__linux) || defined(__linux__)

#include "ADIOpenFile.h"
#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <dirent.h> // For directory traversal
#include <fstream>
#include <iostream>
#include <sstream>
#include <sys/stat.h> // For checking file status
#include <unistd.h>   // For unlink
#include <vector>

// Assuming customFilters and customFilter are defined somewhere else in your project.
extern std::string customFilter;
extern std::vector<std::string> customFilters;

// Function to run the Zenity command
std::string runZenityCommand(const std::string &command) {
    FILE *f = popen(command.c_str(), "r");
    if (!f) {
        perror("popen failed");
        return "";
    }

    char filename[FILENAME_MAX];
    if (!std::fgets(filename, FILENAME_MAX, f)) {
        pclose(f);
        perror("fgets failed");
        return "";
    }

    int ret = pclose(f);
    if (ret < 0) {
        perror("pclose failed");
    }

    // Remove newline character added by fgets
    std::string result(filename);
    result.erase(std::remove(result.begin(), result.end(), '\n'), result.end());
    return (ret == 0) ? result : "";
}

// Function to get the filename using Zenity with a custom extension filter
std::string getADIFileName(void *hwndOwner, const char *customFilter,
                           char *filename, int &FilterIndex) {
    FilterIndex = 0;
    const char zenityP[] = "/usr/bin/zenity";

    // Calculate the total length of customFilter manually by finding the end of the sequence
    size_t filterLength = 0;
    while (customFilter[filterLength] != '\0' ||
           customFilter[filterLength + 1] != '\0') {
        filterLength++;
    }
    filterLength++; // Account for the last null terminator

    // Convert customFilter to std::string including null terminators
    std::string customFilterStr(customFilter, filterLength);

    // Parse customFilter to extract the descriptions and extensions
    std::vector<std::string> filters;
    size_t start = 0;
    while (start < customFilterStr.size()) {
        size_t end = customFilterStr.find('\0', start);
        if (end == std::string::npos) {
            break; // End of string reached
        }

        std::string token = customFilterStr.substr(start, end - start);
        if (!token.empty()) {
            filters.push_back(token);
            //std::cout << "Parsed Token: " << token << std::endl;  // Debug output
        }
        start = end + 1; // Move to the next segment after the null character
    }

    // Construct the Zenity command
    std::string command =
        std::string(zenityP) +
        " --file-selection --save --modal --title=\"Select filename\"";

    // Add the file filters to the command
    for (size_t i = 0; i < filters.size(); i += 2) {
        if (i + 1 < filters.size()) {
            // Add filter with the description and extension pattern
            command += " --file-filter=\"" + filters[i] + " | " +
                       filters[i + 1] + "\"";
        }
    }

    // Print the command for debugging purposes
    std::cout << "Zenity Command: " << command << std::endl;

    // Run the Zenity command
    std::string result = runZenityCommand(command);
    if (result.empty()) {
        filename[0] = '\0'; // Clear filename on cancellation
        return "";
    }

    // Check if the file has an extension, and if not, add a default one
    size_t extensionPos = result.find_last_of('.');
    if (extensionPos == std::string::npos ||
        extensionPos == result.size() - 1) {
        // No extension found, add the default extension
        if (!filters.empty() && filters.size() >= 2) {
            std::string defaultExtension = filters[1];
            size_t wildcardPos = defaultExtension.find('*');
            if (wildcardPos != std::string::npos) {
                defaultExtension = defaultExtension.substr(
                    wildcardPos + 1); // Extract the extension (e.g., ".bin")
                result += defaultExtension;
            }
        }
    }

    // Copy the selected filename to the provided buffer
    strncpy(filename, result.c_str(), FILENAME_MAX - 1);
    filename[FILENAME_MAX - 1] = '\0'; // Ensure null-termination

    // Update FilterIndex to reflect which filter was used
    for (size_t ix = 0; ix < filters.size(); ix += 2) {
        std::string filterExt =
            filters[ix + 1].substr(filters[ix + 1].find('.') + 1);
        if (result.find(filterExt) != std::string::npos) {
            FilterIndex = static_cast<int>(ix / 2) + 1;
            break;
        }
    }

    bool fileExists = false;
    std::ifstream tmpFile(filename);
    fileExists = tmpFile.good();
    tmpFile.close();

    if (fileExists) {
        if (deleteFile(std::string(filename))) {
            return std::string(filename);
        }
    } else {
        return std::string(filename);
    }

    return result;
}

std::string openADIFileName(const char *filter, void *owner, int &FilterIndex) {
    FilterIndex = 0;
    const char zenityP[] = "/usr/bin/zenity";
    
    // Get the starting path (executable directory on first call, last used path subsequently)
    std::string startPath = getDialogStartPath();
    
    std::string command =
        std::string(zenityP) +
        " --file-selection --modal --title=\"Select filename\"";
    
    // Add filename hint with starting directory if available
    if (!startPath.empty()) {
        command += " --filename=\"" + startPath + "/\"";
    }

    std::string filename = runZenityCommand(command);
    if (filename.empty()) {
        return "";
    }

    // Update the last used path for next time
    updateLastUsedPath(filename);

    // Assuming custom filter handling if necessary
    std::vector<std::string> filters(customFilters);
    filters.push_back(filter);
    for (size_t ix = 0; ix < filters.size(); ++ix) {
        std::string filterWithDot = "." + filters[ix];
        if (filename.find(filterWithDot) != std::string::npos) {
            FilterIndex = static_cast<int>(ix + 1);
            break;
        }
    }

    return filename;
}

void getFilesList(std::string filePath, std::string extension,
                  std::vector<std::string> &returnFileName,
                  bool returnFullPath) {
    returnFileName.clear();

    DIR *dir = opendir(filePath.c_str());
    if (!dir) {
        std::cerr << "Failed to open directory: " << filePath << std::endl;
        return;
    }

    // Remove '*' from extension, if present
    if (!extension.empty() && extension[0] == '*') {
        extension = extension.substr(1);
    }

    struct dirent *entry;
    while ((entry = readdir(dir)) != nullptr) {
        std::string file(entry->d_name);

        // Skip "." and ".." entries
        if (file == "." || file == "..") {
            continue;
        }

        // Get file extension
        size_t pos = file.find_last_of('.');
        if (pos != std::string::npos) {
            std::string fileExtension = file.substr(pos);

            // Check if the extension matches
            if (fileExtension == extension) {
                if (returnFullPath) {
                    returnFileName.push_back(filePath + "/" + file);
                } else {
                    returnFileName.push_back(file);
                }
            }
        }
    }

    closedir(dir);
}

bool deleteFile(const std::string &path) {
    if (unlink(path.c_str()) == 0) {
        return true; // File successfully deleted
    } else {
        std::cerr << "Error deleting file on Linux/Unix: " << strerror(errno)
                  << "\n";
        return false;
    }
}

#endif