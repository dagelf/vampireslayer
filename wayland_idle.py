"""Idle/resumed events using the compositor's API; no input devices or polling.

ext-idle-notify is bound through the system libwayland-client. If unavailable,
try Mutter's D-Bus API only when it belongs to this socket's compositor process.
"""
import ctypes as C
import os
import socket
import struct
import sys


class Message(C.Structure):
    _fields_ = [('name', C.c_char_p), ('signature', C.c_char_p), ('types', C.POINTER(C.c_void_p))]


class Interface(C.Structure):
    _fields_ = [('name', C.c_char_p), ('version', C.c_int),
                ('method_count', C.c_int), ('methods', C.POINTER(Message)),
                ('event_count', C.c_int), ('events', C.POINTER(Message))]


class WaylandIdle:
    """Small binding for registry, seats, and ext-idle-notify only."""
    def __init__(self, path, milliseconds):
        self.milliseconds = milliseconds
        self.lib = C.CDLL('libwayland-client.so.0')
        self.keep = []  # C callbacks and protocol descriptors must stay alive.
        self.globals, self.seats = {}, {}
        self.manager = None
        self.ready, self.failed, self.last = False, False, None
        self.lib.wl_display_connect.argtypes = [C.c_char_p]
        self.lib.wl_display_connect.restype = C.c_void_p
        for name in ('wl_display_roundtrip', 'wl_display_dispatch', 'wl_display_get_fd'):
            function = getattr(self.lib, name)
            function.argtypes, function.restype = [C.c_void_p], C.c_int
        self.lib.wl_display_disconnect.argtypes = [C.c_void_p]
        self.lib.wl_proxy_add_listener.argtypes = [C.c_void_p, C.POINTER(C.c_void_p), C.c_void_p]
        self.lib.wl_proxy_marshal_flags.argtypes = [C.c_void_p, C.c_uint32, C.POINTER(Interface),
                                                   C.c_uint32, C.c_uint32]
        self.lib.wl_proxy_marshal_flags.restype = C.c_void_p
        self.registry_type = Interface.in_dll(self.lib, 'wl_registry_interface')
        self.seat_type = Interface.in_dll(self.lib, 'wl_seat_interface')
        self.notification_type = Interface(b'ext_idle_notification_v1', 2, 1,
                                           (Message * 1)(Message(b'destroy', b'', None)), 2,
                                           (Message * 2)(Message(b'idled', b'', None), Message(b'resumed', b'', None)))
        types = (C.c_void_p * 3)(C.addressof(self.notification_type), None, C.addressof(self.seat_type))
        self.manager_type = Interface(b'ext_idle_notifier_v1', 2, 3,
                                      (Message * 3)(Message(b'destroy', b'', None),
                                                    Message(b'get_idle_notification', b'nuo', types),
                                                    Message(b'get_input_idle_notification', b'2nuo', types)), 0, None)
        self.keep.append(types)
        self.display = self.lib.wl_display_connect(os.fsencode(path))
        if not self.display:
            raise RuntimeError(f'Cannot connect to Wayland socket {path}')

    def request(self, proxy, opcode, interface, version, *args):
        result = self.lib.wl_proxy_marshal_flags(proxy, opcode, C.byref(interface), version, 0, *args)
        if not result:
            raise RuntimeError('Cannot create Wayland protocol object')
        return result

    def listen(self, proxy, entries):
        callbacks = []
        for args, function in entries:
            # Exceptions must stop the helper, not disappear inside a C callback.
            def guarded(*values, callback=function):
                try:
                    callback(*values[2:])
                except Exception as error:
                    self.failed = str(error)
            callbacks.append(C.CFUNCTYPE(None, C.c_void_p, C.c_void_p, *args)(guarded))
        listener = (C.c_void_p * len(callbacks))(*(C.cast(c, C.c_void_p) for c in callbacks))
        self.keep.extend([callbacks, listener])
        if self.lib.wl_proxy_add_listener(proxy, listener, None) != 0:
            raise RuntimeError('Cannot listen for Wayland idle events')

    def bind(self, name, interface, version):
        return self.request(self.registry, 0, interface, version,
                            C.c_uint32(name), C.c_char_p(interface.name), C.c_uint32(version), None)

    def publish(self):
        if self.ready and self.seats:
            state = 'idle' if all(self.seats.values()) else 'active'
            if state != self.last:
                print(state, flush=True)
                self.last = state

    def seat_state(self, name, idle):
        if name in self.seats:
            self.seats[name] = idle
            self.publish()

    def add_seat(self, name):
        self.seats[name] = False
        seat = self.bind(name, self.seat_type, 1)
        self.listen(seat, [([C.c_uint32], lambda capabilities: None)])
        # Version 2 ignores compositor idle inhibitors; app media policy stays local.
        notification = self.request(self.manager, 2 if self.version >= 2 else 1,
                                    self.notification_type, self.version,
                                    None, C.c_uint32(self.milliseconds), C.c_void_p(seat))
        self.listen(notification, [([], lambda: self.seat_state(name, True)),
                                   ([], lambda: self.seat_state(name, False))])
        self.publish()

    def global_added(self, name, interface, version):
        self.globals[name] = (interface, version)
        if self.ready and interface == b'wl_seat':
            self.add_seat(name)

    def global_removed(self, name):
        self.globals.pop(name, None)
        if name in self.seats or name == getattr(self, 'manager_name', None):
            # Resume through the parent's EOF handler instead of ignoring a lost seat.
            self.failed = 'Wayland idle manager or seat removed; restart watcher'

    def roundtrip(self):
        if self.lib.wl_display_roundtrip(self.display) < 0 or self.failed:
            raise RuntimeError(self.failed or 'Wayland compositor disconnected')

    def run(self):
        self.registry = self.request(self.display, 1, self.registry_type, 1, None)
        self.listen(self.registry, [([C.c_uint32, C.c_char_p, C.c_uint32], self.global_added),
                                    ([C.c_uint32], self.global_removed)])
        self.roundtrip()
        managers = [(name, version) for name, (interface, version) in self.globals.items()
                    if interface == b'ext_idle_notifier_v1']
        if not managers:
            fd = self.lib.wl_display_get_fd(self.display)
            with socket.socket(fileno=os.dup(fd)) as connection:
                pid, _, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            return pid  # Mutter fallback must be owned by this compositor.
        self.manager_name, version = managers[0]
        self.version = min(version, 2)
        self.manager = self.bind(self.manager_name, self.manager_type, self.version)
        if self.version == 1:
            print('Wayland idle protocol v1: compositor idle inhibitors still apply', file=sys.stderr, flush=True)
        for name, (interface, _) in list(self.globals.items()):
            if interface == b'wl_seat':
                self.add_seat(name)
        if not self.seats:
            raise RuntimeError('Wayland compositor exposes no input seat')
        self.roundtrip()
        self.ready = True
        self.publish()
        while not self.failed and self.lib.wl_display_dispatch(self.display) >= 0:
            pass
        raise RuntimeError(self.failed or 'Wayland compositor disconnected')

    def close(self):
        self.lib.wl_display_disconnect(self.display)


