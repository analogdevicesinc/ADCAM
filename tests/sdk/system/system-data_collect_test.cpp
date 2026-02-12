#include <gtest/gtest.h>
#include "test_utils.h"
#include <aditof/camera.h>
#include <aditof/system.h>
#include <aditof/frame.h>
#include <memory>
#include <vector>
#include <thread>
#include <chrono>
#include <fstream>
#include <cstdio>

using namespace test_utils;

// Global variables from test utilities
std::string& g_device_address = test_utils::g_device_address;
std::string& g_config_path = test_utils::g_config_path;
std::string& g_frame_mode = test_utils::g_frame_mode;

// ============================================================================
// TEST FIXTURE FOR DATA COLLECTION
// ============================================================================

class DataCollectTest : public ::testing::Test {
protected:
    std::unique_ptr<aditof::System> system;
    std::shared_ptr<aditof::Camera> camera;
    std::string testOutputDir = "/tmp/adcam_test_data";
    
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
        
        // Create test output directory
        ::system("mkdir -p /tmp/adcam_test_data");
    }
    
    void TearDown() override {
        if (camera) {
            camera->stop();
        }
        system.reset();
        
        // Cleanup test data
        ::system("rm -rf /tmp/adcam_test_data");
    }
    
    // Helper to collect N frames
    int collectFrames(int numFrames, uint8_t mode = 0) {
        std::vector<uint8_t> modes;
        camera->getAvailableModes(modes);
        if (modes.empty()) return -1;
        
        // Set mode
        camera->setMode(mode);
        
        // Start camera
        auto status = camera->start();
        if (status != aditof::Status::OK) return -1;
        
        int successfulFrames = 0;
        for (int i = 0; i < numFrames; ++i) {
            aditof::Frame frame;
            status = camera->requestFrame(&frame);
            
            if (status == aditof::Status::OK) {
                successfulFrames++;
            }
            
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        }
        
        camera->stop();
        return successfulFrames;
    }
};

// ============================================================================
// DATA COLLECTION TESTS
// ============================================================================

TEST_F(DataCollectTest, CollectSingleFrame) {
    int collected = collectFrames(1);
    EXPECT_EQ(collected, 1) << "Failed to collect single frame";
}

TEST_F(DataCollectTest, Collect10Frames) {
    int collected = collectFrames(10);
    EXPECT_GE(collected, 8) << "Should collect at least 80% of frames";
}

TEST_F(DataCollectTest, Collect50Frames) {
    int collected = collectFrames(50);
    EXPECT_GE(collected, 45) << "Should collect at least 90% of frames";
}

TEST_F(DataCollectTest, Collect100Frames) {
    int collected = collectFrames(100);
    EXPECT_GE(collected, 95) << "Should collect at least 95% of frames";
}

TEST_F(DataCollectTest, CollectFramesAllModes) {
    std::vector<uint8_t> modes;
    camera->getAvailableModes(modes);
    ASSERT_GT(modes.size(), 0);
    
    for (size_t i = 0; i < modes.size(); ++i) {
        int collected = collectFrames(10, static_cast<uint8_t>(i));
        EXPECT_GE(collected, 8) << "Failed for mode index: " << i << " (mode " << static_cast<int>(modes[i]) << ")";
    }
}

TEST_F(DataCollectTest, StressTestContinuousCollection) {
    // Collect frames continuously for multiple start/stop cycles
    const int cycles = 5;
    const int framesPerCycle = 20;
    
    for (int cycle = 0; cycle < cycles; ++cycle) {
        int collected = collectFrames(framesPerCycle);
        EXPECT_GE(collected, framesPerCycle * 0.9) 
            << "Failed on cycle " << cycle;
    }
}

