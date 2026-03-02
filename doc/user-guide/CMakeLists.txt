cmake_minimum_required(VERSION 3.0)

# Find the ADCAM-CameraKit markdown file (version-agnostic pattern)
file(GLOB ADCAM_SOURCE_MD "${CMAKE_CURRENT_SOURCE_DIR}/ADCAM-CameraKit-*.md")

if(NOT ADCAM_SOURCE_MD)
    message(WARNING "No ADCAM-CameraKit-*.md file found in ${CMAKE_CURRENT_SOURCE_DIR}")
else()
    list(GET ADCAM_SOURCE_MD 0 ADCAM_MD_FILE)
    get_filename_component(ADCAM_MD_NAME "${ADCAM_MD_FILE}" NAME)
    message(STATUS "Found ADCAM markdown source: ${ADCAM_MD_NAME}")

    # Output file
    set(TOF_VIEWER_MD "${CMAKE_CURRENT_SOURCE_DIR}/tof-viewer.md")
    
    # Extract script
    set(EXTRACT_SCRIPT "${CMAKE_CURRENT_SOURCE_DIR}/extract_gui_markdown.py")
    
    # Find Python3
    find_package(Python3 COMPONENTS Interpreter)
    
    if(Python3_FOUND)
        # Custom command to generate tof-viewer.md
        add_custom_command(
            OUTPUT "${TOF_VIEWER_MD}"
            COMMAND ${Python3_EXECUTABLE} ${EXTRACT_SCRIPT}
                    ${ADCAM_MD_FILE}
                    ${TOF_VIEWER_MD}
                    --skip-first 10
                    --drop-last 1
            DEPENDS ${ADCAM_MD_FILE} ${EXTRACT_SCRIPT}
            WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
            COMMENT "Generating tof-viewer.md from ${ADCAM_MD_NAME}"
        )
        
        # Custom target to ensure the file is generated
        add_custom_target(generate_tof_viewer_md ALL
            DEPENDS "${TOF_VIEWER_MD}"
        )
        
    else()
        message(WARNING "Python3 not found - tof-viewer.md will not be auto-generated")
    endif()
endif()
