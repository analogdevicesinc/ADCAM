cmake_minimum_required(VERSION 3.10)

project(aditof-python-first_frame)

file(COPY "${CMAKE_CURRENT_SOURCE_DIR}/first_frame.py" DESTINATION "${CMAKE_CURRENT_BINARY_DIR}")

add_custom_command(OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/first_frame.py
                   COMMAND ${CMAKE_COMMAND} -E copy_if_different
                   ${CMAKE_CURRENT_SOURCE_DIR}/first_frame.py
                   ${CMAKE_CURRENT_BINARY_DIR}/first_frame.py
                   DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/first_frame.py
)

add_custom_target(copy_first_frame ALL 
                  DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/first_frame.py
)