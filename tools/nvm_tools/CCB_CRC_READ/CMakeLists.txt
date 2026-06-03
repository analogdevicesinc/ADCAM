cmake_minimum_required(VERSION 3.10)
project(CCB_CRC_READ)

set(NVM_COMMON ../common)

include_directories(
    ${NVM_COMMON}
)

set(SOURCES
    ${NVM_COMMON}/v4l2_common.cpp
)

add_executable(${PROJECT_NAME} CCB_CRC_READ.cpp ${SOURCES})
