cmake_minimum_required(VERSION 3.0)
project(evalkit-doc)

find_program(DOXYGEN_PATH doxygen)
if (NOT DOXYGEN_PATH)
    message(FATAL_ERROR "doxygen not found!")
endif()

######################### This script variables ###############################
set(SOURCES_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../libaditof/sdk/include/aditof)
set(DOXY_WORKING_DIR ${CMAKE_CURRENT_BINARY_DIR}/doxygen_doc)

############################# Doc variables ###################################
set(PROJECT_NAME "Time-of-Flight-SDK")
set(SOURCES_SDK_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../libaditof/sdk)
set(DOCUMENTED_FILES_LIST
    "${SOURCES_SDK_DIR}/src/connections/target/gpio.cpp"
    "${SOURCES_SDK_DIR}/src/connections/target/adsd3500_interrupt_notifier.cpp"
    "${SOURCES_SDK_DIR}/src/connections/target/adsd3500_mode_selector.cpp"
    "${SOURCES_SDK_DIR}/src/connections/target/sensor-tables/device_parameters.cpp"
    "${SOURCES_SDK_DIR}/src/connections/target/adsd3500_sensor.cpp"
    "${SOURCES_SDK_DIR}/src/connections/target/buffer_processor.cpp"
    "${SOURCES_SDK_DIR}/src/connections/offline/offline_depth_sensor.cpp"
    "${SOURCES_SDK_DIR}/src/connections/offline/offline_sensor_enumerator.cpp"
    "${SOURCES_SDK_DIR}/src/connections/network/network.cpp"
    "${SOURCES_SDK_DIR}/src/connections/network/network_sensor_enumerator.cpp"
    "${SOURCES_SDK_DIR}/src/connections/network/network_depth_sensor.cpp"
    "${SOURCES_SDK_DIR}/src/sensor_enumerator_factory.cpp"
    "${SOURCES_SDK_DIR}/src/utils.cpp"
    "${SOURCES_SDK_DIR}/src/system_impl.cpp"
    "${SOURCES_SDK_DIR}/src/platform/sensor_enumerator.cpp"
    "${SOURCES_SDK_DIR}/src/platform/raspberrypi/rpi_media_config.cpp"
    "${SOURCES_SDK_DIR}/src/platform/platform_impl.cpp"
    "${SOURCES_SDK_DIR}/src/status_definitions.cpp"
    "${SOURCES_SDK_DIR}/src/frame_operations.cpp"
    "${SOURCES_SDK_DIR}/src/frame.cpp"
    "${SOURCES_SDK_DIR}/src/utils_ini.cpp"
    "${SOURCES_SDK_DIR}/src/frame_handler.cpp"
    "${SOURCES_SDK_DIR}/src/cameras/itof-camera/camera_itof.cpp"
    "${SOURCES_SDK_DIR}/src/cameras/itof-frame/frame_impl.cpp"
    "${SOURCES_SDK_DIR}/src/cameras/itof-frame/frame_handler_impl.cpp"
    "${SOURCES_SDK_DIR}/src/system.cpp"
    "${SOURCES_SDK_DIR}/common/adi/tofi/opencv_undistort.cpp"
    "${SOURCES_SDK_DIR}/common/adi/tofi/algorithms.cpp"
    "${SOURCES_SDK_DIR}/common/adi/depth-compute-opensource/src/tofiConfig.cpp"
    "${SOURCES_SDK_DIR}/common/adi/depth-compute-opensource/src/tofiCompute.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/mainpage.dox"
)
string(REPLACE ";" " " DOCUMENTED_FILES "${DOCUMENTED_FILES_LIST}")

################# Generate Doxygen configuration file #########################
configure_file(
    sdk.doxy.in
    ${DOXY_WORKING_DIR}/sdk-api.doxy
)

################# Custom target to build Doxygen doc ##########################
add_custom_target(evalkit-doc ALL
    COMMAND ${DOXYGEN_PATH} sdk-api.doxy
    COMMAND ${CMAKE_COMMAND} -E make_directory ${DOXY_WORKING_DIR}/html
    COMMAND ${CMAKE_COMMAND} -E copy_directory ${CMAKE_CURRENT_SOURCE_DIR}/img ${DOXY_WORKING_DIR}/html/img
    WORKING_DIRECTORY ${DOXY_WORKING_DIR}
)

############### Install the documentation in the system #######################
include(GNUInstallDirs)
install(DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/doxygen_doc/html/ DESTINATION ${CMAKE_INSTALL_DOCDIR})
