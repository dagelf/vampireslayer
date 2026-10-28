<p align="center">
  <img src="preview.png" alt="Vampire Slayer — pixel-art vampire castle, hunter sneaking up on a vampire secretly working at a computer" width="960">
</p>

# Vampire Slayer: background browser and app idle suspend

**Brought to you by [dagelf](https://github.com/dagelf).**

[Install](#install-on-omarchy) · [Modes](#one-vampire-three-modes) · [Hotkeys](#hyprland-hotkeys) · [Configuration](#your-policy-preserved-across-plugin-updates)

**Chrome or Firefox eating CPU while you're out for lunch, even when they have nothing to do? Vampire Slayer to the rescue.**

Put background browsers and apps on pause when you walk away. Vampire Slayer
suspends idle Chrome, Chromium, Firefox, Opera, Brave, and Electron app families,
then resumes them when you return to the keyboard or mouse. Your tabs and windows
stay open; unnecessary background CPU work stops while the apps are suspended.

**Less background CPU work. More battery for what you actually want to do.**
Pausing idle apps can reduce power consumption and help extend laptop battery life,
including while you watch a film or listen to music. **Detected audio/video keeps
playing by default, and allowed apps on your ignore list keep running.** Gaming
mode can pause the other eligible apps immediately while your media continues.
Media exemptions follow actual MPRIS `Playing` status.

An **Omarchy plugin for Hyprland**, with automatic Wayland and X11/VNC support.
Keep detected music and video playing, choose an ignore list for apps that must
stay awake, or suspend even with media. Optional background-worker exceptions
let you preserve builds and other jobs; they are off by default. No polling loop,
no browser extension, and no second Quickshell instance.

## One vampire, three modes

Click the vampire in your bar to cycle **Watching → Gaming → Suspended → Watching**.
The default monochrome **Nosferatu** glyph changes pose with the mode and follows your bar's theme.
Hover for the current state, what it does, and the next action.

| Mode | What happens |
| --- | --- |
| **Slayer watching** | Automatically suspend eligible app families after 15 minutes without input on their desktop; resume when you return. |
| **Gaming mode** | **Suspend all eligible background app families immediately**, without waiting for idle. Keep them paused while you use the keyboard and mouse to play. |
| **Slayer suspended** | Resume the apps and turn automatic suspension off. The vampire stays in the bar, ready to wake up. |

Gaming follows your browser/Electron suspend list and Electron detection across
your displays. Ignore rules always win; playing-media exemptions and optional
worker exceptions keep the apps you choose running. Set `suspend_media = ["*"]` in your
TOML if you also want media apps paused. Gaming evaluates apps when entered and when media changes.

Leaving Gaming resumes apps before entering the next mode. Returning to Watching
starts a fresh idle interval. The icon follows the service’s actual state.
Click again after editing your policy to re-enter an active mode and apply it.

**Double-click or right-click the vampire to edit your TOML.** A double-click opens
the editor without switching modes. Single-click waits for the desktop's
double-click interval; a hotkey mode change is immediate. Omarchy's selected editor
opens, defaulting to Neovim in a terminal. The first edit creates a personal copy;
existing settings are never overwritten.

Choose a sprite in `~/.config/vampireslayer/background-suspend.toml`:

```toml
icon_style = "nosferatu"
```

| Gallery option | `icon_style` | Design |
| --- | --- | --- |
| 02 (default) | `nosferatu` | Nosferatu |
| 03 | `widows-peak` | Widow’s Peak |
| 08 | `crescent-bat` | Crescent Bat |
| 18 | `sleeping-screen` | Sleeping Screen |
| 19 | `night-candle` | Night Candle |
| 20 | `fanged-skull` | Fanged Skull |

Save and cycle the mode to apply the icon setting. Existing configs without this
key use Nosferatu. All six designs have Watching, Gaming and Suspended poses.
The [icon review gallery](docs/icon-review.html) shows the numbered designs.

Color sprites are optional, using Omarchy's standard widget setting:

```sh
omarchy bar set dagelf.vampireslayer colorIcons true --json
# Return to theme-colored monochrome glyphs:
omarchy bar set dagelf.vampireslayer colorIcons false --json
```

<details>
<summary>See Vampire Slayer running in Omarchy</summary>

![Monochrome Vampire Slayer icon and Watching tooltip in the live Omarchy desktop](docs/omarchy-watching.png)

</details>

## Hyprland hotkeys

Following [Omarchy's plugin IPC convention](https://github.com/omacom/omarchy/blob/quattro/docs/omarchy-shell.md#ipc),
mouse actions and shortcuts call the same service. Add these bindings to `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + ALT + V", "Vampire Slayer: edit TOML", "omarchy-shell dagelf.vampireslayer edit")
o.bind("SUPER + ALT + F12", "Vampire Slayer: cycle mode", "omarchy-shell dagelf.vampireslayer cycle")
```

**Super+Alt+V** opens your TOML; **Super+Alt+F12** cycles modes. These leave
Omarchy’s Super+V paste and Super+Ctrl+V clipboard shortcuts in place. List your
bindings with `omarchy menu keybindings --print`.

For Hyprland installations still using `.conf` bindings:

```ini
bind = SUPER ALT, V, exec, omarchy-shell dagelf.vampireslayer edit
bind = SUPER ALT, F12, exec, omarchy-shell dagelf.vampireslayer cycle
```

Direct actions can be bound to any keys you prefer:

```sh
omarchy-shell dagelf.vampireslayer gaming
omarchy-shell dagelf.vampireslayer watching
omarchy-shell dagelf.vampireslayer suspended
omarchy-shell dagelf.vampireslayer status
omarchy-shell dagelf.vampireslayer edit
```

Mode requests return `requested …`, `busy`, or an error; `status` reports the
observed state. Commands require the plugin to be enabled in the running shell.
The widget shares one service across monitors in Omarchy’s built-in bar.

Vampire Slayer is the plugin name; `background-suspend` remains the standalone CLI.

## Install on Omarchy

Requires Omarchy Quattro's plugin system, systemd user services, Python 3.11+,
`python-dbus`, and `python-gobject` on Arch. Hyprland already provides the Wayland
client library. X11/VNC watching additionally uses `xorg-xinput` and `coreutils`.
Install the dependencies with your package manager.

```sh
omarchy plugin add https://github.com/dagelf/vampireslayer
omarchy plugin enable dagelf.vampireslayer
```

Omarchy loads the bar widget and `Service.qml` inside its existing shell. It starts the backend with
`systemd-run --user` as **vampireslayer.service**, including an `ExecStopPost` resume
command. Systemd handles shutdown, resumes apps, and collects the unit when stopped.
The plugin passes only desktop-session environment variables to its unit. A small
D-Bus observer reports unit changes to the icon without polling or a status timer.

The existing standalone `background-suspend.service` remains available for people
who prefer a permanently installed systemd user service. Choose the plugin or the
standalone service. For an existing Firefox-only install, follow
[Upgrading from firefox-idle](#upgrading-from-firefox-idle) first.

```sh
systemctl --user status vampireslayer.service
journalctl --user -u vampireslayer.service
omarchy plugin disable dagelf.vampireslayer
systemctl --user stop vampireslayer.service  # Wait for cleanup before deleting files
omarchy plugin remove dagelf.vampireslayer
```

Disabling stops the unit and resumes apps. Run the commands above in order to
finish cleanup before removing the checkout. The systemd-managed watcher keeps
reacting to activity independently of the shell. `ExecStopPost` resumes apps when
the backend exits.

The service entry is kept across ordinary QML hot reloads. After updating QML code,
run `omarchy-restart-shell` so cached components are replaced. For policy changes,
reselect Watching or Gaming, or restart `vampireslayer.service`.

## Your policy, preserved across plugin updates

Double-click the vampire or use the editor hotkey above. Defaults ship in
`background-suspend.toml`. You can also create a user copy manually; an existing file is never overwritten by this command:

```sh
mkdir -p ~/.config/vampireslayer
cp -n ~/.config/omarchy/plugins/dagelf.vampireslayer/background-suspend.toml ~/.config/vampireslayer/
```

Edit `~/.config/vampireslayer/background-suspend.toml`, then reselect an active mode or restart the service.
`XDG_CONFIG_HOME` is respected. Both plugin and CLI prefer this user copy when it
exists; an explicit `--config` selects a different file. Uninstalling the plugin
preserves your policy.

## Related Linux desktop tools

- [Graphic equalizer / PipeWire web EQ](https://github.com/dagelf/eq): a ten-band
  stereo graphic equalizer, preamp, presets, per-output settings, application
  mixer, and MPRIS media controls. Native C processing/control with a browser UI.
- [Audio pause/cycle hotkeys](https://github.com/dagelf/media-hotkeys): pause all
  audio players, cycle one MPRIS source at a time, and return to silence. Includes
  Hyprland/Omarchy and IceWM keyboard shortcut examples.
- [Linux CLI utilities](https://github.com/dagelf/utils): the original home of the
  media-cycle hotkey and other small desktop tools.

Search terms: Vampire Slayer, vampireslayer, background browser and app idle
suspend, Chrome CPU, Chromium CPU, Firefox CPU, Electron CPU, out for lunch,
Omarchy plugin, Hyprland, Wayland, X11, VNC, power management, Gaming mode, Hyprland hotkeys, pixel art, graphic equalizer,
PipeWire, audio pause, audio cycle, media hotkeys.

## Suspension behavior

Suspend browser and Electron process families after 15 minutes without real input
on their X11/VNC display or Wayland session. Activity resumes that session’s apps.
Each desktop has its own idle state; all apps on an active desktop stay awake. XTEST-generated input is ignored on
X11; on Wayland, the compositor decides which activity resets its idle counter.

## Desktop detection

No backend setting is needed. If `WAYLAND_DISPLAY` is set, connect to that socket
and detect the available API:

- **Hyprland, Sway, KDE, and other supporting compositors:** use
  [`ext-idle-notify`](https://gitlab.freedesktop.org/wayland/wayland-protocols/-/blob/main/staging/ext-idle-notify/ext-idle-notify-v1.xml)
  through the system `libwayland-client.so.0`. No additional daemon, package,
  build step, raw input access, or polling is needed.
- **GNOME/Mutter:** when the protocol is absent, use its
  [IdleMonitor D-Bus API](https://github.com/GNOME/mutter/blob/main/data/dbus-interfaces/org.gnome.Mutter.IdleMonitor.xml).
  Verify that the service belongs to the connected compositor before using it.
- **X11/VNC:** retain XInput watching on each independent X server. The current
  Wayland session's XWayland display is excluded from XInput watching, so native
  and XWayland apps share one authoritative idle state.

Native Wayland apps no longer need `DISPLAY`. Other VNC displays remain independent.
The exported `WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR`, and `DISPLAY` identify the current
Wayland session and its XWayland server. Launch independent X11/VNC sessions with
`WAYLAND_DISPLAY` unset so they do not inherit the host session's identity.

Version 2 of the Wayland protocol supplies input-only idle notifications, allowing
our per-app media policy to work independently of compositor idle inhibitors.
Version 1 follows compositor idle inhibitors. Apps resume when the idle connection
ends; restart the watcher after restoring the session.

## Defaults and exceptions

Use [`background-suspend.toml`](background-suspend.toml) as the policy reference. Restart the watcher after
editing your user policy. Patterns are case-insensitive shell globs, not regular expressions.

| Setting | Default and meaning |
| --- | --- |
| `suspend` | Firefox, Chromium, Chrome, Opera, Brave, other browser variants, common Electron apps and editors, Electron and NW.js runtimes. Matches executable basenames. |
| `detect_electron` | `true`: also recognize renamed executables with adjacent `resources/app.asar` or `resources/electron.asar`. |
| `ignore` | `[]`: never suspend matching app families. A matching executable anywhere in the family exempts the whole family. Takes precedence over other options. |
| `suspend_media` | `[]`: keep every app with detected playing media awake. List app-root executable patterns to suspend them even with media; `["*"]` disables media exemptions entirely. |
| `worker_exceptions` | `false`: opt in to preserving apps with matching background workers. |
| `background_workers` | Configurable process/argument-token patterns for Node, builds, language servers, explicit worker scripts, transfers, and headless jobs. Used only when worker exceptions are enabled. |

App roots need a `DISPLAY` or `WAYLAND_DISPLAY`; all their owned descendant processes follow their
policy, including helpers without either variable. To include standalone
Node/Bun/Deno servers, add their executable names to `suspend`. The controller's own ancestor family is always protected.

Media detection listens to **all** registered MPRIS players and maps their PIDs
back to app families, including players hosted in helper processes. Only
[`PlaybackStatus = Playing`](https://specifications.freedesktop.org/mpris/latest/Player_Interface.html)
grants an exemption. Paused and stopped players follow the idle policy. Use an
ignore rule for calls or WebAudio apps that keep their playback outside MPRIS.
Apps resume while media status is being resolved and when the monitor exits.
When media exemptions are disabled globally, no media monitor is required.

Worker exceptions keep an **entire app family** awake while a matching worker
exists. Worker exits trigger an immediate recheck using pidfds. Use app ignore
rules for browser service workers and worker threads inside renderers.

## Commands

Requires Linux pidfds and Python 3.11+. X11 watching uses `xinput` and `stdbuf`;
Wayland watching uses the compositor's existing `libwayland-client`. Media
monitoring and the Mutter fallback use `python3-dbus` and `python3-gi`.
Only the needed backend is started. No browser extension or remote-debugging port is required.

```sh
./background-suspend list                         # Read-only app/decision preview
./background-suspend run                          # Default policy, 15-minute idle time
./background-suspend run --ignore code             # Extra ignore rule for this run
./background-suspend run --suspend-media            # Suspend even with playing media
./background-suspend run --suspend-media 'chrome*'  # Override media for selected roots
./background-suspend run --worker-exceptions       # Opt in to worker exceptions
./background-suspend run --config ./custom.toml    # Alternative policy
./background-suspend resume                       # Resume configured app families
```

`list` previews the policy decisions for each app family. The ignore list always wins, including in `gaming` mode.

The service controls are `start`, `stop`, `status`, and `gaming`. `gaming` stops
automatic watching and immediately suspends eligible apps, respecting media and
worker exceptions. Use `gaming --suspend-media` to override media, and `start` to
return to automatic mode. The standalone `gaming` command takes a one-time media/worker snapshot.
The Omarchy plugin’s Gaming mode keeps following media events. Put persistent
policy in the TOML file for systemd service runs.

## Standalone Arch installation

The same tooling runs directly on Arch with X11/VNC or Wayland. Install the
runtime dependencies, clone this repository, and enable the user service:

```sh
sudo pacman -S --needed python python-dbus python-gobject
git clone https://github.com/dagelf/vampireslayer ~/vampireslayer
cd ~/vampireslayer
# For X11/VNC sessions:
sudo pacman -S --needed xorg-xinput coreutils

mkdir -p ~/.config/systemd/user
install -m 644 background-suspend.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now background-suspend.service
```

The supplied unit uses `~/vampireslayer/background-suspend`. For a checkout
elsewhere, update `ExecStart` and `ExecStopPost` in your installed unit.

```sh
./background-suspend status    # Inspect the standalone user service
./background-suspend gaming    # Pause eligible apps immediately
./background-suspend start     # Resume apps and return to idle watching
./background-suspend stop      # Resume apps and disable automatic watching
```

On Wayland, launch from your compositor’s session environment. If your session
manager needs its variables imported into systemd, run:

```sh
systemctl --user import-environment WAYLAND_DISPLAY DISPLAY XDG_RUNTIME_DIR
systemctl --user restart background-suspend.service
```

For a foreground watcher, run `./background-suspend run` from your desktop terminal.

### Upgrading from firefox-idle

This repository grew out of the Firefox-only X11/VNC watcher in
[dagelf/utils](https://github.com/dagelf/utils). The current script is
**`background-suspend`**, and its standalone unit is **`background-suspend.service`**.
The `firefox-idle` file here is a compatibility launcher for
`~/utils/scripts/firefox-idle`, retained for existing installations.

From your checkout, retire the old watcher and resume its Firefox processes:

```sh
cd ~/vampireslayer
systemctl --user disable --now firefox-idle.service
./firefox-idle resume
```

Then choose the [Omarchy plugin](#install-on-omarchy) or enable the new
[standalone service](#standalone-arch-installation). Update shortcuts that invoke
`firefox-idle` to call `background-suspend` for standalone use, or use the
[plugin IPC actions](#hyprland-hotkeys) inside Omarchy.

To retain a Firefox-only policy with the new watcher, create your personal TOML:

```sh
mkdir -p ~/.config/vampireslayer
cp -n background-suspend.toml ~/.config/vampireslayer/
```

Edit these entries in `~/.config/vampireslayer/background-suspend.toml`, keeping
the other settings:

```toml
suspend = ["firefox", "firefox-esr"]
detect_electron = false
```

Restart your chosen watcher to apply it. Both setups keep the media exemptions,
ignore list, and optional worker exceptions available.

## Roadmap

- **Optional foreground-only execution:** suspend all eligible apps unless they are
  foreground; resume on focus and suspend again when they move to the background.
  Keep media and allowed-app exceptions configurable, with compositor focus
  tracking for multi-window apps and multiple monitors.

## Verification

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests -v
```

Tests use disposable app-named Python processes, synthetic input connections, and
a private D-Bus session. They cover family selection, media state changes, stale
replies, ignore precedence, media overrides, worker exits, PID reuse, and cleanup
after monitoring failure. Wayland tests exercise the real client library with a
private protocol peer, compositor-authoritative state, and a private Mutter API
service.


For an optional live systemd check, run
`VAMPIRESLAYER_TEST_SYSTEMD=1 python3 -m unittest discover -s tests -p 'test_plugin.py'`. It creates a
disposable waiting Python service and verifies cleanup after stop and forced exit.

The Omarchy manifest follows the [official development guide](https://plugins.omarchy.org/develop.html)
and [publishing guide](https://plugins.omarchy.org/publish.html). Validate with
`omarchy plugin validate .` and `qmllint Service.qml Widget.qml PixelVampire.qml` on an Omarchy installation.
The repository is licensed under [MIT](LICENSE).

On an Omarchy installation, `python3 tests/qml_smoke.py` exercises mode cycling
and editor gestures in a private offscreen shell with a fake backend.
Live VNC validation is recorded in [validation notes](docs/VALIDATION.md).

See [artwork notes](docs/ARTWORK.md) for the banner’s generation prompt and marketplace references.

PS This Plugin just packaged my normal arch tooling, check [utils](https://github.com/dagelf/utils), in tribute to DHH's Lex Fridman podcast.

PS Omarchy is a trap, if you're new to Linux, just use Mint or Arch with Xfce4! (Everything else is bloated!)
