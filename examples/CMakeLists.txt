cmake_minimum_required(VERSION 3.10)
project(examples)

add_subdirectory(first-frame)
add_subdirectory(data_collect)
add_subdirectory(tof-viewer)
add_subdirectory(adsd3500_sample_program)

include(GNUInstallDirs)

install(PROGRAMS
    $<TARGET_FILE:first-frame>
    $<TARGET_FILE:data_collect>
    $<TARGET_FILE:ADIToFGUI>
    $<TARGET_FILE:adsd3500_sample_program>
    DESTINATION ${CMAKE_INSTALL_BINDIR} )
