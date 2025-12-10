cmake_minimum_required(VERSION 2.8)
project(discovery_server)

add_executable(${PROJECT_NAME} main.cpp)

target_link_libraries(${PROJECT_NAME} PRIVATE network_discovery)

set_target_properties(${PROJECT_NAME} PROPERTIES CXX_STANDARD 14)

# Copy service files to build directory
configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/discovery-server.service
    ${CMAKE_CURRENT_BINARY_DIR}/discovery-server.service
    COPYONLY
)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/config.json
    ${CMAKE_CURRENT_BINARY_DIR}/config.json
    COPYONLY
)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/install-service.sh
    ${CMAKE_CURRENT_BINARY_DIR}/install-service.sh
    COPYONLY
)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/uninstall-service.sh
    ${CMAKE_CURRENT_BINARY_DIR}/uninstall-service.sh
    COPYONLY
)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/README.md
    ${CMAKE_CURRENT_BINARY_DIR}/README.md
    COPYONLY
)

# Make scripts executable
if(UNIX)
    add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
        COMMAND chmod +x ${CMAKE_CURRENT_BINARY_DIR}/install-service.sh
        COMMAND chmod +x ${CMAKE_CURRENT_BINARY_DIR}/uninstall-service.sh
        COMMENT "Making service scripts executable"
    )
endif()
