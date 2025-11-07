cmake_minimum_required(VERSION 3.0)
project(dependecies)

add_subdirectory(adi/command_parser)
if (WITH_EXAMPLES)
     #add_subdirectory(third-party/imgui2)
     add_subdirectory(third-party/imgui)
endif()
