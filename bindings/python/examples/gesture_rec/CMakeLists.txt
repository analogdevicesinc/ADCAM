cmake_minimum_required(VERSION 3.10)

project(aditof-python-gesture_rec)

set(FILES_TO_COPY
    process.py
    notebook.py
)

foreach(file ${FILES_TO_COPY})
    add_custom_command(OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/${file}
                   COMMAND ${CMAKE_COMMAND} -E copy_if_different
                           ${CMAKE_CURRENT_SOURCE_DIR}/${file}
                           ${CMAKE_CURRENT_BINARY_DIR}/${file}
                   DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/${file}
    )
endforeach()



add_custom_target(copy_gesture_rec ALL 
                  DEPENDS 
                        ${CMAKE_CURRENT_BINARY_DIR}/process.py
                        ${CMAKE_CURRENT_BINARY_DIR}/notebook.py
)  