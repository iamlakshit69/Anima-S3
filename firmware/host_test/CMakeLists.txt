cmake_minimum_required(VERSION 3.16)
project(firmware_host_test CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include_directories(
    ../main
    ../main/net
    ../main/audio
    ../main/app
    ../main/sys
    ../main/ui
    ../main/boards
)

enable_testing()

# 1. Protocol frame framing test
add_executable(test_protocol_host test_protocol_host.cc)
add_test(NAME test_protocol_host COMMAND test_protocol_host)

# 2. Lock-free SPSC Ring buffer test
add_executable(test_ring_buffer_host test_ring_buffer_host.cc)
add_test(NAME test_ring_buffer_host COMMAND test_ring_buffer_host)

# 3. Jitter buffer test
add_executable(test_jitter_buffer_host test_jitter_buffer_host.cc ../main/audio/jitter_buffer.cc)
add_test(NAME test_jitter_buffer_host COMMAND test_jitter_buffer_host)

# 4. Button debouncer test
add_executable(test_buttons_host test_buttons_host.cc ../main/sys/buttons.cc)
add_test(NAME test_buttons_host COMMAND test_buttons_host)

# 5. Table-driven state machine test
add_executable(test_state_machine_host test_state_machine_host.cc ../main/app/state_machine.cc)
add_test(NAME test_state_machine_host COMMAND test_state_machine_host)

# 6. Diagnostics & self-test
add_executable(test_diag_host test_diag_host.cc ../main/sys/diag.cc)
add_test(NAME test_diag_host COMMAND test_diag_host)

# 7. Wake word detector test
add_executable(test_wake_word_host test_wake_word_host.cc ../main/audio/wake_word.cc)
add_test(NAME test_wake_word_host COMMAND test_wake_word_host)

# 8. Device tool registry & forbidden check
add_executable(test_tools_host test_tools_host.cc ../main/sys/tools.cc ../main/sys/settings.cc)
add_test(NAME test_tools_host COMMAND test_tools_host)

# 9. Settings, OTA manager, and auth error handling test
add_executable(test_settings_ota_host test_settings_ota_host.cc ../main/sys/settings.cc ../main/net/ota_manager.cc ../main/net/ws_client.cc)
add_test(NAME test_settings_ota_host COMMAND test_settings_ota_host)
