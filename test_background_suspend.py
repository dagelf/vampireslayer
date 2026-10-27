"""Run with /usr/bin/python3 -m unittest -v test_background_suspend.

Uses a private D-Bus session and disposable browser-named processes, never the
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
import tempfile
import time
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name('background-suspend')
loader = importlib.machinery.SourceFileLoader('background_suspend', str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
app = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = app
loader.exec_module(app)


# Only test process families on a synthetic display can receive signals.
WATCH_TEST_CODE = '''
import os, signal, sys, tempfile
from pathlib import Path
from test_background_suspend import app
display = os.environ['DISPLAY']
send = app.app_signal
app.app_signal = lambda name, scope=None, playing=None, policy=None, worker_watch=None: send(name, display, playing, policy, worker_watch)
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
    policy = app.load_policy()
    policy.worker_exceptions = os.environ.get('TEST_WORKERS') == '1'
    if os.environ.get('TEST_NO_MEDIA') == '1':
        policy.suspend_media = ['*']
    app.watch(.1, policy)
'''

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
    name = f'org.mpris.MediaPlayer2.chromium.test_{os.getpid()}'
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

    def browser(self, display, name='firefox', child_name='helper-task'):
        code = f'''
import os, signal, json, sys
read, write = os.pipe()
os.set_inheritable(write, True)
child = os.fork()
if child == 0:
    os.close(read)
    os.environ.pop('DISPLAY', None)
    os.execv(os.readlink('/proc/self/exe'), [{child_name!r}, '-c',
        f'import os,signal; os.write({{write}}, b"1"); os.close({{write}}); signal.pause()'])
os.close(write)
os.read(read, 1)
os.close(read)
print(json.dumps([os.getpid(), child]), flush=True)
signal.pause()
'''
        proc = subprocess.Popen([name, '-c', code], executable=sys.executable,
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
        app.app_signal('SIGSTOP', display, {playing[0]})
        self.assert_state(playing + elsewhere, False)
        self.assert_state(idle, True)
        app.app_signal('SIGSTOP', display, set())  # Paused or Stopped: exemption removed.
        self.assert_state(playing + idle, True)
        app.app_signal('SIGSTOP', display, {playing[0]})  # Playback event resumes this family.
        self.assert_state(playing, False)
        self.assert_state(idle, True)
        app.app_signal('SIGCONT', display)
        self.assert_state(playing + idle + elsewhere, False)

    def test_chromium_child_media_override_ignore_and_workers(self):
        display = f':test-policy-{os.getpid()}'
        chrome = self.browser(display, 'chromium', 'node')
        opera = self.browser(display, 'opera')
        brave = self.browser(display, 'brave-browser')
        server = self.browser(display, 'node')
        policy = app.load_policy()
        policy.ignore = ['opera']
        app.app_signal('SIGSTOP', display, {chrome[1]}, policy)
        self.assert_state(chrome + opera + server, False)
        self.assert_state(brave, True)
        policy.suspend_media = ['chromium']
        app.app_signal('SIGSTOP', display, {chrome[1]}, policy)
        self.assert_state(chrome + brave, True)
        self.assert_state(opera + server, False)
        policy.worker_exceptions = True
        app.app_signal('SIGSTOP', display, set(), policy)
        self.assert_state(chrome + opera + server, False)
        self.assert_state(brave, True)
        app.app_signal('SIGCONT', display, policy=policy)
        self.assert_state(chrome + opera + brave + server, False)


class PolicyTests(unittest.TestCase):
    def proc(self, pid, name, ppid=1, display=':test', argv=()):
        return app.Process(pid, ppid, 123, (name, *argv), '/apps/' + name, display)

    def test_default_targets_and_no_generic_js_server(self):
        policy = app.load_policy()
        expected = ['firefox', 'chromium', 'opera', 'brave-browser', 'google-chrome',
                    'chrome', 'electron35', 'code', 'cursor', 'windsurf', 'qoder', 'antigravity', 'slack']
        processes = {i: self.proc(i, name, ppid=0) for i, name in enumerate(expected, 10)}
        processes[100] = self.proc(100, 'node', ppid=0, argv=('server.js',))
        processes[101] = self.proc(101, 'python', ppid=0, argv=('firefox',))
        processes[102] = self.proc(102, 'chrome', ppid=0, display='')
        families = app.app_families(processes, policy)
        self.assertEqual({root.argv[0] for root, _, _ in families}, set(expected))
        self.assertFalse(policy.worker_exceptions)
        self.assertTrue(policy.needs_media)

    def test_nested_matches_and_helpers_stay_in_one_family(self):
        processes = {10: self.proc(10, 'code'), 11: self.proc(11, 'sh', 10, ''),
                     12: self.proc(12, 'electron', 11), 13: self.proc(13, 'node', 12, '')}
        policy = app.load_policy()
        root, members, _ = app.app_families(processes, policy)[0]
        self.assertEqual(root.pid, 10)
        self.assertEqual({p.pid for p in members}, {10, 11, 12, 13})
        self.assertEqual(app.exemption(root, members, policy, {13}), 'playing')
        policy.suspend_media = ['code']
        self.assertIsNone(app.exemption(root, members, policy, {13}))
        policy.ignore = ['node']
        self.assertEqual(app.exemption(root, members, policy, {13}), 'ignored')

    def test_renamed_electron_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            resources = Path(directory, 'resources')
            resources.mkdir()
            (resources / 'app.asar').touch()
            proc = self.proc(10, 'custom-desktop')
            proc.exe = str(Path(directory, 'custom-desktop'))
            policy = app.load_policy()
            families = app.app_families({10: proc}, policy)
            self.assertEqual(families[0][2], 'electron bundle')
            policy.detect_electron = False
            self.assertEqual(app.app_families({10: proc}, policy), [])

    def test_unknown_media_and_global_override(self):
        proc, policy = self.proc(10, 'chrome'), app.load_policy()
        self.assertEqual(app.exemption(proc, [proc], policy, None), 'media unknown')
        policy.suspend_media = ['*']
        self.assertFalse(policy.needs_media)
        self.assertIsNone(app.exemption(proc, [proc], policy, None))
        policy.ignore = ['chrome']
        self.assertEqual(app.exemption(proc, [proc], policy, None), 'ignored')

    def test_cannot_suspend_controller_family(self):
        root, controller = self.proc(10, 'code'), self.proc(os.getpid(), 'python', 10)
        self.assertEqual(app.exemption(root, [root, controller], app.load_policy(), set()), 'controller')

    def test_bad_config_and_media_snapshots_fail_validation(self):
        for value in ('ignore = "chrome"', 'worker_exceptions = 1', 'suspend = [false]', 'typo = true'):
            with self.subTest(value=value), tempfile.NamedTemporaryFile(mode='w') as file:
                file.write(value)
                file.flush()
                with self.assertRaises(ValueError):
                    app.load_policy(file.name)
        for value in ('[true]', '[-1]', '{}', '["123"]'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                app.parse_media(value)

    def test_pin_rejects_reused_pid(self):
        proc = self.proc(10, 'chrome')
        fields = ['S', '1'] + ['0'] * 17 + ['456']
        with mock.patch.object(app.os, 'pidfd_open', return_value=99), \
             mock.patch.object(app.os, 'close') as close, \
             mock.patch.object(app.Path, 'read_text', return_value='10 (chrome) ' + ' '.join(fields)):
            with self.assertRaises(ProcessLookupError):
                app.pin(proc)
            close.assert_called_once_with(99)


class WorkerWatchTests(unittest.TestCase):
    browser = IdleTests.browser
    assert_state = IdleTests.assert_state

    def test_worker_exit_rechecks_idle_family_without_media_monitor(self):
        display = f':test-worker-{os.getpid()}'
        editor = self.browser(display, 'code', 'node')
        other = self.browser(display, 'chromium')
        watcher = subprocess.Popen([sys.executable, '-c', WATCH_TEST_CODE],
                                   env={**os.environ, 'DISPLAY': display,
                                        'TEST_WORKERS': '1', 'TEST_NO_MEDIA': '1'},
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        def cleanup():
            watcher.terminate()
            try:
                watcher.wait(timeout=3)
            except subprocess.TimeoutExpired:
                watcher.kill()
                watcher.wait()
            watcher.stdout.close()
            watcher.stderr.close()
        self.addCleanup(cleanup)
        self.assert_state(other, True)
        self.assert_state(editor, False)
        deadline = time.monotonic() + 3
        while True:
            infos = [p.read_text() for p in Path(f'/proc/{watcher.pid}/fdinfo').iterdir()]
            if any(f'Pid:\t{editor[1]}\n' in info for info in infos):
                break
            if time.monotonic() >= deadline:
                self.fail('Worker pidfd was not registered')
            time.sleep(.01)
        children = Path(f'/proc/{watcher.pid}/task/{watcher.pid}/children').read_text().split()
        self.assertFalse(any(b'media-watch' in Path(f'/proc/{pid}/cmdline').read_bytes()
                             for pid in children))
        os.kill(editor[1], signal.SIGKILL)
        self.assert_state([editor[0]], True)
        watcher.terminate()
        watcher.wait(timeout=3)
        self.assertEqual(watcher.returncode, 0, watcher.stderr.read())
        self.assert_state([editor[0], *other], False)


@unittest.skipUnless(os.environ.get('BACKGROUND_SUSPEND_TEST_BUS'), 'runs inside private D-Bus test below')
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
        watcher, _ = self.start_process([sys.executable, '-c', WATCH_TEST_CODE], env=env)
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
        if os.environ.get('BACKGROUND_SUSPEND_TEST_BUS'):
            self.skipTest('Already running on private bus')
        result = subprocess.run(['dbus-run-session', '--', sys.executable, '-m', 'unittest',
                                 '-v', 'test_background_suspend.MediaBusTests'],
                                env={**os.environ, 'BACKGROUND_SUSPEND_TEST_BUS': '1'},
                                capture_output=True, text=True, timeout=25,
                                cwd=SCRIPT.parent)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    if '--fake-player' in sys.argv:
        fake_player()
    else:
        unittest.main()
