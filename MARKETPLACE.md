# Omarchy marketplace submission

Repository URL: https://github.com/dagelf/vampireslayer

Category: System

Tags: Power management, Hyprland, System

Preview: `preview.png` (original pixel-art promotional banner)

## Listing copy

**Vampire Slayer: background browser and app idle suspend**

Chrome or Firefox eating CPU while you're out for lunch, even when they have
nothing to do? Vampire Slayer to the rescue.

Pause CPU-hungry background browsers and Electron apps when you walk away; resume
them when you return. Keep detected media playing, choose an ignore list, or
suspend even with media. Optional background-worker exceptions preserve jobs you
want to keep running. Works with Omarchy/Hyprland, compatible Wayland compositors,
GNOME/Mutter, and X11/VNC. Uses event notifications and systemd user-service cleanup.

Reduce background CPU work to save power and help extend battery life, even
while watching media. Detected audio/video keeps playing by default, and allowed
apps on your ignore list continue running.

Click the vampire to cycle Slayer watching, Gaming mode, and Slayer suspended.
Gaming immediately suspends eligible background app families; double-click opens
your TOML in the default editor. Monochrome pixel glyphs by default, optional color,
and documented Hyprland hotkeys through Omarchy IPC. Brought to you by dagelf.

Also see the graphic equalizer and audio pause/cycle hotkeys linked in the README.

## Maintainer notes

- Bar widget plus singleton service; no second Quickshell process.
- Widget uses Omarchy click/drag routing and capability-scoped own-service lookup.
- Namespaced IPC exposes cycle, gaming, watching, suspended, edit and status.
- Editor uses omarchy-launch-editor; user config is created exclusively, never overwritten.
- Starts a transient systemd user unit; disables cleanly and uses ExecStopPost to resume apps.
- Requires systemd, Python 3.11+, python-dbus, python-gobject; xorg-xinput/coreutils only for X11/VNC.
- Uses the compositor's libwayland-client on Wayland; no privileged input-device access.
- MIT license; original generated preview.png and hand-authored monochrome pixel glyphs.
- Does not overwrite user configuration, install packages, or run sudo.
- Tested with private Wayland/Mutter/MPRIS fixtures and disposable app processes; manifest validation and QML lint pass. Live Omarchy/Hyprland activation, Gaming/media behavior, and editor gestures were tested through WayVNC; see VALIDATION.md.
- A disposable systemd service verifies normal-stop and forced-exit cleanup.

Submission: https://github.com/omacom/omarchy-plugin-marketplace/issues/13061
