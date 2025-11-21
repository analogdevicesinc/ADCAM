cmake_minimum_required(VERSION 3.0)
project(examples)

add_subdirectory(first-frame)
add_subdirectory(data_collect)
add_subdirectory(tof-viewer)

include(GNUInstallDirs)

install(PROGRAMS
    $<TARGET_FILE:first-frame>
    $<TARGET_FILE:data_collect>
    $<TARGET_FILE:ADIToFGUI>
    DESTINATION ${CMAKE_INSTALL_BINDIR} )
