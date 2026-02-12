#include <gtest/gtest.h>
#include "test_utils.h"
#include <aditof/camera.h>
#include <aditof/system.h>
#include <aditof/frame.h>
#include <memory>
#include <vector>
#include <thread>
#include <chrono>

using namespace test_utils;

// Global variables from test utilities
std::string& g_device_address = test_utils::g_device_address;
std::string& g_config_path = test_utils::g_config_path;
std::string& g_frame_mode = test_utils::g_frame_mode;

// ============================================================================
// TEST FIXTURE DEFINITION
// ============================================================================

class FirstFrameTest : public ::testing::Test {
protected:
    std::unique_ptr<aditof::System> system;
    std::shared_ptr<aditof::Camera> camera;
    
    void SetUp() override {
        // Create system
        system = std::make_unique<aditof::System>();
        
        // Find cameras
        std::vector<std::shared_ptr<aditof::Camera>> cameras;
        auto status = system->getCameraList(cameras);
        
        if (status != aditof::Status::OK) {
            GTEST_SKIP() << "Failed to get camera list: " << static_cast<int>(status);
        }
        
        if (cameras.empty()) {
            GTEST_SKIP() << "No cameras found - hardware may not be connected";
        }
        
        // Use first camera
        camera = cameras[0];
        
        // Initialize camera
        status = camera->initialize();
        if (status != aditof::Status::OK) {
            GTEST_SKIP() << "Failed to initialize camera: " << static_cast<int>(status);
        }
    }
    
    void TearDown() override {
        if (camera) {
            camera->stop();
        }
        system.reset();
    }
};

// ============================================================================
// BASIC TESTS
// ============================================================================

TEST(SystemBasicTest, SystemCreation) {
    EXPECT_NO_THROW({
        aditof::System sys;
    });
}

TEST(SystemBasicTest, CameraDiscovery) {
    aditof::System sys;
    std::vector<std::shared_ptr<aditof::Camera>> cameras;
    auto status = sys.getCameraList(cameras);
    
    EXPECT_EQ(status, aditof::Status::OK);
    // Note: cameras may be empty if hardware not connected
}

// ============================================================================
// FIXTURE-BASED TESTS
// ============================================================================

TEST_F(FirstFrameTest, CameraInitialization) {
    EXPECT_NE(camera, nullptr);
}

TEST_F(FirstFrameTest, GetAvailableModes) {
    std::vector<uint8_t> modes;
    auto status = camera->getAvailableModes(modes);
    
    EXPECT_EQ(status, aditof::Status::OK);
    EXPECT_GT(modes.size(), 0) << "No frame modes available";
}

TEST_F(FirstFrameTest, SetFrameMode) {
    std::vector<uint8_t> modes;
    auto status = camera->getAvailableModes(modes);
    ASSERT_EQ(status, aditof::Status::OK);
    ASSERT_GT(modes.size(), 0);
    
    // Try to set mode 0 (first MP mode)
    status = camera->setMode(0);
    EXPECT_EQ(status, aditof::Status::OK);
}

TEST_F(FirstFrameTest, StartStopCamera) {
    std::vector<uint8_t> modes;
    camera->getAvailableModes(modes);
    ASSERT_GT(modes.size(), 0);
    
    camera->setMode(0);
    
    auto status = camera->start();
    EXPECT_EQ(status, aditof::Status::OK);
    
    // Give camera time to start
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    
    status = camera->stop();
    EXPECT_EQ(status, aditof::Status::OK);
}

TEST_F(FirstFrameTest, CaptureFrame) {
    // Get available modes
    std::vector<uint8_t> modes;
    camera->getAvailableModes(modes);
    ASSERT_GT(modes.size(), 0);
    
    // Set mode
    camera->setMode(modes[0]);
    
    // Start camera
    auto status = camera->start();
    ASSERT_EQ(status, aditof::Status::OK);
    
    // Create frame
    aditof::Frame frame;
    
    // Request frame (this should capture one)
    status = camera->requestFrame(&frame);
    EXPECT_EQ(status, aditof::Status::OK);
    
    // Get frame details
    aditof::FrameDetails frameDetails;
    status = frame.getDetails(frameDetails);
    EXPECT_EQ(status, aditof::Status::OK);
    
    EXPECT_GT(frameDetails.width, 0) << "Frame width should be > 0";
    EXPECT_GT(frameDetails.height, 0) << "Frame height should be > 0";
    
    // Stop camera
    camera->stop();
}

