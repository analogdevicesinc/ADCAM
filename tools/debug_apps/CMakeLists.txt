cmake_minimum_required(VERSION 3.0)
project(debug_apps)

######################### Target based Options ################################
option(RPI "Set to ON when building on RPI" OFF)
option(NVIDIA "Set to ON when building on NVIDIA" OFF)

# Add the device definition
if(RPI)
	add_definitions(-DRPI)
elseif(NVIDIA)
	add_definitions(-DNVIDIA)
endif()

add_subdirectory(ctrl_app)
