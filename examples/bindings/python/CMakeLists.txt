cmake_minimum_required(VERSION 3.0)

function(PopulateforPython targetdir)
    add_subdirectory(${targetdir})
    
    file(GLOB PythonSources "${CMAKE_CURRENT_SOURCE_DIR}/${targetdir}/*.py")
    
endfunction()

if (WITH_EXAMPLES)
    PopulateforPython("dnn")
    PopulateforPython("first_frame")
    PopulateforPython("gesture_rec")
    PopulateforPython("streaming")
    PopulateforPython("skeletal_tracking")
    PopulateforPython("skeletal_tracking_in_pointcloud")
    PopulateforPython("deprecated/saveCCBToFile")
    PopulateforPython("data_collect")
    PopulateforPython("showPointCloud")

endif()

if(NOT WIN32)
        install(CODE "execute_process(WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR} COMMAND ${PYTHON_EXECUTABLE} setup.py install --prefix=${CMAKE_INSTALL_PREFIX})")
endif()
