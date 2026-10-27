# Validation

Tested 2026-10-27 against the running Omarchy/Hyprland desktop exposed by WayVNC on localhost:5900, plus isolated automated fixtures.

## Live Omarchy session

- Installed the service + bar-widget plugin through Omarchy's registry and enabled it.
- Confirmed the native Wayland idle connection in the systemd journal: `Watching display wayland:/run/user/1000/wayland-1`.
- Gaming immediately stopped a disposable Firefox-named process while a Chromium-named fixture exporting MPRIS `PlaybackStatus=Playing` continued running. This tests the exemption behavior; it is not a physical audio playback benchmark.
- Suspended resumed the stopped process and stopped the watcher. Watching restarted with a fresh idle interval.
- Clicked the actual bar icon to change modes. Double-click opened the personal TOML in Neovim without cycling or toggling bar transparency.
- Tested the documented Super+Alt+F12 mode shortcut and Super+Alt+V editor shortcut in Hyprland. Restored the original bindings file afterward.
- Tested optional color glyphs, then restored monochrome. The personal TOML was created without altering its defaults.
- Left the plugin enabled in Watching mode with systemd reporting active and the plugin status reporting no error. The host's separate idle service was not modified.

Live testing found and corrected two integration differences that an isolated component test missed: older Omarchy needs `IpcHandler` (also supported through the newer IPC fallback), and the bar forwards double-clicks as composed mouse events. The editor launcher now replaces its helper process so its lifetime and error reporting remain attached to the QML process.

## Automated checks

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_background_suspend test_wayland_idle test_plugin test_gaming
VAMPIRESLAYER_TEST_SYSTEMD=1 python3 -m unittest test_plugin
python3 tests/qml_smoke.py  # On Omarchy; fake backend, private D-Bus, offscreen window
omarchy plugin validate .
```

The full Python suite passed (35 tests, three wrapper-managed private-bus cases skipped in the outer process and run inside their private sessions). The opt-in systemd test verified normal-stop and forced-exit cleanup using a harmless waiting Python service. The QML smoke test passed mode cycling, single-click Gaming, and double-click editor dispatch without changing modes. After the final editor change, the 13 plugin/gaming tests and QML smoke test were rerun successfully; the live systemd check remains opt-in.

The editor test verifies exclusive first creation, file permissions, preserving an existing TOML, and use of Omarchy's default-editor launcher. Gaming fixtures test immediate suspension, Playing/Paused/unknown media transitions, ignore-list precedence, and resumption after monitor or signal failure. Existing tests cover process families, worker exits, PID reuse, X11/VNC separation, Wayland protocol events, and the Mutter fallback.

Qt 6 static lint found no syntax errors in the plugin. The available host linter reports metadata warnings when reading the guest's newer Quickshell type descriptions; real QML loading and interaction were therefore verified using the guest's Quickshell runtime and the live Omarchy shell.

Battery savings are workload-dependent and were not benchmarked. Optional foreground-only suspension is a roadmap item, not part of these checks.
