cmake_minimum_required(VERSION 3.0)
project(tools)

# Tools are currently only supported on NVIDIA and NXP platforms
# They require specific V4L2 controls and kernel interfaces
if (ON_TARGET AND (NVIDIA OR NXP))
    add_subdirectory(debug_apps)
    add_subdirectory(nvm_tools)
endif()

include(GNUInstallDirs)
