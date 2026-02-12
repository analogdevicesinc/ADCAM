#include "test_utils.h"
#include <iostream>
#include <sstream>
#include <fstream>
#include <chrono>
#include <iomanip>
#include <cstring>
#include <libgen.h>
#include <unistd.h>

namespace test_utils {

// Initialize global variables
std::string g_device_address = "";
std::string g_config_path = "";
std::string g_frame_mode = "0";

std::string getUTCTimestamp() {
    auto now = std::chrono::system_clock::now();
    std::time_t now_c = std::chrono::system_clock::to_time_t(now);
    std::tm now_tm;
    gmtime_r(&now_c, &now_tm);
    
    std::ostringstream oss;
    oss << std::put_time(&now_tm, "%Y%m%d_%H%M%S");
    return oss.str();
}

bool compareTextFiles(const std::string& file1, const std::string& file2) {
    std::ifstream f1(file1);
    std::ifstream f2(file2);
    
    if (!f1.is_open() || !f2.is_open()) {
        return false;
    }
    
    std::string line1, line2;
    while (std::getline(f1, line1) && std::getline(f2, line2)) {
        if (line1 != line2) {
            return false;
        }
    }
    
    return f1.eof() && f2.eof();
}

// TestRunner implementation
TestRunner::TestRunner(const std::string& programName)
    : programName_(programName), execName_(programName), helpRequested_(false),
      strictArgs_(true), preTestValidator_(nullptr), newArgc_(0),
      executablePath_(programName) {
    
    // Extract executable directory
    char* path_copy = strdup(programName.c_str());
    executablePath_ = std::string(dirname(path_copy));
    free(path_copy);
    
    // Extract executable name
    char* name_copy = strdup(programName.c_str());
    execName_ = std::string(basename(name_copy));
    free(name_copy);
    
    timestamp_ = getUTCTimestamp();
    
    // Automatically add common arguments
    addArgument(CustomArg("--device=", &g_device_address,
                          "Specify the device address/IP"));
    addArgument(CustomArg("--config=", &g_config_path,
                          "Specify the configuration file path"));
    addArgument(CustomArg("--mode=", &g_frame_mode,
                          "Specify the frame mode (0-6)"));
}

void TestRunner::addArgument(const CustomArg& arg) {
    customArgs_.push_back(arg);
}

void TestRunner::setPreTestValidator(std::function<bool()> validator) {
    preTestValidator_ = validator;
}

void TestRunner::setStrictArguments(bool strict) {
    strictArgs_ = strict;
}

int TestRunner::initialize(int& argc, char** argv) {
    // Parse custom arguments
    newArgv_.clear();
    newArgv_.push_back(argv[0]);
    
    std::vector<std::string> unknownArgs;
    
    for (int i = 1; i < argc; ++i) {
        std::string arg(argv[i]);
        bool handled = false;
        
        // Check for help
        if (arg == "-h" || arg == "--help") {
            helpRequested_ = true;
            handled = true;
        }
        
        // Check custom arguments
        for (const auto& customArg : customArgs_) {
            if (arg.find(customArg.prefix) == 0) {
                std::string value = arg.substr(customArg.prefix.length());
                
                if (customArg.type == CustomArg::STRING) {
                    *static_cast<std::string*>(customArg.target) = value;
                } else if (customArg.type == CustomArg::INT) {
                    *static_cast<int*>(customArg.target) = std::stoi(value);
                } else if (customArg.type == CustomArg::UINT16) {
                    *static_cast<uint16_t*>(customArg.target) = std::stoul(value);
                } else if (customArg.type == CustomArg::BOOL) {
                    *static_cast<bool*>(customArg.target) = true;
                }
                
                handled = true;
                break;
            }
        }
        
        // If not handled, pass to GoogleTest or track as unknown
        if (!handled) {
            if (arg.find("--gtest") == 0) {
                newArgv_.push_back(argv[i]);
            } else {
                unknownArgs.push_back(arg);
            }
        }
    }
    
    // Show help if requested
    if (helpRequested_) {
        std::cout << "Usage: " << execName_ << " [OPTIONS]" << std::endl;
        std::cout << std::endl;
        std::cout << "Custom Options:" << std::endl;
        for (const auto& arg : customArgs_) {
            std::cout << "  " << arg.prefix << "<value>  " << arg.description << std::endl;
        }
        std::cout << std::endl;
        std::cout << "GoogleTest Options:" << std::endl;
        std::cout << "  --gtest_filter=<pattern>  Run only tests matching pattern" << std::endl;
        std::cout << "  --gtest_repeat=N          Repeat tests N times" << std::endl;
        std::cout << "  --gtest_shuffle           Randomize test order" << std::endl;
        std::cout << "  --gtest_output=<format>   Output format (json:filename)" << std::endl;
        std::cout << std::endl;
        return 0;
    }
    
    // Handle unknown arguments
    if (!unknownArgs.empty() && strictArgs_) {
        std::cerr << "Error: Unknown arguments:" << std::endl;
        for (const auto& arg : unknownArgs) {
            std::cerr << "  " << arg << std::endl;
        }
        std::cerr << "Use -h or --help for usage information" << std::endl;
        return 1;
    }
    
    // Initialize GoogleTest
    newArgc_ = static_cast<int>(newArgv_.size());
    ::testing::InitGoogleTest(&newArgc_, newArgv_.data());
    
    // Run pre-test validator if set
    if (preTestValidator_ && !preTestValidator_()) {
        std::cerr << "Pre-test validation failed" << std::endl;
        return 1;
    }
    
    return -1; // Continue to runTests()
}

int TestRunner::runTests() {
    return RUN_ALL_TESTS();
}

} // namespace test_utils