TEST_F(FirstFrameTest, CaptureMultipleFrames) {
    // Get available modes
    std::vector<uint8_t> modes;
    camera->getAvailableModes(modes);
    ASSERT_GT(modes.size(), 0);
    
    // Set mode
    camera->setMode(0);
    
    // Start camera
    auto status = camera->start();
    ASSERT_EQ(status, aditof::Status::OK);
    
    const int numFrames = 10;
    int successfulFrames = 0;
    
    for (int i = 0; i < numFrames; ++i) {
        aditof::Frame frame;
        status = camera->requestFrame(&frame);
        
        if (status == aditof::Status::OK) {
            successfulFrames++;
        }
        
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
    
    EXPECT_GT(successfulFrames, numFrames / 2) 
        << "Should capture at least half of requested frames";
    
    // Stop camera
    camera->stop();
}

TEST_F(FirstFrameTest, FrameDataAccess) {
    // Get available modes
    std::vector<uint8_t> modes;
    camera->getAvailableModes(modes);
    ASSERT_GT(modes.size(), 0);
    
    // Set mode
    camera->setMode(0);
    
    // Start camera
    auto status = camera->start();
    ASSERT_EQ(status, aditof::Status::OK);
    
    // Create frame
    aditof::Frame frame;
    
    // Request frame
    status = camera->requestFrame(&frame);
    ASSERT_EQ(status, aditof::Status::OK);
    
    // Get frame data
    uint16_t* depthData;
    status = frame.getData("depth", &depthData);
    EXPECT_EQ(status, aditof::Status::OK);
    EXPECT_NE(depthData, nullptr);
    
    // Stop camera
    camera->stop();
}

// ============================================================================
// PARAMETERIZED TESTS FOR DIFFERENT MODES
// ============================================================================

class FrameModeTest : public FirstFrameTest, 
                      public ::testing::WithParamInterface<int> {
};

TEST_P(FrameModeTest, TestSpecificMode) {
    int modeIndex = GetParam();
    
    std::vector<uint8_t> modes;
    auto status = camera->getAvailableModes(modes);
    ASSERT_EQ(status, aditof::Status::OK);
    
    if (modeIndex >= static_cast<int>(modes.size())) {
        GTEST_SKIP() << "Mode " << modeIndex << " not available";
    }
    
    // Set mode
    status = camera->setMode(static_cast<uint8_t>(modeIndex));
    ASSERT_EQ(status, aditof::Status::OK);
    
    // Start camera
    status = camera->start();
    ASSERT_EQ(status, aditof::Status::OK);
    
    // Capture frame
    aditof::Frame frame;
    status = camera->requestFrame(&frame);
    EXPECT_EQ(status, aditof::Status::OK);
    
    // Stop camera
    camera->stop();
}

INSTANTIATE_TEST_SUITE_P(
    AllModes,
    FrameModeTest,
    ::testing::Values(0, 1, 2, 3, 4, 5, 6)
);

// ============================================================================
// MAIN FUNCTION WITH CUSTOM ARGUMENTS
// ============================================================================

int main(int argc, char** argv) {
    // Create test runner
    TestRunner runner(argv[0]);
    
    // Add custom arguments (beyond the defaults)
    // Note: --device, --config, and --mode are automatically added
    
    // Initialize (parses args, sets up GoogleTest)
    int initResult = runner.initialize(argc, argv);
    if (initResult != -1) {
        return initResult;  // Help was shown or error occurred
    }
    
    // Run tests
    return runner.runTests();
}
