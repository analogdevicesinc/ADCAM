cmake_minimum_required(VERSION 3.10)

project(aditof-python-dynamic_mode_switching)

file(COPY "${CMAKE_CURRENT_SOURCE_DIR}/dynamic_mode_switching.py" DESTINATION "${CMAKE_CURRENT_BINARY_DIR}")

add_custom_command(OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/dynamic_mode_switching.py
                   COMMAND ${CMAKE_COMMAND} -E copy_if_different
                   ${CMAKE_CURRENT_SOURCE_DIR}/dynamic_mode_switching.py
                   ${CMAKE_CURRENT_BINARY_DIR}/dynamic_mode_switching.py
                   DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/dynamic_mode_switching.py
)

add_custom_target(copy_dynamic_mode_switching ALL 
                  DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/dynamic_mode_switching.py
)