def gnome_watch(milliseconds, compositor_pid):
    import dbus
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    interface = 'org.gnome.Mutter.IdleMonitor'
    owner = bus.get_name_owner(interface)
    daemon = dbus.Interface(bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus'), 'org.freedesktop.DBus')
    if int(daemon.GetConnectionUnixProcessID(owner, timeout=3)) != compositor_pid:
        raise RuntimeError('Mutter idle service belongs to a different compositor')
    monitor = dbus.Interface(bus.get_object(owner, '/org/gnome/Mutter/IdleMonitor/Core', introspect=False), interface)
    loop, watches = GLib.MainLoop(), {'idle': None, 'active': None}
    last, error = None, None

    def publish(state):
        nonlocal last
        if state != last:
            print(state, flush=True)
            last = state

    def fail(message):
        nonlocal error
        error = str(message)
        loop.quit()

    def idle():
        if watches['active'] is None:
            watches['active'] = int(monitor.AddUserActiveWatch(timeout=3))
        # Activity can race the idle signal and registration of the active watch.
        if int(monitor.GetIdletime(timeout=3)) >= milliseconds:
            publish('idle')
        else:
            monitor.RemoveWatch(watches['active'], timeout=3)
            watches['active'] = None
            publish('active')

    def fired(watch_id):
        try:
            if watch_id == watches['idle']:
                idle()
            elif watch_id == watches['active']:
                watches['active'] = None  # Mutter removes one-shot active watches.
                publish('active')
        except Exception as exc:
            fail(exc)

    bus.add_signal_receiver(fired, signal_name='WatchFired', dbus_interface=interface,
                            bus_name=owner, path='/org/gnome/Mutter/IdleMonitor/Core')
    bus.add_signal_receiver(lambda name, old, new: fail('Mutter idle service disappeared') if old == owner else None,
                            signal_name='NameOwnerChanged', dbus_interface='org.freedesktop.DBus', arg0=interface)
    bus.call_on_disconnection(lambda _: fail('Session bus disconnected'))
    try:
        watches['idle'] = int(monitor.AddIdleWatch(dbus.UInt64(milliseconds), timeout=3))
        if int(monitor.GetIdletime(timeout=3)) >= milliseconds:
            idle()
        else:
            publish('active')
        loop.run()
        raise RuntimeError(error or 'Mutter idle monitor ended')
    finally:
        for watch in watches.values():
            if watch is not None:
                try:
                    monitor.RemoveWatch(watch, timeout=1)
                except dbus.DBusException:
                    pass


def watch(path, milliseconds):
    if not 0 < milliseconds <= 0xffffffff:
        raise ValueError('Idle interval must fit in a positive 32-bit millisecond value')
    client = WaylandIdle(path, milliseconds)
    try:
        compositor_pid = client.run()
    finally:
        client.close()
    gnome_watch(milliseconds, compositor_pid)


if __name__ == '__main__':
    try:
        watch(sys.argv[1], int(sys.argv[2]))
    except Exception as error:
        print(f'Wayland idle monitoring unavailable: {error}', file=sys.stderr)
        raise SystemExit(1)
