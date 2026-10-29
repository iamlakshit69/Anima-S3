#include "sys/tools.h"
#include "sys/settings.h"
#include <cassert>
#include <cstdio>
#include <cstring>

int main() {
    printf("[HOST_TEST] Running test_tools_host...\n");

    ToolDispatcher::init();

    // 1. Tool count & registry
    assert(ToolDispatcher::tool_count() == 4);
    assert(ToolDispatcher::find_tool("set_volume") != nullptr);
    assert(ToolDispatcher::find_tool("set_brightness") != nullptr);
    assert(ToolDispatcher::find_tool("lamp_set") != nullptr);
    assert(ToolDispatcher::find_tool("get_status") != nullptr);

    // Also supports "device." prefix
    assert(ToolDispatcher::find_tool("device.set_volume") != nullptr);

    // 2. set_volume
    ToolResult res = ToolDispatcher::dispatch("set_volume", "{\"level\": 45}");
    assert(res.ok == true);
    assert(strstr(res.payload, "\"volume\":45") != nullptr);
    assert(Settings::get().volume == 45);

    // Clamping > 100
    res = ToolDispatcher::dispatch("set_volume", "{\"level\": 150}");
    assert(res.ok == true);
    assert(strstr(res.payload, "\"volume\":100") != nullptr);
    assert(Settings::get().volume == 100);

    // Clamping < 0
    res = ToolDispatcher::dispatch("set_volume", "{\"level\": -25}");
    assert(res.ok == true);
    assert(strstr(res.payload, "\"volume\":0") != nullptr);
    assert(Settings::get().volume == 0);

    // Bad args
    res = ToolDispatcher::dispatch("set_volume", "{\"invalid\": 10}");
    assert(res.ok == false);
    assert(strcmp(res.error, "E_TOOL_BAD_ARGS") == 0);

    // 3. set_brightness
    res = ToolDispatcher::dispatch("set_brightness", "{\"level\": 85}");
    assert(res.ok == true);
    assert(strstr(res.payload, "\"brightness\":85") != nullptr);
    assert(Settings::get().brightness == 85);

    res = ToolDispatcher::dispatch("set_brightness", "{}");
    assert(res.ok == false);
    assert(strcmp(res.error, "E_TOOL_BAD_ARGS") == 0);

    // 4. lamp_set
    res = ToolDispatcher::dispatch("lamp_set", "{\"on\": true}");
    assert(res.ok == true);
    assert(strstr(res.payload, "\"on\":true") != nullptr);

    res = ToolDispatcher::dispatch("lamp_set", "{\"on\": false}");
    assert(res.ok == true);
    assert(strstr(res.payload, "\"on\":false") != nullptr);

    res = ToolDispatcher::dispatch("lamp_set", "{\"on\": 123}");
    assert(res.ok == false);
    assert(strcmp(res.error, "E_TOOL_BAD_ARGS") == 0);

    // 5. get_status
    res = ToolDispatcher::dispatch("get_status", "{}");
    assert(res.ok == true);
    assert(strstr(res.payload, "\"battery_pct\":100") != nullptr);

    // 6. Rule R7: Forbidden capabilities permanently denied
    assert(ToolDispatcher::is_forbidden("reboot"));
    assert(ToolDispatcher::is_forbidden("upgrade_firmware"));
    assert(ToolDispatcher::is_forbidden("wifi_credentials"));
    assert(ToolDispatcher::is_forbidden("factory_reset"));
    assert(ToolDispatcher::is_forbidden("set_token"));

    res = ToolDispatcher::dispatch("reboot", "{}");
    assert(res.ok == false);
    assert(strcmp(res.error, "E_TOOL_DENIED") == 0);

    res = ToolDispatcher::dispatch("upgrade_firmware", "{}");
    assert(res.ok == false);
    assert(strcmp(res.error, "E_TOOL_DENIED") == 0);

    res = ToolDispatcher::dispatch("wifi_set", "{}");
    assert(res.ok == false);
    assert(strcmp(res.error, "E_TOOL_DENIED") == 0);

    res = ToolDispatcher::dispatch("factory_reset", "{}");
    assert(res.ok == false);
    assert(strcmp(res.error, "E_TOOL_DENIED") == 0);

    res = ToolDispatcher::dispatch("set_token", "{}");
    assert(res.ok == false);
    assert(strcmp(res.error, "E_TOOL_DENIED") == 0);

    // 7. Unknown tool
    res = ToolDispatcher::dispatch("hack_device", "{}");
    assert(res.ok == false);
    assert(strcmp(res.error, "E_TOOL_DENIED") == 0);

    printf("[HOST_TEST] test_tools_host passed!\n");
    return 0;
}

