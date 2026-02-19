################################# PLATFORM DETECTION ###############################

# Platform detection function
function(detect_platform)
    set(DETECTED_PLATFORM "UNKNOWN" PARENT_SCOPE)
    
    # Check for Raspberry Pi
    if(EXISTS "/proc/device-tree/model")
        file(READ "/proc/device-tree/model" RPI_MODEL)
        if(RPI_MODEL MATCHES "Raspberry Pi")
            set(DETECTED_PLATFORM "RPI" PARENT_SCOPE)
            message(STATUS "Platform auto-detected: Raspberry Pi")
            return()
        endif()
    endif()
    
    # Check for NVIDIA Jetson
    if(EXISTS "/proc/device-tree/model")
        file(READ "/proc/device-tree/model" JETSON_MODEL)
        if(JETSON_MODEL MATCHES "Jetson")
            set(DETECTED_PLATFORM "NVIDIA" PARENT_SCOPE)
            message(STATUS "Platform auto-detected: NVIDIA Jetson")
            return()
        endif()
    endif()
    
    # Fallback: check for environment variables
    if(DEFINED ENV{JETSON_TARGETS})
        set(DETECTED_PLATFORM "NVIDIA" PARENT_SCOPE)
        message(STATUS "Platform detected via environment: NVIDIA Jetson")
        return()
    endif()
    
    message(STATUS "Platform auto-detection: Could not detect hardware, defaulting to RPI")
    set(DETECTED_PLATFORM "RPI" PARENT_SCOPE)
endfunction()

# Auto-detect or use explicit choice
string(COMPARE EQUAL "${PLATFORM_CHOICE}" "NVIDIA" IS_NVIDIA)
string(COMPARE EQUAL "${PLATFORM_CHOICE}" "AUTO" IS_AUTO)
string(COMPARE EQUAL "${PLATFORM_CHOICE}" "RPI" IS_RPI)
string(COMPARE EQUAL "${PLATFORM_CHOICE}" "HOST" IS_HOST)

if(IS_AUTO)
    detect_platform()
    if(DETECTED_PLATFORM STREQUAL NVIDIA)
        set(NVIDIA ON CACHE BOOL "Set to ON when building on NVIDIA" FORCE)
    elseif(DETECTED_PLATFORM STREQUAL RPI)
        set(RPI ON CACHE BOOL "Set to ON when building on Raspberry Pi" FORCE)
    else()
        set(RPI ON CACHE BOOL "Set to ON when building on Raspberry Pi" FORCE)
    endif()
elseif(IS_NVIDIA)
    set(NVIDIA ON CACHE BOOL "Set to ON when building on NVIDIA" FORCE)
    message(STATUS "Platform explicitly set to: NVIDIA")
elseif(IS_RPI)
    set(RPI ON CACHE BOOL "Set to ON when building on Raspberry Pi" FORCE)
    message(STATUS "Platform explicitly set to: Raspberry Pi")
elseif(IS_HOST)
    message(STATUS "Platform set to: HOST (no platform-specific flags)")
else()
    message(FATAL_ERROR "Invalid PLATFORM_CHOICE: ${PLATFORM_CHOICE}. Use AUTO, NVIDIA, RPI, or HOST.")
endif()

