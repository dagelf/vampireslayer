"""Run with /usr/bin/python3 -m unittest -v test_firefox_idle.

Uses a private D-Bus session and disposable Firefox-named processes, never the
desktop's browsers. No network or desktop display is needed.
"""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time
import unittest

SCRIPT = Path(__file__).with_name('firefox-idle')
loader = importlib.machinery.SourceFileLoader('firefox_idle', str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
app = importlib.util.module_from_spec(spec)
loader.exec_module(app)


class Lines:
    def __init__(self, pipe):
        self.pipe, self.buffer = pipe, b''

    def read(self):
        deadline = time.monotonic() + 5
        while b'\n' not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.pipe], [], [], remaining)[0]:
                raise AssertionError('Timed out waiting for subprocess output')
            data = os.read(self.pipe.fileno(), 65536)
            if not data:
                raise AssertionError('Subprocess ended unexpectedly')
            self.buffer += data
        line, self.buffer = self.buffer.split(b'\n', 1)
        return json.loads(line)


def fake_player():
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    name = f'org.mpris.MediaPlayer2.firefox.test_{os.getpid()}'
    bus.request_name(name)
    interface = 'org.mpris.MediaPlayer2.Player'

    class Player(dbus.service.Object):
        status = 'Playing' if '--playing' in sys.argv else 'Paused'
        deferred = False
        pending = []

        @dbus.service.method('org.freedesktop.DBus.Properties', in_signature='ss',
                             out_signature='v', async_callbacks=('reply', 'error'))
        def Get(self, iface, prop, reply, error):
            assert iface == interface and prop == 'PlaybackStatus'
            if self.deferred:
                self.pending.append((reply, self.status))
            else:
                reply(dbus.String(self.status))
            print(json.dumps('queried'), flush=True)

        @dbus.service.signal('org.freedesktop.DBus.Properties', signature='sa{sv}as')
        def PropertiesChanged(self, iface, changed, invalidated):
            pass

    player = Player(bus, '/org/mpris/MediaPlayer2')
    loop = GLib.MainLoop()

    def command(fd, condition):
        # Avoid TextIO readahead hiding a second command from the fd watcher.
        line = sys.stdin.buffer.raw.readline().decode().strip()
        if not line:
            loop.quit()
            return False
        if line in ('Playing', 'Paused', 'Stopped'):
            player.status = line
            player.PropertiesChanged(interface, {'PlaybackStatus': line}, [])
        elif line == 'defer':
            player.deferred = True
            player.PropertiesChanged(interface, {}, ['PlaybackStatus'])
        elif line == 'reply':
            for reply, status in player.pending:
                reply(dbus.String(status))
            player.pending.clear()
            player.deferred = False
        elif line == 'remove':
            bus.release_name(name)
        elif line == 'acquire':
            bus.request_name(name)
        elif line == 'invalidate':
            player.PropertiesChanged(interface, {}, ['PlaybackStatus'])
        return True

    GLib.io_add_watch(sys.stdin.fileno(), GLib.IO_IN | GLib.IO_HUP, command)
    print(json.dumps(os.getpid()), flush=True)
    loop.run()


class IdleTests(unittest.TestCase):
    def test_media_changes_do_not_reset_idle_deadline(self):
        now, sent = [0], []
        idle = app.Idle(10, send=sent.append, clock=lambda: now[0])
        idle.media_changed()
        self.assertEqual(sent, [])
        now[0] = 10
        idle.expire()
        idle.expire()
        self.assertEqual(sent, ['SIGSTOP'])
        idle.media_changed()
        self.assertEqual(sent, ['SIGSTOP', 'SIGSTOP'])
        self.assertEqual(idle.last_input, 0)
        idle.resume()  # Detection temporarily unknown: resume but retain deadline.
        self.assertEqual(idle.timeout(), 0)
        idle.expire()
        idle.activity()
        self.assertFalse(idle.paused)
        self.assertEqual(idle.timeout(), 10)
        self.assertEqual(sent[-3:], ['SIGCONT', 'SIGSTOP', 'SIGCONT'])

    def browser(self, display):
        code = ('import os,signal,json; child=os.fork(); '
                'print(json.dumps([os.getpid(), child]),flush=True) if child else None; '
                'signal.pause()')
        proc = subprocess.Popen(['firefox', '-c', code], executable=sys.executable,
                                env={**os.environ, 'DISPLAY': display}, stdout=subprocess.PIPE)
        root, child = Lines(proc.stdout).read()

        def cleanup():
            for pid in (child, root):
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            proc.wait(timeout=3)
            proc.stdout.close()
        self.addCleanup(cleanup)
        return root, child

    def assert_state(self, pids, stopped):
        deadline = time.monotonic() + 3
        while True:
            states = [Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0]
                      for pid in pids]
            if all((state == 'T') == stopped for state in states):
                return
            if time.monotonic() >= deadline:
                self.fail(f'Expected stopped={stopped}, got {states}')
            time.sleep(.01)

    def test_only_playing_family_is_exempt_on_shared_display(self):
        display = f':test-{os.getpid()}'
        playing = self.browser(display)
        idle = self.browser(display)
        elsewhere = self.browser(display + '-other')
        app.suspend_except(display, {playing[0]})
        self.assert_state(playing + elsewhere, False)
        self.assert_state(idle, True)
        app.suspend_except(display, set())  # Paused or Stopped: exemption removed.
        self.assert_state(playing + idle, True)
        app.suspend_except(display, {playing[0]})  # Playback event resumes this family.
        self.assert_state(playing, False)
        self.assert_state(idle, True)
        app.firefox_signal('SIGCONT', display)
        self.assert_state(playing + idle + elsewhere, False)


