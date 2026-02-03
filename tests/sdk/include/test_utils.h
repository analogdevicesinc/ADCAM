#ifndef TEST_UTILS_H
#define TEST_UTILS_H

#include <gtest/gtest.h>
#include <string>
#include <vector>
#include <map>
#include <functional>

namespace test_utils {

// ============================================================================
// GLOBAL CONFIGURATION
// ============================================================================

// Global test configuration variables (automatically available to all tests)
extern std::string g_device_address;
extern std::string g_config_path;
extern std::string g_frame_mode;

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

// Generate UTC timestamp in format: YYYYMMDD_HHMMSS
std::string getUTCTimestamp();

// File comparison utilities
bool compareTextFiles(const std::string& file1, 
                     const std::string& file2);

// ============================================================================
// CUSTOM ARGUMENT STRUCTURE
// ============================================================================

struct CustomArg {
    enum Type { STRING, INT, UINT16, BOOL };
    
    std::string prefix;           // e.g., "--device="
    Type type;
    void* target;                 // Pointer to variable to store value
    std::string description;      // Help text
    
    CustomArg(const std::string& p, std::string* t, const std::string& d)
        : prefix(p), type(STRING), target(t), description(d) {}
    
    CustomArg(const std::string& p, int* t, const std::string& d)
        : prefix(p), type(INT), target(t), description(d) {}
    
    CustomArg(const std::string& p, uint16_t* t, const std::string& d)
        : prefix(p), type(UINT16), target(t), description(d) {}
    
    CustomArg(const std::string& p, bool* t, const std::string& d)
        : prefix(p), type(BOOL), target(t), description(d) {}
};

// ============================================================================
// TEST RUNNER CLASS
// ============================================================================

class TestRunner {
public:
    explicit TestRunner(const std::string& programName);
    
    // Add custom command-line arguments
    void addArgument(const CustomArg& arg);
    
    // Parse arguments and initialize GoogleTest
    // Returns: -1 to continue, 0 if help shown, 1 if error
    int initialize(int& argc, char** argv);
    
    // Set pre-test validation callback
    void setPreTestValidator(std::function<bool()> validator);
    
    // Enable/disable strict argument checking (default: true)
    void setStrictArguments(bool strict);
    
    // Run all tests
    int runTests();
    
    // Accessors
    std::string getTimestamp() const { return timestamp_; }
    std::string getExecutablePath() const { return executablePath_; }
    
private:
    std::string programName_;
    std::string execName_;
    std::string timestamp_;
    std::string executablePath_;
    std::vector<CustomArg> customArgs_;
    bool helpRequested_;
    bool strictArgs_;
    std::function<bool()> preTestValidator_;
    
    std::vector<char*> newArgv_;
    int newArgc_;
};

} // namespace test_utils

#endif // TEST_UTILS_H
