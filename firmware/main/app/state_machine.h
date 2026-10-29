/*
 * firmware/main/app/state_machine.h — Table-driven state machine (Architecture section 7.5).
 */

#pragma once

#include <stddef.h>
#include "app/events.h"
#include "app/app_context.h"
#include "ui/ui.h"

typedef void (*ActionFn)(AppContext& ctx, const Event& event);

struct Transition {
    DeviceState from;
    EventType event;
    DeviceState to;
    ActionFn action;
};

class StateMachine {
public:
    StateMachine();

    /**
     * @brief Looks up a transition matching (current_state, event.type).
     * @return Pointer to transition if found, nullptr otherwise.
     */
    const Transition* find_transition(DeviceState from, EventType event) const;

    size_t transition_count() const;
    const Transition* get_transitions() const;
};
