"""Private Wayland wire and Mutter D-Bus fixtures; never connects to the desktop."""
import json
import os
from pathlib import Path
import queue
import select
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import unittest

import test_background_suspend as fixtures
from test_background_suspend import Lines, app

HELPER = Path(__file__).with_name('wayland_idle.py')


def uint(value):
    return struct.pack('=I', value)


def string(value):
    data = value.encode() + b'\0'
    return uint(len(data)) + data + b'\0' * (-len(data) % 4)


class Compositor:
    """Minimal protocol peer to exercise the actual libwayland-client binding."""
    def __init__(self, path, version=2, seats=1):
        self.version, self.seat_count = version, seats
        self.requests, self.commands = queue.Queue(), queue.Queue()
        self.errors, self.connection = [], None
        self.closed = False
        self.listener = socket.socket(socket.AF_UNIX)
        self.listener.bind(str(path))
        self.listener.listen(1)
        self.wake_read, self.wake_write = socket.socketpair()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def event(self, obj, opcode, payload=b''):
        self.connection.sendall(uint(obj) + uint(((len(payload) + 8) << 16) | opcode) + payload)

    def run(self):
        try:
            self.connection, _ = self.listener.accept()
            objects, buffer = {1: 'display'}, b''
            while True:
                ready, _, _ = select.select([self.connection, self.wake_read], [], [])
                if self.wake_read in ready:
                    self.wake_read.recv(1)
                    command = self.commands.get()
                    if command is None:
                        return
                    self.event(*command)
                if self.connection not in ready:
                    continue
                data = self.connection.recv(65536)
                if not data:
                    return
                buffer += data
                while len(buffer) >= 8:
                    obj, header = struct.unpack('=II', buffer[:8])
                    size, opcode = header >> 16, header & 0xffff
                    if len(buffer) < size:
                        break
                    payload, buffer = buffer[8:size], buffer[size:]
                    kind = objects[obj]
                    if kind == 'display' and opcode == 1:
                        registry, = struct.unpack('=I', payload)
                        objects[registry] = 'registry'
                        if self.version is not None:
                            self.event(registry, 0, uint(100) + string('ext_idle_notifier_v1') + uint(self.version))
                        for seat in range(self.seat_count):
                            self.event(registry, 0, uint(200 + seat) + string('wl_seat') + uint(1))
                    elif kind == 'display' and opcode == 0:
                        callback, = struct.unpack('=I', payload)
                        self.event(callback, 0, uint(0))
                        self.event(1, 1, uint(callback))  # display.delete_id
                    elif kind == 'registry' and opcode == 0:
                        name, length = struct.unpack('=II', payload[:8])
                        interface = payload[8:8 + length - 1].decode()
                        offset = 8 + ((length + 3) // 4) * 4
                        version, new_id = struct.unpack('=II', payload[offset:])
                        objects[new_id] = interface
                        if interface == 'wl_seat':
                            self.event(new_id, 0, uint(3))  # capabilities
                    elif kind == 'ext_idle_notifier_v1':
                        notification, timeout, seat = struct.unpack('=III', payload)
                        objects[notification] = 'ext_idle_notification_v1'
                        self.requests.put((notification, opcode, timeout, seat))
                    else:
                        raise AssertionError(f'Unexpected request: {kind}/{opcode}')
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as error:
            self.errors.append(error)
        finally:
            if self.connection is not None:
                self.connection.close()

    def send(self, obj, opcode):
        self.commands.put((obj, opcode))
        self.wake_write.send(b'1')

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.commands.put(None)
        try:
            self.wake_write.send(b'1')
        except BrokenPipeError:
            pass
        self.thread.join(timeout=3)
        for stream in (self.listener, self.wake_read, self.wake_write):
            stream.close()


class PlainLines(Lines):
    def __init__(self, pipe):
        super().__init__(pipe, bytes.decode)


class WaylandProtocolTests(unittest.TestCase):
    def test_input_idle_events_multiseat_and_disconnect(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'wayland-test')
            server = Compositor(path, seats=2)
            self.addCleanup(server.close)
            child = subprocess.Popen([sys.executable, str(HELPER), str(path), '1234'],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.addCleanup(self.stop, child)
            events = PlainLines(child.stdout)
            first, second = server.requests.get(timeout=5), server.requests.get(timeout=5)
            self.assertEqual(first[1:3], (2, 1234))
            self.assertEqual(second[1:3], (2, 1234))
            self.assertEqual(events.read(), 'active')
            server.send(first[0], 0)
            server.send(second[0], 0)
            self.assertEqual(events.read(), 'idle')
            server.send(first[0], 1)
            self.assertEqual(events.read(), 'active')
            server.close()
            child.wait(timeout=3)
            self.assertEqual(child.returncode, 1)
            self.assertIn(b'disconnected', child.stderr.read())
            self.assertEqual(server.errors, [])
            self.doCleanups()

    def test_v1_uses_inhibitor_aware_request(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'wayland-test')
            server = Compositor(path, version=1)
            self.addCleanup(server.close)
            child = subprocess.Popen([sys.executable, str(HELPER), str(path), '1000'],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.addCleanup(self.stop, child)
            notification, opcode, timeout, _ = server.requests.get(timeout=5)
            self.assertEqual((opcode, timeout), (1, 1000))
            events = PlainLines(child.stdout)
            self.assertEqual(events.read(), 'active')
            server.send(notification, 0)
            self.assertEqual(events.read(), 'idle')
            self.stop(child)
            self.assertEqual(server.errors, [])
            self.doCleanups()

    @staticmethod
    def stop(child):
        child.terminate()
        child.wait(timeout=3)
        child.stdout.close()
        child.stderr.close()


class WaylandStateTests(unittest.TestCase):
    assert_state = fixtures.IdleTests.assert_state

    def test_native_process_without_display_is_selected_and_resumed(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {**os.environ, 'WAYLAND_DISPLAY': 'wayland-test', 'XDG_RUNTIME_DIR': directory}
            env.pop('DISPLAY', None)
            process = subprocess.Popen(['chromium', '-c',
                                        'import os,signal; print(os.getpid(),flush=True); signal.pause()'],
                                       executable=sys.executable, env=env, stdout=subprocess.PIPE)
            try:
                self.assertEqual(Lines(process.stdout).read(), process.pid)
                proc = app.process_snapshot()[process.pid]
                self.assertEqual(proc.display, '')
                self.assertEqual(proc.scope, app.wayland_scope(env))
                app.app_signal('SIGSTOP', proc.scope, set())
                self.assert_state([process.pid], True)
                app.app_signal('SIGCONT', proc.scope)
                self.assert_state([process.pid], False)
            finally:
                process.kill()
                process.wait(timeout=3)
                process.stdout.close()

    def test_only_compositor_can_expire_wayland_idle(self):
        sent = []
        idle = app.CompositorIdle(1, send=sent.append, clock=lambda: 100)
        idle.last_input = 0
        idle.expire()
        self.assertEqual(sent, [])
        idle.inactive = True
        idle.expire()
        self.assertEqual(sent, ['SIGSTOP'])
        idle.resume()  # Media status temporarily unknown; keep compositor state.
        self.assertEqual(idle.timeout(), 0)
        idle.expire()
        idle.activity()
        self.assertEqual(sent, ['SIGSTOP', 'SIGCONT', 'SIGSTOP', 'SIGCONT'])
        self.assertIsNone(idle.timeout())

    def test_native_and_xwayland_share_scope_but_vnc_does_not(self):
        from unittest import mock
        env = {'WAYLAND_DISPLAY': 'wayland-1', 'XDG_RUNTIME_DIR': '/run/user/123', 'DISPLAY': ':0'}
        with mock.patch.dict(os.environ, env, clear=True):
            key = app.wayland_scope(env)
            native = app.Process(10, 1, 1, ('chrome',), '/apps/chrome', '', key)
            xwayland = app.Process(20, 1, 1, ('firefox',), '/apps/firefox', ':0')
            vnc = app.Process(30, 1, 1, ('firefox',), '/apps/firefox', ':9')
            self.assertEqual(native.scope, xwayland.scope)
            self.assertNotEqual(native.scope, vnc.scope)
            families = app.app_families({10: native, 20: xwayland, 30: vnc}, app.load_policy(), key)
            self.assertEqual({root.pid for root, _, _ in families}, {10, 20})

    def test_partial_events_and_lost_connection_resume(self):
        from unittest import mock
        sent = []
        with mock.patch.object(app.subprocess, 'Popen') as popen:
            popen.return_value.stdout.closed = False
            session = app.WaylandSession('wayland:/tmp/test', (1, 1), 1, set(),
                                         lambda name, *_: sent.append(name))
            session.feed(b'act')
            self.assertFalse(session.ready)
            session.feed(b'ive\n')
            self.assertTrue(session.ready)
            session.idle.expire()
            self.assertEqual(sent, [])
            session.feed(b'idle\n')
            session.idle.expire()
            self.assertEqual(sent, ['SIGSTOP'])
            session.close()
            self.assertEqual(sent, ['SIGSTOP', 'SIGCONT'])


def fake_mutter():
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    interface = 'org.gnome.Mutter.IdleMonitor'

    class Monitor(dbus.service.Object):
        counter, idletime = 0, 0
        watches = {}

        @dbus.service.method(interface, in_signature='t', out_signature='u')
        def AddIdleWatch(self, interval):
            self.counter += 1
            self.watches[self.counter] = 'idle'
            return self.counter

        @dbus.service.method(interface, in_signature='', out_signature='u')
        def AddUserActiveWatch(self):
            self.counter += 1
            self.watches[self.counter] = 'active'
            return self.counter

        @dbus.service.method(interface, in_signature='', out_signature='t')
        def GetIdletime(self):
            return self.idletime

        @dbus.service.method(interface, in_signature='u', out_signature='')
        def RemoveWatch(self, watch):
            self.watches.pop(watch, None)

        @dbus.service.signal(interface, signature='u')
        def WatchFired(self, watch):
            pass

    monitor = Monitor(bus, '/org/gnome/Mutter/IdleMonitor/Core')
    bus.request_name(interface)
    server = Compositor(sys.argv[2], version=None)
    loop = GLib.MainLoop()

    def command(fd, condition):
        line = sys.stdin.buffer.raw.readline().decode().strip()
        if not line:
            loop.quit()
            return False
        if line == 'remove':
            bus.release_name(interface)
        elif line in ('idle', 'active', 'race'):
            monitor.idletime = 10000 if line == 'idle' else 0
            for watch, kind in list(monitor.watches.items()):
                if kind == ('idle' if line == 'race' else line):
                    monitor.WatchFired(watch)
                    if kind == 'active':
                        monitor.watches.pop(watch, None)
        return True

    GLib.io_add_watch(sys.stdin.fileno(), GLib.IO_IN | GLib.IO_HUP, command)
    print(json.dumps(os.getpid()), flush=True)
    try:
        loop.run()
    finally:
        server.close()


@unittest.skipUnless(os.environ.get('BACKGROUND_SUSPEND_WAYLAND_TEST_BUS'), 'runs in private bus test')
class MutterTests(unittest.TestCase):
    def spawn(self, command):
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        def close():
            process.terminate()
            process.wait(timeout=3)
            process.stdin.close()
            process.stdout.close()
            process.stderr.close()
        self.addCleanup(close)
        return process

    def test_idle_active_rearming_owner_loss_and_wrong_compositor(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = str(Path(directory.name, 'wayland-mutter'))
        service = self.spawn([sys.executable, __file__, '--fake-mutter', path])
        pid = Lines(service.stdout).read()
        code = 'from wayland_idle import gnome_watch; gnome_watch(1000, int(__import__("sys").argv[1]))'
        wrong = self.spawn([sys.executable, '-c', code, str(pid + 1)])
        wrong.wait(timeout=5)
        self.assertNotEqual(wrong.returncode, 0)
        self.assertIn(b'different compositor', wrong.stderr.read())
        helper = self.spawn([sys.executable, str(HELPER), path, '1000'])
        events = PlainLines(helper.stdout)
        self.assertEqual(events.read(), 'active')

        def command(text):
            service.stdin.write((text + '\n').encode())
            service.stdin.flush()

        for _ in range(2):
            command('idle')
            self.assertEqual(events.read(), 'idle')
            command('active')
            self.assertEqual(events.read(), 'active')
        command('race')  # Stale idle signal; GetIdletime says user is active.
        command('idle')
        self.assertEqual(events.read(), 'idle')
        command('remove')
        helper.wait(timeout=5)
        self.assertNotEqual(helper.returncode, 0)
        self.assertIn(b'idle service disappeared', helper.stderr.read())


class IsolatedMutterTests(unittest.TestCase):
    def test_private_bus(self):
        result = subprocess.run(['dbus-run-session', '--', sys.executable, '-m', 'unittest',
                                 '-v', 'test_wayland_idle.MutterTests'],
                                env={**os.environ, 'BACKGROUND_SUSPEND_WAYLAND_TEST_BUS': '1'},
                                cwd=HELPER.parent, capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    if '--fake-mutter' in sys.argv:
        fake_mutter()
    else:
        unittest.main()
