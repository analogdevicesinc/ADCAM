cmake_minimum_required(VERSION 3.0)
project(adi_tof_project)

####################### Disable In-source builds ##############################
if( ${CMAKE_SOURCE_DIR} STREQUAL ${CMAKE_BINARY_DIR} )
    message(FATAL_ERROR "In-source builds are not allowed. \
    Consider making a separate build folder and run cmake \
    from there using this command:
    cmake ${CMAKE_SOURCE_DIR}")
endif()

############################### Version #######################################
set(ADCAM_VERSION_MAJOR 0)
set(ADCAM_VERSION_MINOR 2)
set(ADCAM_VERSION_PATCH 0)

set(VERSION "${ADCAM_VERSION_MAJOR}.${ADCAM_VERSION_MINOR}.${ADCAM_VERSION_PATCH}")

############################### Options #######################################
option(WITH_EXAMPLES "Build examples?" ON)
option(WITH_DOC "Build documentation?" OFF)
option(WITH_PYTHON "Build python bindings?" ON)
option(WITH_NETWORK "Build network interface?" OFF)

################################# FIXED #######################################

### Note: Turn the following off when building on the host
option(NVIDIA "Set to ON when building on NVIDIA" ON)

if (WITH_NETWORK)
        option(WITH_SUBMODULES "Use submodules to build the library" ON)
        option(WITH_PROTOBUF_DEPENDENCY "Build with PROTOBUF dependency?" ON)
else()
        option(WITH_SUBMODULES "Use submodules to build the library" OFF)
        option(WITH_PROTOBUF_DEPENDENCY "Build with PROTOBUF dependency?" OFF)
endif()
option(WITH_OFFLINE "Build offline interface?" ON)
option(WITH_COMMAND_LINE_TOOLS "Build with command line tools?" ON)
option(USE_DEPTH_COMPUTE_OPENSOURCE "Use an open source implementation?" OFF)
option(CI_BUILD "Build for CI" OFF)
set(SOM_TYPE "Dual" CACHE STRING "Which SoM SDK is building for?")
################################## Git ########################################
include(FindGit OPTIONAL)
if (GIT_FOUND)
        execute_process(
                COMMAND ${GIT_EXECUTABLE} rev-parse --show-toplevel
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                OUTPUT_VARIABLE ADITOFSDK_GIT_REPO
                OUTPUT_STRIP_TRAILING_WHITESPACE
                ERROR_QUIET
        )

        if ("${ADITOFSDK_GIT_REPO}" STREQUAL "${CMAKE_CURRENT_SOURCE_DIR}")
                execute_process(
                        COMMAND ${GIT_EXECUTABLE} rev-parse --short HEAD
                        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                        OUTPUT_VARIABLE ADITOFSDK_GIT_COMMIT
                        OUTPUT_STRIP_TRAILING_WHITESPACE
                )
                execute_process(
                        COMMAND ${GIT_EXECUTABLE} rev-parse --abbrev-ref HEAD
                        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                        OUTPUT_VARIABLE TOFSDK_GIT_BRANCH
                        OUTPUT_STRIP_TRAILING_WHITESPACE
                )
        endif()
        if (WITH_SUBMODULES)
                add_definitions(-DWITH_SUBMODULES)
                message("Updating submodules")
                execute_process(COMMAND ${GITEXECUTABLE} submodule update --init
                        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                        RESULT_VARIABLE WITH_SUBMODULES_RESULT)

                if(NOT WITH_SUBMODULES_RESULT EQUAL 0)
                        message(ERROR "Git submodules failed to initialize, check submodules")
                endif()
        endif()
endif()

add_definitions(-DTOFSDK_GIT_COMMIT="${TOFSDK_GIT_COMMIT}")
add_definitions(-DTOFSDK_GIT_BRANCH="${TOFSDK_GIT_BRANCH}")

############################## Rest of cmake ##################################

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Set general path for libaditof submodule
set(LIBADITOF_SUBMODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR}/libaditof)

# Check whether we configure thgs for remote or we're on target
set(SELECTED_PLATFORMS 0)
set(ALL_PLATFORMS NVIDIA)
foreach(platform IN LISTS ALL_PLATFORMS)
    if(${platform})
        math(EXPR SELECTED_PLATFORMS "${SELECTED_PLATFORMS}+1")
    endif()
endforeach()

set(ON_TARGET FALSE)
if(${SELECTED_PLATFORMS} GREATER 1)
        message(FATAL_ERROR "More than one platform was selected. \nPlease select a single platform. CMake will exit.")
elseif(${SELECTED_PLATFORMS} EQUAL 1)
    add_definitions(-DTARGET)
    set(ON_TARGET TRUE)
endif()

if(NOT ON_TARGET AND USE_DEPTH_COMPUTE_OPENSOURCE)
        message (STATUS "USE_DEPTH_COMPUTE_OPENSOURCE is not used on host")
endif()

if(CI_BUILD)
    set(USE_DEPTH_COMPUTE_OPENSOURCE ON)
endif()

if (WITH_NETWORK)
        add_definitions(-DHAS_NETWORK)
endif()

if(SOM_TYPE STREQUAL "Dual")
        message("Building for Dual pulsatrix")
        add_definitions(-DDUAL)
else()
        add_definitions(-DSINGLE)
endif()


# Add the device definition
if(NVIDIA)
     add_definitions(-DNVIDIA)
endif()

set(RESOURCES_DIR "${CMAKE_BINARY_DIR}/resources")
make_directory(${RESOURCES_DIR})

if (WITH_OFFLINE)
        add_definitions(-DHAS_OFFLINE)
endif()

if(NOT WITH_PROTOBUF_DEPENDENCY)
        if(NOT ON_TARGET)
                message(FATAL_ERROR "SDK can be built without protobuf only on target builds!")
        endif()
else()
        add_definitions(-DUSE_PROTOBUF)
endif()

if(${ON_TARGET})
        if(USE_DEPTH_COMPUTE_OPENSOURCE)
                set(LIBTOFI_LIBDIR_PATH "${CMAKE_BINARY_DIR}/libaditof/sdk/common/adi/depth-compute-opensource")
        else()
                if (NOT DEFINED LIBTOFI_LIBDIR_PATH)
                        set(LIBTOFI_LIBDIR_PATH "${CMAKE_SOURCE_DIR}/../libs")
                endif()
        endif()
endif()

set(CONFIG_DIR_NAME "config")

add_definitions(-DCONFIG_DIR_NAME="${CONFIG_DIR_NAME}")
add_definitions(-DRESOURCES="${RESOURCES_DIR}")

add_subdirectory(dependencies)
add_subdirectory(libaditof)
add_subdirectory(apps)
add_subdirectory(tests)


if (WITH_EXAMPLES)
        add_subdirectory(examples)
endif()
if (WITH_DOC)
        add_subdirectory(doc)
endif()
if (WITH_PYTHON)
        add_subdirectory(examples/bindings/python)
endif()
if (WITH_COMMAND_LINE_TOOLS)
        add_subdirectory(tools)
endif()

############################### Installer #######################################
configure_file(cmake/aditof-setup.iss.cmakein ${CMAKE_CURRENT_BINARY_DIR}/aditof-setup.iss @ONLY)

############################### Version #######################################
configure_file(cmake/version.h.cmakein ${CMAKE_SOURCE_DIR}/libaditof/sdk/include/aditof/version-kit.h @ONLY)
