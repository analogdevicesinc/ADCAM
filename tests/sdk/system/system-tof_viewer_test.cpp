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
// TEST FIXTURE FOR TOF VIEWER / GUI TESTS
// ============================================================================

class TofViewerTest : public ::testing::Test {
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
    
    // Helper to simulate viewer operations
    bool simulateViewerSession(int numFrames, uint8_t mode = 0) {
        std::vector<uint8_t> modes;
        camera->getAvailableModes(modes);
        if (modes.empty()) return false;
        
        // Set mode
        camera->setMode(mode);
        
        // Start camera (like viewer does)
        auto status = camera->start();
        if (status != aditof::Status::OK) return false;
        
        // Simulate continuous frame display
        bool allFramesOk = true;
        for (int i = 0; i < numFrames; ++i) {
            aditof::Frame frame;
            status = camera->requestFrame(&frame);
            
            if (status != aditof::Status::OK) {
                allFramesOk = false;
                break;
            }
            
            // Simulate processing time (like rendering)
            std::this_thread::sleep_for(std::chrono::milliseconds(33)); // ~30 FPS
        }
        
        camera->stop();
        return allFramesOk;
    }
};

// ============================================================================
// GUI INITIALIZATION TESTS
// ============================================================================

TEST_F(TofViewerTest, CameraInitialization) {
    EXPECT_NE(camera, nullptr);
}

TEST_F(TofViewerTest, GetCameraInfo) {
    // Simulate getting camera info for GUI display
    std::vector<uint8_t> modes;
    auto status = camera->getAvailableModes(modes);
    
    EXPECT_EQ(status, aditof::Status::OK);
    EXPECT_GT(modes.size(), 0) << "No modes available for viewer";
}

// ============================================================================
// FRAME STREAMING TESTS (VIEWER PLAYBACK)
// ============================================================================

TEST_F(TofViewerTest, ShortStreamSession) {
    // Simulate short viewer session (10 frames)
    bool success = simulateViewerSession(10);
    EXPECT_TRUE(success) << "Failed to maintain short streaming session";
}

TEST_F(TofViewerTest, MediumStreamSession) {
    // Simulate medium viewer session (50 frames)
    bool success = simulateViewerSession(50);
    EXPECT_TRUE(success) << "Failed to maintain medium streaming session";
}

TEST_F(TofViewerTest, LongStreamSession) {
    // Simulate long viewer session (200 frames)
    bool success = simulateViewerSession(200);
    EXPECT_TRUE(success) << "Failed to maintain long streaming session";
}

TEST_F(TofViewerTest, ExtendedStreamSession) {
    // Simulate extended viewer session (500 frames, ~16 seconds at 30fps)
    bool success = simulateViewerSession(500);
    EXPECT_TRUE(success) << "Failed to maintain extended streaming session";
}

// ============================================================================
// MODE SWITCHING TESTS (VIEWER FUNCTIONALITY)
// ============================================================================

TEST_F(TofViewerTest, ModeSwitchingDuringStream) {
    std::vector<uint8_t> modes;
    camera->getAvailableModes(modes);
    ASSERT_GT(modes.size(), 1) << "Need at least 2 modes for switching test";
    
    // Stream in first mode
    camera->setMode(0);
    auto status = camera->start();
    ASSERT_EQ(status, aditof::Status::OK);
    
    // Capture some frames
    for (int i = 0; i < 10; ++i) {
        aditof::Frame frame;
        camera->requestFrame(&frame);
        std::this_thread::sleep_for(std::chrono::milliseconds(33));
    }
    
    // Stop and switch mode
    camera->stop();
    camera->setMode(1);
    
    // Resume streaming
    status = camera->start();
    EXPECT_EQ(status, aditof::Status::OK);
    
    // Capture more frames in new mode
    bool allOk = true;
    for (int i = 0; i < 10; ++i) {
        aditof::Frame frame;
        status = camera->requestFrame(&frame);
        if (status != aditof::Status::OK) {
            allOk = false;
            break;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(33));
    }
    
    EXPECT_TRUE(allOk) << "Failed after mode switch";
    camera->stop();
}

