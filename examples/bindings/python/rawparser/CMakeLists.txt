cmake_minimum_required(VERSION 3.10)

project(aditof-python-rawparser)

file(COPY "${CMAKE_CURRENT_SOURCE_DIR}/rawparser.py" DESTINATION "${CMAKE_CURRENT_BINARY_DIR}")

add_custom_command(OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/rawparser.py
                   COMMAND ${CMAKE_COMMAND} -E copy_if_different
                   ${CMAKE_CURRENT_SOURCE_DIR}/rawparser.py
                   ${CMAKE_CURRENT_BINARY_DIR}/rawparser.py
                   DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/rawparser.py
)

add_custom_target(copy_rawparser ALL 
                  DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/rawparser.py
)