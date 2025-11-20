cmake_minimum_required(VERSION 3.14)

# Ensure aditof (and optionally aditofpython) targets are defined before this file's copy logic.

function(PopulateforPython targetdir)
    add_subdirectory(${targetdir})
    file(GLOB PythonSources "${CMAKE_CURRENT_SOURCE_DIR}/${targetdir}/*.py")
endfunction()

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

foreach(ex ${PY_EXAMPLES})
    PopulateforPython("${ex}")
endforeach()

if (NOT WIN32)
    if (TARGET aditof AND TARGET aditofpython)
        add_custom_target(copy_so_to_python_examples ALL
            COMMENT "Copying aditofpython shared object to Python example directories (non-Windows)."
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
                COMMENT "Copied aditofpython to ${ex}"
            )
        endforeach()
    else()
        message(WARNING "Targets 'aditof' or 'aditofpython' not found for non-Windows copy step.")
    endif()
else()
    # Windows-only copy logic.
    # Most likely bindings live under: <binary>/libaditof/bindings/python/<CONFIG>
    # Change this to ${CMAKE_BINARY_DIR}/build/libaditof/bindings/python if you truly have a nested build directory.
    set(ADITOF_PY_BINDINGS_BASE "${CMAKE_BINARY_DIR}/libaditof/bindings/python")

    if (CMAKE_CONFIGURATION_TYPES)
        set(_ADITOF_PY_CFG "$<CONFIG>")
    else()
        if (NOT CMAKE_BUILD_TYPE)
            message(WARNING "CMAKE_BUILD_TYPE not set; defaulting to Release.")
            set(CMAKE_BUILD_TYPE "Release")
        endif()
        set(_ADITOF_PY_CFG "${CMAKE_BUILD_TYPE}")
    endif()

    set(ADITOF_PY_BINDINGS_DIR "${ADITOF_PY_BINDINGS_BASE}/${_ADITOF_PY_CFG}")

    if (TARGET aditof)
        add_custom_target(copy_runtime_to_examples ALL
            COMMENT "Copying aditof.dll and Python bindings (${_ADITOF_PY_CFG}) to Python example directories (Windows)."
        )
        add_dependencies(copy_runtime_to_examples aditof)

        # Optional: if a target producing the Python extension exists, depend on it too.
        if (TARGET aditofpython)
            add_dependencies(copy_runtime_to_examples aditofpython)
        endif()

        foreach(ex ${PY_EXAMPLES})
            # Single command per example for cleaner output
            add_custom_command(
                TARGET copy_runtime_to_examples
                COMMAND ${CMAKE_COMMAND} -E make_directory
                        "${CMAKE_CURRENT_BINARY_DIR}/${ex}"
                COMMAND ${CMAKE_COMMAND} -E copy_if_different
                        "$<TARGET_FILE:aditof>"
                        "${CMAKE_CURRENT_BINARY_DIR}/${ex}/aditof.dll"
                # Copy the entire configuration-specific bindings directory.
                COMMAND ${CMAKE_COMMAND} -E copy_directory
                        "${ADITOF_PY_BINDINGS_DIR}"
                        "${CMAKE_CURRENT_BINARY_DIR}/${ex}"
                COMMENT "Copied aditof.dll and Python bindings to ${ex}"
            )

            # ------------------------------------------------------------------
            # Alternative (copy only the built Python extension module) - UNCOMMENT IF NEEDED:
            # if (TARGET aditofpython)
            #     add_custom_command(
            #         TARGET copy_runtime_to_examples
            #         COMMAND ${CMAKE_COMMAND} -E copy_if_different
            #                 "$<TARGET_FILE:aditofpython>"
            #                 "${CMAKE_CURRENT_BINARY_DIR}/${ex}/"
            #         COMMENT "Copied aditofpython module to ${ex}"
            #     )
            # endif()
            # ------------------------------------------------------------------
        endforeach()
    else()
        message(WARNING "Target 'aditof' not found. Cannot copy runtime/bindings.")
    endif()
endif()