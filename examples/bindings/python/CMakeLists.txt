cmake_minimum_required(VERSION 3.14)

# IMPORTANT: Ensure the aditof target (which builds aditof.dll) is defined
# BEFORE this copying logic runs. For example:
# add_subdirectory(libaditof/sdk)  # (Adjust path to where aditof target is defined)

function(PopulateforPython targetdir)
    add_subdirectory(${targetdir})
    # Optional: collect Python sources if you want to use them later
    file(GLOB PythonSources "${CMAKE_CURRENT_SOURCE_DIR}/${targetdir}/*.py")
endfunction()

# List of Python example directories (relative to this CMakeLists.txt)
set(PY_EXAMPLES
    dnn
    first_frame
    gesture_rec
    streaming
    skeletal_tracking
    skeletal_tracking_in_pointcloud
    data_collect
    showPointCloud
)

# Unconditionally add all example subdirectories
foreach(ex ${PY_EXAMPLES})
    PopulateforPython("${ex}")
endforeach()

# Copy .so files to each Python example directory
if (NOT WIN32)
    if (TARGET aditof AND TARGET aditofpython)
        # Single aggregate target that depends on both libraries
        add_custom_target(copy_so_to_python_examples ALL
            COMMENT "Copying aditof.so and aditofpython.so to Python example directories."
        )
        add_dependencies(copy_so_to_python_examples aditof aditofpython)

        foreach(ex ${PY_EXAMPLES})
            add_custom_command(
                TARGET copy_so_to_python_examples
                COMMAND ${CMAKE_COMMAND} -E make_directory
                        "${CMAKE_CURRENT_BINARY_DIR}/${ex}"
                COMMAND ${CMAKE_COMMAND} -E copy_if_different
                        "$<TARGET_FILE:aditofpython>"
                        "${CMAKE_CURRENT_BINARY_DIR}/${ex}/"
                COMMENT "Copied aditof.so and aditofpython.so to ${ex}"
            )
        endforeach()
    else()
        message(WARNING
            "Targets 'aditof' or 'aditofpython' not found. Define them before this point.")
    endif()
else()
    # Windows: copy aditof.dll (per configuration) into each example's build dir.
    if (TARGET aditof)
        # Single aggregate target that depends on 'aditof' and performs all copies.
        add_custom_target(copy_dll_to_examples ALL
            COMMENT "Copying aditof.dll to Python example directories (Windows)."
        )
        add_dependencies(copy_dll_to_examples aditof)

        foreach(ex ${PY_EXAMPLES})
            add_custom_command(
                TARGET copy_dll_to_examples
                COMMAND ${CMAKE_COMMAND} -E make_directory
                        "${CMAKE_CURRENT_BINARY_DIR}/${ex}"
                COMMAND ${CMAKE_COMMAND} -E copy_if_different
                        "$<TARGET_FILE:aditof>"
                        "${CMAKE_CURRENT_BINARY_DIR}/${ex}/aditof.dll"
                COMMENT "Copied aditof.dll to ${ex}"
            )
        endforeach()
    else()
        message(WARNING
            "Target 'aditof' not found. Define it before this point or add a fallback path.")
    endif()
endif()

# (Optional) Previous non-Windows Python install step removed since you stated Windows-only need.
# If you still need install logic for other platforms, re-add it here.
