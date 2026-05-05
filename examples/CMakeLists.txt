cmake_minimum_required(VERSION 3.10)
project(examples)

add_subdirectory(first-frame)
add_subdirectory(data_collect)
add_subdirectory(tof-viewer)
# adsd3500_sample_program requires proprietary ToFi libraries
if(ON_TARGET AND NOT USE_DEPTH_COMPUTE_OPENSOURCE)
    add_subdirectory(adsd3500_sample_program)
endif()

include(GNUInstallDirs)

install(PROGRAMS
    $<TARGET_FILE:first-frame>
    $<TARGET_FILE:data_collect>
    $<TARGET_FILE:ADIToFGUI>
    DESTINATION ${CMAKE_INSTALL_BINDIR} )

if(ON_TARGET AND NOT USE_DEPTH_COMPUTE_OPENSOURCE)
    install(PROGRAMS
        $<TARGET_FILE:adsd3500_sample_program>
        DESTINATION ${CMAKE_INSTALL_BINDIR} )
endif()
