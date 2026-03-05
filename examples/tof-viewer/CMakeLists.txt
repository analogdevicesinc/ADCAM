# Copyright (c) Analog Devices, Inc. All rights reserved.
# Minimum Version determined by the following dev environments
# Visual Studio 2017 15.7 - CMake 3.11
cmake_minimum_required(VERSION 3.10)

# set the project name
project(ADIToFGUI LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(ENABLE_CUDA_ACCELERATION "Enable CUDA GPU acceleration if available" ON)

# WSL2-specific OpenGL version configuration
if(WSL2)
    set(WSL2_GL_VERSION "3.3" CACHE STRING "WSL2 OpenGL version override (3.3 or 4.6)")
    if(WSL2_GL_VERSION STREQUAL "4.6")
        add_compile_definitions(WSL2_GL_VERSION_MAJOR=4 WSL2_GL_VERSION_MINOR=6)
        message(STATUS "WSL2 OpenGL override: 4.6 (requires GPU passthrough)")
    else()
        add_compile_definitions(WSL2_GL_VERSION_MAJOR=3 WSL2_GL_VERSION_MINOR=3)
        message(STATUS "WSL2 OpenGL override: 3.3 (default)")
    endif()
endif()

# Disable ARM and CUDA support on Windows - use x86 SIMD (AVX2) instead
if(WIN32)
    set(USE_CUDA OFF)
    set(USE_ARM_NEON OFF)
    message(STATUS "Windows platform: ARM NEON and CUDA disabled, using x86 SIMD (AVX2)")
# Check for CUDA support on ARM64 (Linux/embedded only)
elseif(ENABLE_CUDA_ACCELERATION AND (CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64" OR CMAKE_SYSTEM_PROCESSOR MATCHES "arm64"))
    # Try to enable CUDA on ARM64 platforms (Jetson)
    include(CheckLanguage)
    check_language(CUDA)
    if(CMAKE_CUDA_COMPILER)
        enable_language(CUDA)
        set(USE_CUDA ON)
        set(USE_ARM_NEON ON)
        set(CMAKE_CUDA_STANDARD 14)
        set(CMAKE_CUDA_STANDARD_REQUIRED ON)
        message(STATUS "CUDA support enabled for ARM64")
    else()
        set(USE_CUDA OFF)
        set(USE_ARM_NEON ON)
        message(STATUS "CUDA not found, using NEON optimizations only")
    endif()
else()
    set(USE_CUDA OFF)
    if(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64" OR CMAKE_SYSTEM_PROCESSOR MATCHES "arm64")
        set(USE_ARM_NEON ON)
        message(STATUS "CUDA acceleration disabled (ENABLE_CUDA_ACCELERATION=OFF), using NEON only")
    else()
        set(USE_ARM_NEON OFF)
        message(STATUS "Using standard x86 SIMD optimizations (AVX2)")
    endif()
endif()

option(ENBABLE_PASSIVE_IR "Allow passive IR (PCM) mode" OFF)

configure_file(ADIToFConfig.h.in ADIToFConfig.h)

# adding submodules and subdirectories
if( WIN32 )
    set(OS_SPECIFIC_DIR windows)
elseif ( APPLE )
    set(CMAKE_CXX_FLAGS "-x objective-c")
    set(OS_SPECIFIC_SOURCES ${ADIToF_SOURCE_DIR}/fileDialog.mm) 	
elseif ( UNIX )
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -pthread")
    set(OS_SPECIFIC_DIR linux)
else()
    message(FATAL_ERROR "Platform not supported")
endif()

# Disable Wayland support for GLFW to avoid missing protocol file dependencies
set(GLFW_BUILD_WAYLAND OFF CACHE BOOL "Build support for Wayland" FORCE)

add_subdirectory("${CMAKE_SOURCE_DIR}/dependencies/third-party/imgui/glfw" "${CMAKE_BINARY_DIR}/glfw")

set(IMGUI_SOURCE_DIR ${CMAKE_SOURCE_DIR}/dependencies/third-party/imgui)
set(IMGUI_TOGGLE_SOURCE_DIR ${CMAKE_SOURCE_DIR}/dependencies/third-party/imgui/imgui_toggle)
set(IMPLOT_SOURCE_DIR ${CMAKE_SOURCE_DIR}/dependencies/third-party/imgui/implot)
set(IMOGUIZMO_SOURCE_DIR ${CMAKE_SOURCE_DIR}/dependencies/third-party/imgui/imoguizmo)
set(GLM_SOURCE_DIR ${CMAKE_SOURCE_DIR}/dependencies/third-party/imgui/glm)
set(ADIToF_SOURCE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/src)
set(IMGUIMD__SOURCE_DIR ${CMAKE_SOURCE_DIR}/dependencies/third-party/imgui/imgui_md)
set(M4DC_SOURCE_DIR ${CMAKE_SOURCE_DIR}/dependencies/third-party/imgui/m4dc)

# Collect all source files EXCEPT platform-specific optimized versions
file(GLOB ADIToF_SOURCES CONFIGURE_DEPENDS "${ADIToF_SOURCE_DIR}/*.cpp")

# Remove ARM NEON and CUDA files from the list (we'll add them conditionally)
list(FILTER ADIToF_SOURCES EXCLUDE REGEX ".*ADIView_neon\\.cpp$")
list(FILTER ADIToF_SOURCES EXCLUDE REGEX ".*ADIView_cuda_wrapper\\.cpp$")

# Add ARM NEON optimized source files for ARM64 platforms (not on Windows)
if(USE_ARM_NEON)
    list(APPEND ADIToF_SOURCES "${ADIToF_SOURCE_DIR}/ADIView_neon.cpp")
    message(STATUS "Adding ARM NEON optimized sources")
    
    # Enable NEON compilation flags
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        add_compile_options(-march=armv8-a+simd)
    endif()
else()
    message(STATUS "ARM NEON sources excluded")
endif()

# Add CUDA source files if CUDA is available (not on Windows)
if(USE_CUDA)
    list(APPEND ADIToF_SOURCES "${ADIToF_SOURCE_DIR}/ADIView_cuda_wrapper.cpp")
    set(CUDA_SOURCES "${ADIToF_SOURCE_DIR}/ADIView_cuda.cu")
    message(STATUS "Adding CUDA accelerated sources")
else()
    message(STATUS "CUDA sources excluded")
endif()

# Enable x86 SIMD (AVX2) on Windows
if(WIN32)
    if(MSVC)
        add_compile_options(/arch:AVX2)
        message(STATUS "Enabling AVX2 optimizations for Windows (MSVC)")
    elseif(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        add_compile_options(-mavx2 -mfma)
        message(STATUS "Enabling AVX2 optimizations for Windows (GCC/Clang)")
    endif()
endif()

if(USE_CUDA)
    add_executable(ADIToFGUI
        ${ADIToF_SOURCES}
        ${CUDA_SOURCES}
        ${OS_SPECIFIC_SOURCES}
    )
    
    # Set CUDA properties
    set_target_properties(ADIToFGUI PROPERTIES
        CUDA_SEPARABLE_COMPILATION ON
        CUDA_RESOLVE_DEVICE_SYMBOLS ON
    )
    
    # Add CUDA architectures for Jetson Orin
    set_property(TARGET ADIToFGUI PROPERTY CUDA_ARCHITECTURES 87)
    
    target_compile_definitions(ADIToFGUI PRIVATE USE_CUDA)
else()
    add_executable(ADIToFGUI
        ${ADIToF_SOURCES}
        ${OS_SPECIFIC_SOURCES}
    )
endif()

# Link Libraries
if(UNIX)
	set(OpenGL_GL_PREFERENCE "LEGACY")
endif()

find_package(OpenGL REQUIRED)
if( WIN32 )																	 
	#target_link_libraries(ADIToFGUI PRIVATE "${PROJECT_BINARY_DIR}/src/examples/libs/glfw/lib-vc2010-64/glfw3.lib")
	target_link_libraries(ADIToFGUI PUBLIC glfw)
elseif (UNIX)
	find_package(glfw3 REQUIRED)
	target_link_libraries(${PROJECT_NAME} PRIVATE glfw)
endif()

target_link_libraries(ADIToFGUI PRIVATE
					  aditof
					  imgui::imgui
					  ${OPENGL_gl_LIBRARY}
					  ${CMAKE_DL_LIBS}
					  json-c
					 )

# Generate tof-viewer.md only when building ADIToFGUI
find_package(Python3 COMPONENTS Interpreter)
if(Python3_FOUND)
    file(GLOB ADCAM_SOURCE_MD "${CMAKE_SOURCE_DIR}/doc/user-guide/ADCAM-CameraKit-*.md")
    if(ADCAM_SOURCE_MD)
        list(GET ADCAM_SOURCE_MD 0 ADCAM_MD_FILE)
        get_filename_component(ADCAM_MD_NAME "${ADCAM_MD_FILE}" NAME)

        set(TOF_VIEWER_MD "${CMAKE_SOURCE_DIR}/doc/user-guide/tof-viewer.md")
        set(EXTRACT_SCRIPT "${CMAKE_SOURCE_DIR}/doc/user-guide/extract_gui_markdown.py")

        add_custom_command(
            OUTPUT "${TOF_VIEWER_MD}"
            COMMAND ${Python3_EXECUTABLE} ${EXTRACT_SCRIPT}
                    ${ADCAM_MD_FILE}
                    ${TOF_VIEWER_MD}
                    --skip-first 10
                    --drop-last 1
            DEPENDS ${ADCAM_MD_FILE} ${EXTRACT_SCRIPT}
            WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}/doc/user-guide
            COMMENT "Generating tof-viewer.md from ${ADCAM_MD_NAME}"
        )

        add_custom_target(generate_tof_viewer_md
            DEPENDS "${TOF_VIEWER_MD}"
        )

        add_dependencies(ADIToFGUI generate_tof_viewer_md)
    else()
        message(WARNING "No ADCAM-CameraKit-*.md found - tof-viewer.md will not be auto-generated")
    endif()
else()
    message(WARNING "Python3 not found - tof-viewer.md will not be auto-generated")
endif()

# Link CUDA runtime if CUDA is enabled
if(USE_CUDA)
    target_link_libraries(ADIToFGUI PRIVATE ${CUDA_LIBRARIES})
    message(STATUS "Linking CUDA libraries")
endif()

# Add architecture-specific optimizations for x86_64
if(CMAKE_SYSTEM_PROCESSOR MATCHES "(x86)|(X86)|(amd64)|(AMD64)")
    target_compile_options(ADIToFGUI PRIVATE -mavx2 -mfma)
    message(STATUS "Enabling AVX2 optimizations for x86_64")
endif()

if( WIN32 )					 
	set_target_properties(ADIToFGUI PROPERTIES
	LINK_FLAGS /SUBSYSTEM:WINDOWS
	)
elseif(APPLE)
    set(CMAKE_CXX_FLAGS "-framework Carbon -framework Cocoa -framework OpenGL -framework IOKit -framework CoreVideo")
endif()
	
target_include_directories(ADIToFGUI PUBLIC
						"${PROJECT_BINARY_DIR}"
						"${PROJECT_SOURCE_DIR}/include"
						"${IMGUI_SOURCE_DIR}/src/examples/libs/gl3w"
						"${IMGUI_SOURCE_DIR}/src/examples/libs/glfw/include"
						"${IMGUI_SOURCE_DIR}/src/examples"
						"${IMGUI_SOURCE_DIR}/src"
						"${IMGUI_TOGGLE_SOURCE_DIR}"
						"${IMPLOT_SOURCE_DIR}"
						"${IMOGUIZMO_SOURCE_DIR}"
						"${GLM_SOURCE_DIR}"
						"${PROJECT_SOURCE_DIR}/src"
						"${IMGUIMD__SOURCE_DIR}"
						"${M4DC_SOURCE_DIR}/src"
				)

target_include_directories(ADIToFGUI PUBLIC
                        "${CMAKE_SOURCE_DIR}/libaditof/sdk/src/cameras/itof-camera")

# Add json-c include directories (both source and build for generated headers)
target_include_directories(ADIToFGUI PRIVATE
                        "${CMAKE_SOURCE_DIR}/libaditof/dependencies/third-party/json-c"
                        "${CMAKE_BINARY_DIR}/libaditof/dependencies/third-party/json-c")

if (ENBABLE_PASSIVE_IR)
	message(STATUS "Building with Passive IR Mode enabled")
	add_definitions(-DENBABLE_PASSIVE_IR)
endif()

# Copying necessary dlls from SDK and the necessary config files
add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different ${CMAKE_CURRENT_SOURCE_DIR}/tof-tools.config $<TARGET_FILE_DIR:${PROJECT_NAME}>/.
    COMMAND ${CMAKE_COMMAND} -E copy_if_different ${LIBADITOF_SUBMODULE_PATH}/sdk/src/cameras/itof-camera/config/config_adsd3500_adsd3100.json $<TARGET_FILE_DIR:${PROJECT_NAME}>/.
    COMMAND ${CMAKE_COMMAND} -E copy_if_different ${LIBADITOF_SUBMODULE_PATH}/sdk/src/cameras/itof-camera/config/config_adsd3500_adsd3030.json $<TARGET_FILE_DIR:${PROJECT_NAME}>/.
    COMMAND ${CMAKE_COMMAND} -E copy_if_different ${CMAKE_SOURCE_DIR}/doc/user-guide/tof-viewer.md $<TARGET_FILE_DIR:${PROJECT_NAME}>/.
    COMMAND ${CMAKE_COMMAND} -E copy_directory ${CMAKE_SOURCE_DIR}/doc/user-guide/images $<TARGET_FILE_DIR:${PROJECT_NAME}>/images
    COMMENT "Copying docs, cfgs and libs to build examples for tof-viewer."
	)

if(WIN32)
	# copy sdk lib and dc dll to exe directory
	add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
					COMMAND ${CMAKE_COMMAND} -E copy_directory $<TARGET_LINKER_FILE_DIR:aditof> ${CMAKE_CURRENT_BINARY_DIR}/$<CONFIG>
					)

	set_target_properties(ADIToFGUI PROPERTIES VS_DEBUGGER_WORKING_DIRECTORY "$(ProjectDir)\\$(Configuration)")
endif()
