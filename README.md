# background-suspend

Suspend browser and Electron process families after 15 minutes without real input
on their X11/VNC display. Activity resumes that display's apps. This retains the
original per-display idle model: it does not suspend an unfocused app while you
are using another app on the same display. XTEST-generated input is ignored.

## Defaults and exceptions

Edit [`background-suspend.toml`](background-suspend.toml). Restart the watcher after
editing its policy. Patterns are case-insensitive shell globs, not regular expressions.

| Setting | Default and meaning |
| --- | --- |
| `suspend` | Firefox, Chromium, Chrome, Opera, Brave, other browser variants, common Electron apps and editors, Electron and NW.js runtimes. Matches executable basenames. |
| `detect_electron` | `true`: also recognize renamed executables with adjacent `resources/app.asar` or `resources/electron.asar`. |
| `ignore` | `[]`: never suspend matching app families. A matching executable anywhere in the family exempts the whole family. Takes precedence over other options. |
| `suspend_media` | `[]`: keep every app with detected playing media awake. List app-root executable patterns to suspend them even with media; `["*"]` disables media exemptions entirely. |
| `worker_exceptions` | `false`: opt in to preserving apps with matching background workers. |
| `background_workers` | Configurable process/argument-token patterns for Node, builds, language servers, explicit worker scripts, transfers, and headless jobs. Used only when worker exceptions are enabled. |

App roots need a `DISPLAY`; all their owned descendant processes follow their
policy, including helpers without a `DISPLAY`. A standalone Node/Bun/Deno server
is not selected merely because it runs JavaScript. Add its executable to `suspend`
explicitly if wanted. The controller's own ancestor family is always protected.

Media detection listens to **all** registered MPRIS players and maps their PIDs
back to app families, including players hosted in helper processes. Only
[`PlaybackStatus = Playing`](https://specifications.freedesktop.org/mpris/latest/Player_Interface.html)
grants an exemption. Paused/stopped players do not. Media not exposed through
MPRIS, such as some calls and WebAudio applications, cannot be detected. Unknown
status temporarily releases suspensions; a failed monitor resumes apps and exits.
When media exemptions are disabled globally, no media monitor is required.

Worker exceptions protect an **entire app family**, not just its worker. A worker's
existence is the signal, not CPU use: a long-lived idle Node worker will also keep
the app awake. Worker exits trigger an immediate recheck using pidfds, with no
polling timer. Browser service workers and worker threads inside renderers cannot
be reliably classified from OS process names; use an app ignore rule for those.

## Commands

Requires Linux pidfds, Python 3.11+, `python3-dbus`, `python3-gi`, `xinput`, and
`stdbuf`. No browser extension or remote-debugging port is required.

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

`list` shows what would happen when a display becomes idle, not whether its idle
deadline has elapsed. The ignore list always wins, including in `gaming` mode.

The service controls are `start`, `stop`, `status`, and `gaming`. `gaming` stops
automatic watching and immediately suspends eligible apps, respecting media and
worker exceptions. Use `gaming --suspend-media` to override media, and `start` to
return to automatic mode. Gaming exemptions are a one-time snapshot; worker/media
changes are followed only in `run` mode. Put persistent policy in the TOML file;
service controls do not pass command-line policy overrides to systemd.

## Installation and existing Firefox service

This change is confined to this repository. `~/utils/scripts/firefox-idle` and the
installed Firefox service are unchanged. The small `firefox-idle` compatibility
launcher delegates to that existing utils script because the old service points
at this folder. It continues to use the previous Firefox-only policy.

The new unit is supplied here, but is **not installed or enabled automatically**.
To switch from the old service, from this directory:

```sh
systemctl --user disable --now firefox-idle.service
install -m 644 background-suspend.service ~/.config/systemd/user/
systemctl --user daemon-reload
./background-suspend start
```

The supplied unit assumes the checkout is `~/vampireslayer`; adjust its paths if
you move it. Do not run both watchers on the same displays.

## Verification

```sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest -v test_background_suspend
```

Tests use disposable app-named Python processes, synthetic input connections, and
a private D-Bus session. They cover family selection, media state changes, stale
replies, ignore precedence, media overrides, worker exits, PID reuse, and cleanup
after monitoring failure. They do not suspend desktop apps.
