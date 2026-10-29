/*
 * firmware/main/sys/tools.h — Device-side tool registry and execution engine.
 * Architecture Section 7.8 and Rules R7 & R8.
 */

#pragma once

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

enum class ToolRisk {
    SAFE = 0,
    CONFIRM = 1
};

struct ToolResult {
    bool ok;
    char payload[256];
    char error[64];
};

typedef ToolResult (*ToolFn)(const char* args_json);

struct Tool {
    const char* name;
    const char* desc;
    const char* params_schema;
    ToolRisk risk;
    ToolFn fn;
};

class ToolDispatcher {
public:
    static void init();

    /**
     * @brief Dispatches a tool call from the server.
     * @param tool_name Name of the tool (e.g. "set_volume", "lamp_set")
     * @param args_json JSON string of arguments
     * @return ToolResult indicating success/payload or error
     */
    static ToolResult dispatch(const char* tool_name, const char* args_json);

    /**
     * @brief Checks if a tool name is strictly forbidden per Rule R7.
     */
    static bool is_forbidden(const char* tool_name);

    /**
     * @brief Looks up a registered tool by name.
     */
    static const Tool* find_tool(const char* tool_name);

    static size_t tool_count();
    static const Tool* get_tools();

    // Individual tool handlers
    static ToolResult tool_set_volume(const char* args_json);
    static ToolResult tool_set_brightness(const char* args_json);
    static ToolResult tool_lamp_set(const char* args_json);
    static ToolResult tool_get_status(const char* args_json);
};

