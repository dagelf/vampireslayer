import QtQuick
import qs.Ui

BarWidget {
    id: root
    moduleName: "dagelf.vampireslayer"
    property var shell: null
    readonly property var service: shell ? shell.serviceFor(moduleName) : (bar && bar.shell ? bar.shell.serviceFor(moduleName) : null)
    readonly property string mode: service ? service.mode : "suspended"
    readonly property string label: !service || !service.initialized ? "Status unavailable" : mode === "gaming" ? "Gaming mode" : mode === "watching" ? "Slayer watching" : "Slayer suspended"
    readonly property string operation: !service || !service.initialized ? "Check the shell log; re-enable to reconnect." : mode === "gaming" ? "Selected background apps stay paused while you play." : mode === "watching" ? "Pause eligible apps after 15 minutes idle; resume on input." : "Automatic suspension is off; apps are resumed."
    implicitWidth: button.implicitWidth
    implicitHeight: barSize

    WidgetButton {
        id: button
        bar: root.bar
        hasVisualContent: true
        labelVisible: false
        fixedWidth: root.barSize
        fixedHeight: root.barSize
        dimmed: root.mode === "suspended"
        tooltipText: "Vampire Slayer — " + root.label + "\n" + root.operation
            + "\nClick: Watching → Gaming → Suspended"
            + "\nDouble-click or right-click: edit TOML"
            + "\nIgnore/media rules apply. Brought to you by dagelf."
            + (root.service && root.service.error ? "\n" + root.service.error : "")
        // WidgetButton registers with Omarchy's bar drag/click routing.
        // Delay a single click so a double-click never changes modes first.
        onPressed: function(buttonCode) {
            if (!root.service) return;
            if (buttonCode === Qt.RightButton) { click.stop(); root.service.editConfig(); }
            else if (buttonCode === Qt.LeftButton) {
                if (click.running) { click.stop(); root.service.editConfig(); }
                else click.start();
            }
        }
        // The bar forwards single clicks through WidgetButton, but propagates
        // composed double-clicks to the widget's MouseAreas. Accept that event
        // here so it does not reach the bar's transparency gesture beneath us.
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton
            propagateComposedEvents: true
            onClicked: function(mouse) { mouse.accepted = false; }
            onDoubleClicked: function(mouse) {
                click.stop();
                if (root.service) root.service.editConfig();
                mouse.accepted = true;
            }
        }
        PixelVampire {
            anchors.centerIn: parent
            width: Math.max(16, Math.floor((root.barSize - 8) / 16) * 16)
            height: width
            mode: root.mode
            iconStyle: root.service ? root.service.iconStyle : "nosferatu"
            colorful: root.setting("colorIcons", false)
            foreground: root.bar ? root.bar.foreground : "white"
            opacity: root.service && root.service.busy ? 0.5 : 1
        }
    }
    Timer {
        id: click
        interval: Qt.styleHints.mouseDoubleClickInterval
        onTriggered: if (root.service) root.service.cycle()
    }
}