TEST_F(DataCollectTest, VerifyFrameDataSize) {
    std::vector<uint8_t> modes;
    camera->getAvailableModes(modes);
    ASSERT_GT(modes.size(), 0);
    
    camera->setMode(0);
    auto status = camera->start();
    ASSERT_EQ(status, aditof::Status::OK);
    
    aditof::Frame frame;
    status = camera->requestFrame(&frame);
    ASSERT_EQ(status, aditof::Status::OK);
    
    // Get frame details
    aditof::FrameDetails frameDetails;
    status = frame.getDetails(frameDetails);
    ASSERT_EQ(status, aditof::Status::OK);
    
    // Verify frame dimensions
    EXPECT_GT(frameDetails.width, 0);
    EXPECT_GT(frameDetails.height, 0);
    
    // Check expected sizes for known modes
    // Mode 0-1 are MP (1024x1024), Mode 2-6 are QMP (512x512)
    if (modes[0] >= 2) {
        // QMP mode
        EXPECT_EQ(frameDetails.width, 512);
        EXPECT_EQ(frameDetails.height, 512);
    } else {
        // MP mode
        EXPECT_EQ(frameDetails.width, 1024);
        EXPECT_EQ(frameDetails.height, 1024);
    }
    
    camera->stop();
}

TEST_F(DataCollectTest, VerifyDepthDataRange) {
    std::vector<uint8_t> modes;
    camera->getAvailableModes(modes);
    ASSERT_GT(modes.size(), 0);
    
    camera->setMode(0);
    auto status = camera->start();
    ASSERT_EQ(status, aditof::Status::OK);
    
    aditof::Frame frame;
    status = camera->requestFrame(&frame);
    ASSERT_EQ(status, aditof::Status::OK);
    
    // Get depth data
    uint16_t* depthData;
    status = frame.getData("depth", &depthData);
    ASSERT_EQ(status, aditof::Status::OK);
    ASSERT_NE(depthData, nullptr);
    
    // Get frame details for size
    aditof::FrameDetails frameDetails;
    frame.getDetails(frameDetails);
    
    // Check some depth values are in valid range
    int validPixels = 0;
    int totalPixels = frameDetails.width * frameDetails.height;
    int sampleSize = std::min(1000, totalPixels);
    
    for (int i = 0; i < sampleSize; ++i) {
        if (depthData[i] > 0 && depthData[i] < 65535) {
            validPixels++;
        }
    }
    
    // At least some pixels should have valid depth
    EXPECT_GT(validPixels, 0) << "No valid depth data found";
    
    camera->stop();
}

// ============================================================================
// PARAMETERIZED TESTS FOR FRAME COUNTS
// ============================================================================

class FrameCountTest : public DataCollectTest,
                       public ::testing::WithParamInterface<int> {
};

TEST_P(FrameCountTest, CollectVariableFrames) {
    int numFrames = GetParam();
    int collected = collectFrames(numFrames);
    
    // Allow 10% tolerance for frame drops
    EXPECT_GE(collected, static_cast<int>(numFrames * 0.9))
        << "Failed to collect " << numFrames << " frames";
}

INSTANTIATE_TEST_SUITE_P(
    VariableFrameCounts,
    FrameCountTest,
    ::testing::Values(1, 5, 10, 25, 50, 100, 200)
);

// ============================================================================
// MODE-SPECIFIC TESTS
// ============================================================================

class ModeDataCollectTest : public DataCollectTest,
                            public ::testing::WithParamInterface<int> {
};

TEST_P(ModeDataCollectTest, CollectFramesPerMode) {
    int modeIndex = GetParam();
    
    std::vector<uint8_t> modes;
    camera->getAvailableModes(modes);
    
    if (modeIndex >= static_cast<int>(modes.size())) {
        GTEST_SKIP() << "Mode " << modeIndex << " not available";
    }
    
    int collected = collectFrames(10, static_cast<uint8_t>(modeIndex));
    EXPECT_GE(collected, 8) 
        << "Failed for mode index: " << modeIndex << " (mode " << static_cast<int>(modes[modeIndex]) << ")";
}

INSTANTIATE_TEST_SUITE_P(
    AllModes,
    ModeDataCollectTest,
    ::testing::Values(0, 1, 2, 3, 4, 5, 6)
);

// ============================================================================
// MAIN FUNCTION
// ============================================================================

int main(int argc, char** argv) {
    TestRunner runner(argv[0]);
    
    int initResult = runner.initialize(argc, argv);
    if (initResult != -1) {
        return initResult;
    }
    
    return runner.runTests();
}
