# Omarchy marketplace submission

Repository URL: https://github.com/dagelf/vampireslayer

Category: System

Tags: Power management, Hyprland, System

## Listing copy

**Vampire Slayer: background browser and app idle suspend**

Chrome or Firefox eating CPU while you're out for lunch, even when they have
nothing to do? Vampire Slayer to the rescue.

Pause CPU-hungry background browsers and Electron apps when you walk away; resume
them when you return. Keep detected media playing, choose an ignore list, or
suspend even with media. Optional background-worker exceptions preserve jobs you
want to keep running. Works with Omarchy/Hyprland, compatible Wayland compositors,
GNOME/Mutter, and X11/VNC. Uses event notifications and systemd user-service cleanup.

Also see the graphic equalizer and audio pause/cycle hotkeys linked in the README.

## Maintainer notes

- Headless service plugin; one entry point, no second Quickshell process.
- Starts a transient systemd user unit; disables cleanly and uses ExecStopPost to resume apps.
- Requires systemd, Python 3.11+, python-dbus, python-gobject; xorg-xinput/coreutils only for X11/VNC.
- Uses the compositor's libwayland-client on Wayland; no privileged input-device access.
- MIT license; no preview assets or external artwork.
- Does not overwrite user configuration, install packages, or run sudo.
- Detection limits and v1 compositor inhibitors are documented.
- Tested with private Wayland/Mutter/MPRIS fixtures and disposable app processes; manifest validation and QML lint pass. Live Omarchy shell activation has not been tested in this X11 session.
- A disposable systemd service verifies normal-stop and forced-exit cleanup.

Submit using https://github.com/omacom/omarchy-plugin-marketplace/issues/new?template=submit-plugin.yml
after the public repository is reachable. Marketplace approval is a separate maintainer action.
