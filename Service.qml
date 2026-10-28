import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: root
    property var shell: null
    property var manifest: null
    readonly property string controller: decodeURIComponent(Qt.resolvedUrl("plugin-service").toString().replace(/^file:\/\//, ""))
    property string mode: "suspended"
    property string iconStyle: "nosferatu"
    property string activeState: "unknown"
    property string error: ""
    property bool initialized: false
    readonly property bool busy: control.running || activeState === "activating" || activeState === "deactivating"

    function setMode(next) {
        if (!["watching", "gaming", "suspended"].includes(next)) return "invalid mode";
        if (!initialized) return "status unavailable";
        if (busy) return "busy";
        error = "";
        control.command = ["/usr/bin/python3", controller, next];
        control.running = true;
        return "requested " + next;
    }
    function cycle() {
        return setMode(mode === "watching" ? "gaming" : mode === "gaming" ? "suspended" : "watching");
    }
    function editConfig() {
        if (!editor.running) { error = ""; editor.running = true; }
    }
    function acceptStatus(line) {
        try {
            const state = JSON.parse(line);
            if (!["watching", "gaming", "suspended"].includes(state.mode)) throw new Error("Invalid mode");
            mode = state.mode;
            iconStyle = typeof state.iconStyle === "string" ? state.iconStyle : "nosferatu";
            activeState = state.activeState;
            if (!initialized) {
                initialized = true;
                // Reconnect to an existing mode after a shell restart.
                if (activeState === "inactive" || activeState === "failed") setMode("watching");
            }
        } catch (e) { error = String(e); }
    }

    Process {
        id: observer
        command: ["/usr/bin/python3", root.controller, "observe"]
        running: true
        stdout: SplitParser { onRead: function(line) { root.acceptStatus(line); } }
        stderr: SplitParser { onRead: function(line) { root.error = line; } }
        onExited: {
            root.initialized = false;
            root.error = "Service status unavailable. Re-enable Vampire Slayer to reconnect.";
        }
    }
    Process {
        id: control
        stdout: SplitParser { onRead: function(line) { console.log("Vampire Slayer:", line); } }
        stderr: SplitParser { onRead: function(line) { console.warn("Vampire Slayer:", line); } }
        onExited: function(exitCode) {
            if (exitCode !== 0) root.error = "Mode change failed; see the shell log. Existing service state is shown.";
        }
    }
    Process {
        id: editor
        command: ["/usr/bin/python3", root.controller, "edit-config"]
        stderr: SplitParser { onRead: function(line) { console.warn("Vampire Slayer editor:", line); } }
        onExited: function(exitCode) {
            if (exitCode !== 0) root.error = "Editor launch failed; see the shell log.";
        }
    }
    IpcHandler {
        target: "dagelf.vampireslayer"
        function cycle(): string { return root.cycle(); }
        function gaming(): string { return root.setMode("gaming"); }
        function watching(): string { return root.setMode("watching"); }
        function suspended(): string { return root.setMode("suspended"); }
        function edit(): void { root.editConfig(); }
        function status(): string { return JSON.stringify({mode: root.mode, iconStyle: root.iconStyle, activeState: root.activeState, busy: root.busy, error: root.error}); }
    }
    Component.onDestruction: Quickshell.execDetached(["systemctl", "--user", "stop", "vampireslayer.service"])
}
