import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: root

    property var shell: null
    property var manifest: null
    readonly property string controller: decodeURIComponent(Qt.resolvedUrl("plugin-service").toString().replace(/^file:\/\//, ""))

    Process {
        command: ["/usr/bin/python3", root.controller, "start"]
        running: true
        stdout: SplitParser { onRead: function(line) { console.log("Vampireslayer:", line); } }
        stderr: SplitParser { onRead: function(line) { console.warn("Vampireslayer:", line); } }
        onExited: function(exitCode) {
            if (exitCode !== 0)
                console.warn("Vampireslayer did not start; inspect the message above and re-enable to retry.");
        }
    }

    // systemd owns the watcher and its resume cleanup, independently of QML.
    Component.onDestruction: Quickshell.execDetached(["systemctl", "--user", "stop", "vampireslayer.service"])
}
