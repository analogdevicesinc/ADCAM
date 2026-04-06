cmake_minimum_required(VERSION 3.10)
project(adsd3500_sample_program)

# Source files
set(SOURCES
    src/run_adsd3500.cpp
    src/adsd3500_util.cpp
    src/adsd3500_interrupt_notifier.cpp
)

# Header files (for IDE integration)
set(HEADERS
    include/adsd3500_util.h
    include/adsd3500_interrupt_notifier.h
)

# Create executable
add_executable(${PROJECT_NAME} ${SOURCES} ${HEADERS})

# Set C++ standard
set_target_properties(${PROJECT_NAME} PROPERTIES CXX_STANDARD 11)

# Include directories
target_include_directories(${PROJECT_NAME} PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/libaditof/sdk/common  # For adi/tofi headers
)

# Find ToFi libraries
# They are typically in ../libs/ relative to ADCAM root or in /usr/lib
set(TOFI_LIB_SEARCH_PATHS
    "${CMAKE_SOURCE_DIR}/../libs"
    "${CMAKE_SOURCE_DIR}/../lib"
    "/usr/lib"
    "/usr/local/lib"
)

find_library(TOFI_COMPUTE_LIB
    NAMES tofi_compute libtofi_compute
    PATHS ${TOFI_LIB_SEARCH_PATHS}
    NO_DEFAULT_PATH
)

find_library(TOFI_CONFIG_LIB
    NAMES tofi_config libtofi_config
    PATHS ${TOFI_LIB_SEARCH_PATHS}
    NO_DEFAULT_PATH
)

# Fallback to system search if not found
if(NOT TOFI_COMPUTE_LIB)
    find_library(TOFI_COMPUTE_LIB NAMES tofi_compute libtofi_compute)
endif()

if(NOT TOFI_CONFIG_LIB)
    find_library(TOFI_CONFIG_LIB NAMES tofi_config libtofi_config)
endif()

# Check if libraries were found
if(NOT TOFI_COMPUTE_LIB OR NOT TOFI_CONFIG_LIB)
    message(WARNING "ToFi libraries not found. Searched in: ${TOFI_LIB_SEARCH_PATHS}")
    message(WARNING "  TOFI_COMPUTE_LIB: ${TOFI_COMPUTE_LIB}")
    message(WARNING "  TOFI_CONFIG_LIB: ${TOFI_CONFIG_LIB}")
    message(WARNING "The example will be configured but may fail to link.")
    message(WARNING "Install libraries or set TOFI_COMPUTE_LIB and TOFI_CONFIG_LIB manually.")
endif()

# Link libraries
# Note: This example uses ToFi compute library directly, not through aditof SDK
target_link_libraries(${PROJECT_NAME} PRIVATE
    ${TOFI_COMPUTE_LIB}
    ${TOFI_CONFIG_LIB}
)

# Install the executable
install(TARGETS ${PROJECT_NAME}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)

# Install configuration files (if they exist)
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/config")
    install(DIRECTORY config/
        DESTINATION ${CMAKE_INSTALL_PREFIX}/share/adsd3500_sample_program/config
        FILES_MATCHING PATTERN "*.ini" PATTERN "*.json" PATTERN "*.png"
    )
endif()

# Install Python visualization script (if it exists)
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/visualize.py")
    install(FILES visualize.py
        DESTINATION ${CMAKE_INSTALL_PREFIX}/share/adsd3500_sample_program/
        PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
    )
endif()

# Copy config directory to build directory for easier testing
add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E make_directory $<TARGET_FILE_DIR:${PROJECT_NAME}>/config
    COMMENT "Creating config directory in build output"
)

# Add a custom target to download config files (optional helper)
add_custom_target(download-adsd3500-configs
    COMMAND ${CMAKE_COMMAND} -E echo "Config files must be manually downloaded from:"
    COMMAND ${CMAKE_COMMAND} -E echo "https://github.com/analogdevicesinc/ToF/tree/rel-4.3.0-example-linux-code/tools/adsd3500_sample_program/config"
    COMMAND ${CMAKE_COMMAND} -E echo "Place them in: ${CMAKE_CURRENT_SOURCE_DIR}/config/"
    VERBATIM
)
