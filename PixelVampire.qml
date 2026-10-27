import QtQuick

// Original 16-pixel glyph. Palette changes never change the state silhouette.
Canvas {
    id: root
    property string mode: "watching"
    property bool colorful: false
    property color foreground: "white"
    implicitWidth: 24
    implicitHeight: 24
    antialiasing: false
    onModeChanged: requestPaint()
    onColorfulChanged: requestPaint()
    onForegroundChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        const ctx = getContext("2d");
        ctx.clearRect(0, 0, width, height);
        const scale = Math.max(1, Math.floor(Math.min(width, height) / 16));
        const ox = Math.floor((width - 16 * scale) / 2);
        const oy = Math.floor((height - 16 * scale) / 2);
        const rows = [
            "................", ".....HHHHHH.....", "....HH.HH.HH....",
            "....HFFFFFFH....", "....FF.FF.FF....", "....FFFFFFFF....",
            ".....F.FF.F.....", "..C...FFFF...C..", "..CC...FF...CC..",
            "...CC.CCCC.CC...", "...CCCCCCCCCC...", "..CCCCCCCCCCCC..",
            ".CCCCCCCCCCCCCC.", "...CCC.CC.CCC...", ".....CC..CC.....", "................"
        ];
        if (mode === "suspended") {
            rows[4] = "....F..FF..F....";
            rows[9] = ".....CCCCCC.....";
            rows[10] = ".....CCCCCC.....";
            rows[11] = "....CCCCCCCC....";
            rows[12] = "....CCCCCCCC....";
        } else if (mode === "gaming") {
            rows[2] = "....HHHHHHHH....";
            rows[4] = "....F.FFFF.F....";
            rows[8] = "..CC...FF...CC.S";
            rows[9] = "...CC.CCCC.CC.SS";
            rows[10] = "...CCCCCCCCCC.S.";
            rows[11] = "..CCCCCCCCCCSSS.";
        }
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
