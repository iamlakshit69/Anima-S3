cmake_minimum_required(VERSION 3.16)
project(firmware_host_test CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include_directories(
    ../main
    ../main/net
)

enable_testing()

add_executable(test_protocol_host test_protocol_host.cc)
add_test(NAME test_protocol_host COMMAND test_protocol_host)
