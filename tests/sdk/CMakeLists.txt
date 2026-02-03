cmake_minimum_required(VERSION 3.15)
project(sdk)

# Add existing test directories
add_subdirectory(sdk_stream_test)

# Check if GoogleTest is available for system tests
find_package(GTest QUIET)

if(GTEST_FOUND)
    message(STATUS "GoogleTest found - enabling system tests")
    
    # Set test output directory
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/tests/bin)

    # Common test utilities library
    add_library(test_utils STATIC
        src/test_utils.cpp
    )

    target_include_directories(test_utils PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
    )

    target_link_libraries(test_utils
        PUBLIC
        GTest::gtest
        GTest::gtest_main
        aditof
    )

    # Function to add a test executable
    function(add_adcam_test target_name source_file)
        add_executable(${target_name} ${source_file})
        
        target_link_libraries(${target_name}
            PRIVATE
            test_utils
            GTest::gtest
            aditof
        )
        
        # Add to CTest
        add_test(NAME ${target_name} COMMAND ${target_name})
        
        # Set test properties
        set_tests_properties(${target_name} PROPERTIES
            TIMEOUT 300
            LABELS "automated"
        )
    endfunction()

    # Add test executables
    # System tests
    if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/system/system-first_frame_test.cpp)
        add_adcam_test(system-first_frame_test system/system-first_frame_test.cpp)
    endif()

    if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/system/system-frame_modes_test.cpp)
        add_adcam_test(system-frame_modes_test system/system-frame_modes_test.cpp)
    endif()

    if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/system/system-data_collect_test.cpp)
        add_adcam_test(system-data_collect_test system/system-data_collect_test.cpp)
    endif()

    if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/system/system-tof_viewer_test.cpp)
        add_adcam_test(system-tof_viewer_test system/system-tof_viewer_test.cpp)
    endif()

    # Enable testing
    enable_testing()
else()
    message(STATUS "GoogleTest not found - skipping system tests")
endif()