TEST_F(TofViewerTest, MultipleModeSwitches) {
    std::vector<uint8_t> modes;
    camera->getAvailableModes(modes);
    ASSERT_GT(modes.size(), 0);
    
    // Switch through all modes
    for (size_t i = 0; i < std::min(modes.size(), size_t(4)); ++i) {
        bool success = simulateViewerSession(10, static_cast<uint8_t>(i));
        EXPECT_TRUE(success) << "Failed on mode index: " << i << " (mode " << static_cast<int>(modes[i]) << ")";
    }
}

// ============================================================================
// START/STOP TESTS (VIEWER PAUSE/RESUME)
// ============================================================================

TEST_F(TofViewerTest, PauseResumeStream) {
    std::vector<uint8_t> modes;
    camera->getAvailableModes(modes);
    ASSERT_GT(modes.size(), 0);
    
    camera->setMode(modes[0]);
    
    // Start stream
    auto status = camera->start();
    ASSERT_EQ(status, aditof::Status::OK);
    
    // Stream some frames
    for (int i = 0; i < 10; ++i) {
        aditof::Frame frame;
        camera->requestFrame(&frame);
    }
    
    // Pause (stop)
    status = camera->stop();
    EXPECT_EQ(status, aditof::Status::OK);
    
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    
    // Resume (start again)
    status = camera->start();
    EXPECT_EQ(status, aditof::Status::OK);
    
    // Stream more frames
    bool resumeOk = true;
    for (int i = 0; i < 10; ++i) {
        aditof::Frame frame;
        status = camera->requestFrame(&frame);
        if (status != aditof::Status::OK) {
            resumeOk = false;
            break;
        }
    }
    
    EXPECT_TRUE(resumeOk) << "Failed to resume after pause";
    camera->stop();
}

TEST_F(TofViewerTest, MultiplePauseResumeCycles) {
    std::vector<uint8_t> modes;
    camera->getAvailableModes(modes);
    ASSERT_GT(modes.size(), 0);
    
    camera->setMode(modes[0]);
    
    const int cycles = 5;
    for (int cycle = 0; cycle < cycles; ++cycle) {
        // Start
        auto status = camera->start();
        ASSERT_EQ(status, aditof::Status::OK) << "Failed to start on cycle " << cycle;
        
        // Stream
        for (int i = 0; i < 5; ++i) {
            aditof::Frame frame;
            camera->requestFrame(&frame);
        }
        
        // Stop
        status = camera->stop();
        EXPECT_EQ(status, aditof::Status::OK) << "Failed to stop on cycle " << cycle;
        
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
}

// ============================================================================
// FRAME DATA QUALITY TESTS
// ============================================================================

TEST_F(TofViewerTest, VerifyFrameDataConsistency) {
    std::vector<uint8_t> modes;
    camera->getAvailableModes(modes);
    ASSERT_GT(modes.size(), 0);
    
    camera->setMode(modes[0]);
    auto status = camera->start();
    ASSERT_EQ(status, aditof::Status::OK);
    
    // Capture multiple frames and verify consistency
    aditof::FrameDetails firstFrameDetails;
    bool firstFrame = true;
    
    for (int i = 0; i < 20; ++i) {
        aditof::Frame frame;
        status = camera->requestFrame(&frame);
        ASSERT_EQ(status, aditof::Status::OK);
        
        aditof::FrameDetails details;
        frame.getDetails(details);
        
        if (firstFrame) {
            firstFrameDetails = details;
            firstFrame = false;
        } else {
            // All frames should have same dimensions
            EXPECT_EQ(details.width, firstFrameDetails.width);
            EXPECT_EQ(details.height, firstFrameDetails.height);
        }
    }
    
    camera->stop();
}

// ============================================================================
// PARAMETERIZED TESTS FOR ALL MODES
// ============================================================================

class ViewerModeTest : public TofViewerTest,
                       public ::testing::WithParamInterface<int> {
};

TEST_P(ViewerModeTest, StreamInSpecificMode) {
    int modeIndex = GetParam();
    
    std::vector<uint8_t> modes;
    camera->getAvailableModes(modes);
    
    if (modeIndex >= static_cast<int>(modes.size())) {
        GTEST_SKIP() << "Mode " << modeIndex << " not available";
    }
    
    bool success = simulateViewerSession(30, static_cast<uint8_t>(modeIndex));
    EXPECT_TRUE(success) << "Failed to stream in mode index: " << modeIndex << " (mode " << static_cast<int>(modes[modeIndex]) << ")";
}

INSTANTIATE_TEST_SUITE_P(
    AllViewerModes,
    ViewerModeTest,
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
