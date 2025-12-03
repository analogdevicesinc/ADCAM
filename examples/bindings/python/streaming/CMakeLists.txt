cmake_minimum_required(VERSION 3.10)

project(aditof-python-streaming)


add_custom_command(OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/depth-image-animation-pygame.py
                   COMMAND ${CMAKE_COMMAND} -E copy_if_different
                   ${CMAKE_CURRENT_SOURCE_DIR}/depth-image-animation-pygame.py
                   ${CMAKE_CURRENT_BINARY_DIR}/depth-image-animation-pygame.py
                   DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/depth-image-animation-pygame.py
)

add_custom_target(copy_depth_pygame ALL 
                  DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/depth-image-animation-pygame.py
) 