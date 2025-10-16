cmake_minimum_required(VERSION 3.10)

project(aditof-python-skeletal-tracking)


add_custom_command(OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/skeletal_tracking_in_pointcloud.py
                   COMMAND ${CMAKE_COMMAND} -E copy_if_different
                   ${CMAKE_CURRENT_SOURCE_DIR}/skeletal_tracking_in_pointcloud.py
                   ${CMAKE_CURRENT_BINARY_DIR}/skeletal_tracking_in_pointcloud.py
                   DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/skeletal_tracking_in_pointcloud.py
)

add_custom_target(copy_skeletal_tracking_in_pointcloud ALL 
                  DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/skeletal_tracking_in_pointcloud.py
) 