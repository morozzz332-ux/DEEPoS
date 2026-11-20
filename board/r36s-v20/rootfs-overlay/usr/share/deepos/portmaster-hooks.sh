#!/bin/bash
# Sourced by the upstream PortMaster launch script.
pm_hook_env() {
    source "$controlfolder/control.txt"
    get_controls
}

pm_hook_gui_env() {
    # SDL and the display are provided by run-port.sh.
    :
}

pm_hook_pre_launch() { :; }
pm_hook_post_launch() { :; }

pm_hook_run_pugwash() {
    ./pugwash $PORTMASTER_CMDS
    deepos_pm_status=$?
}

pm_hook_frontend_refresh() {
    return "${deepos_pm_status:-0}"
}
