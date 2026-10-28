import QtQuick
import Quickshell.Io

// Selected 16-pixel glyphs from the review gallery, monochrome by default.
Canvas {
    id: root
    property string mode: "watching"
    property string iconStyle: "nosferatu"
    property bool colorful: false
    property color foreground: "white"
    readonly property var sprites: JSON.parse(spriteFile.text() || "{}")
    readonly property var poses: sprites[iconStyle] || sprites.nosferatu || {}
    implicitWidth: 24
    implicitHeight: 24
    antialiasing: false
    onModeChanged: requestPaint()
    onPosesChanged: requestPaint()
    onColorfulChanged: requestPaint()
    onForegroundChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    FileView {
        id: spriteFile
        path: Qt.resolvedUrl("icons.json")
        blockLoading: true
    }
    onPaint: {
        const ctx = getContext("2d");
        ctx.clearRect(0, 0, width, height);
        const scale = Math.max(1, Math.floor(Math.min(width, height) / 16));
        const ox = Math.floor((width - 16 * scale) / 2);
        const oy = Math.floor((height - 16 * scale) / 2);
        const rows = poses[mode] || poses.watching;
        if (!rows) return;
        const palette = {H: "#b8a4e6", F: "#f3e5cf", C: "#cb4861", S: "#f3c66d"};
        for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) {
            const pixel = rows[y][x];
            if (pixel !== ".") {
                ctx.fillStyle = colorful ? palette[pixel] : foreground;
                ctx.fillRect(ox + x * scale, oy + y * scale, scale, scale);
            }
        }
    }
}
