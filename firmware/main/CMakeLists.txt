# Main component CMakeLists.txt
idf_component_register(
    SRCS
        "net/protocol_gen.h"
    INCLUDE_DIRS
        "."
        "net"
    REQUIRES
        esp_websocket_client
        cjson
)
