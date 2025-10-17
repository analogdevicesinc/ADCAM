cmake_minimum_required(VERSION 3.10)

project(aditof-python-data_collect)

add_custom_command(OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/data_collect.py
                   COMMAND ${CMAKE_COMMAND} -E copy_if_different
                   ${CMAKE_CURRENT_SOURCE_DIR}/data_collect.py
                   ${CMAKE_CURRENT_BINARY_DIR}/data_collect.py
                   DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/data_collect.py
)

add_custom_target(copy_data_collect ALL 
                  DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/data_collect.py
)