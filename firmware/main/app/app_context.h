/*
 * firmware/main/app/app_context.h — Abstract interface for application actions.
 */

#pragma once

#include <stdint.h>
#include <stddef.h>

class AppContext {
public:
    virtual ~AppContext() = default;

    virtual void start_turn(const char* reason) = 0;
    virtual void stop_uplink() = 0;
    virtual void send_listen_end() = 0;
    virtual void abort_turn() = 0;
    virtual void start_playback() = 0;
    virtual void finish_playback() = 0;
    virtual void barge_in() = 0;

    virtual void connect_wifi() = 0;
    virtual void connect_server() = 0;
    virtual void on_connected() = 0;
    virtual void on_disconnected() = 0;
    virtual void start_provisioning() = 0;
    virtual void start_ota() = 0;
    virtual void ota_done() = 0;
};