@unittest.skipUnless(os.environ.get('FIREFOX_IDLE_TEST_BUS'), 'runs inside private D-Bus test below')
class MediaBusTests(unittest.TestCase):
    assert_state = IdleTests.assert_state

    def start_process(self, command, **kwargs):
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, **kwargs)

        def cleanup():
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            for pipe in (proc.stdin, proc.stdout, proc.stderr):
                pipe.close()
        self.addCleanup(cleanup)
        return proc, Lines(proc.stdout)

    def test_watcher_failure_resumes_idle_browsers(self):
        display = f':test-watch-{os.getpid()}'
        env = {**os.environ, 'DISPLAY': display}
        player, output = self.start_process(
            ['firefox', __file__, '--fake-player', '--playing'], executable=sys.executable, env=env)
        pid = output.read()
        idle, _ = self.start_process(['firefox', '-c', 'import signal; signal.pause()'],
                                    executable=sys.executable, env=env)
        # Exercise the real selector loop and media subprocess. Supply a quiet
        # XInput connection and scope every signal to disposable test processes.
        code = '''
import os, signal, sys, tempfile
from pathlib import Path
from test_firefox_idle import app
display = os.environ['DISPLAY']
send = app.firefox_signal
app.firefox_signal = lambda name, scope=None, playing=None: send(name, display, playing)
app.displays = lambda: {display: (1, 1)}
popen = app.subprocess.Popen
def start(command, **kwargs):
    if command[0] == 'stdbuf':
        command = [sys.executable, '-c',
                   'import signal; print("device id=1", flush=True); signal.pause()']
    return popen(command, **kwargs)
app.subprocess.Popen = start
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
with tempfile.TemporaryDirectory() as directory:
    app.XSOCKETS = Path(directory)
    app.watch(.1)
'''
        watcher, _ = self.start_process([sys.executable, '-c', code], env=env)
        self.assert_state([idle.pid], True)
        self.assert_state([pid], False)
        children = Path(f'/proc/{watcher.pid}/task/{watcher.pid}/children').read_text().split()
        monitors = [int(p) for p in children
                    if b'media-watch' in Path(f'/proc/{p}/cmdline').read_bytes().split(b'\0')]
        self.assertEqual(len(monitors), 1)
        os.kill(monitors[0], signal.SIGTERM)
        watcher.wait(timeout=5)
        self.assertNotEqual(watcher.returncode, 0)
        self.assertIn(b'Media watcher ended', watcher.stderr.read())
        self.assert_state([pid, idle.pid], False)

    def test_registered_paused_playing_stopped_removed_and_stale_reply(self):
        player, replies = self.start_process([sys.executable, __file__, '--fake-player'])
        pid = replies.read()
        watcher, snapshots = self.start_process([sys.executable, str(SCRIPT), 'media-watch'])

        def snapshot(expected):
            value = snapshots.read()
            if value is None and expected is not None:
                value = snapshots.read()
            self.assertEqual(value, expected)

        def command(text):
            player.stdin.write((text + '\n').encode())
            player.stdin.flush()

        snapshot([])  # Registration alone is insufficient; initially Paused.
        self.assertEqual(replies.read(), 'queried')
        command('Playing')
        snapshot([pid])
        command('Paused')
        snapshot([])
        command('Playing')
        snapshot([pid])
        command('Stopped')
        snapshot([])
        command('defer')
        snapshot(None)
        self.assertEqual(replies.read(), 'queried')
        command('Playing')  # A fresh signal wins over the delayed Stopped reply.
        snapshot([pid])
        command('reply')
        command('invalidate')
        snapshot(None)
        snapshot([pid])
        self.assertEqual(replies.read(), 'queried')
        command('remove')
        snapshot([])
        command('acquire')
        snapshot([pid])
        self.assertEqual(replies.read(), 'queried')
        command('defer')
        snapshot(None)
        watcher.wait(timeout=5)  # Unknown status must fail safely, never hang.
        self.assertEqual(watcher.returncode, 1)
        self.assertIn(b'Media monitoring failed', watcher.stderr.read())


class IsolatedBusTests(unittest.TestCase):
    def test_media_events_on_private_bus(self):
        if os.environ.get('FIREFOX_IDLE_TEST_BUS'):
            self.skipTest('Already running on private bus')
        result = subprocess.run(['dbus-run-session', '--', sys.executable, '-m', 'unittest',
                                 '-v', 'test_firefox_idle.MediaBusTests'],
                                env={**os.environ, 'FIREFOX_IDLE_TEST_BUS': '1'},
                                capture_output=True, text=True, timeout=25,
                                cwd=SCRIPT.parent)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    if '--fake-player' in sys.argv:
        fake_player()
    else:
        unittest.main()
