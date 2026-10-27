"""Gaming mode operates only on disposable browser-named fixture processes."""
import io
import os
import unittest
from unittest import mock
import test_background_suspend as fixtures
app = fixtures.app


class GamingTests(unittest.TestCase):
    browser = fixtures.IdleTests.browser
    assert_state = fixtures.IdleTests.assert_state

    def test_no_media_immediate_suspend_then_exit_resumes(self):
        display = f':gaming-{os.getpid()}'
        pids = self.browser(display)
        policy = app.load_policy()
        policy.suspend_media = ['*']
        send = app.app_signal

        def pause():
            self.assert_state(pids, True)
            raise SystemExit(0)

        with mock.patch.object(app, 'app_signal', side_effect=lambda name, **kw: send(name, display, **kw)), \
             mock.patch.object(app.signal, 'pause', side_effect=pause):
            with self.assertRaises(SystemExit):
                app.gaming_watch(policy)
        self.assert_state(pids, False)

    def test_media_changes_and_monitor_failure_resume(self):
        display = f':gaming-media-{os.getpid()}'
        playing = self.browser(display)
        idle = self.browser(display)
        ignored = self.browser(display, name='chromium')
        policy = app.load_policy()
        policy.ignore = ['chromium']
        send = app.app_signal
        calls = []

        def apply(name, **kwargs):
            send(name, display, **kwargs)
            calls.append((name, kwargs.get('playing')))
            current = kwargs.get('playing')
            self.assert_state(ignored, False)
            self.assert_state(playing, name == 'SIGSTOP' and current is not None and playing[0] not in current)
            self.assert_state(idle, name == 'SIGSTOP' and current is not None)

        media = mock.Mock(stdout=io.BytesIO(f'[{playing[0]}]\n[]\nnull\n'.encode()))
        with mock.patch.object(app.subprocess, 'Popen', return_value=media), \
             mock.patch.object(app, 'app_signal', side_effect=apply):
            with self.assertRaisesRegex(RuntimeError, 'Media watcher ended'):
                app.gaming_watch(policy)
        self.assertEqual(calls, [('SIGSTOP', {playing[0]}), ('SIGSTOP', set()), ('SIGSTOP', None), ('SIGCONT', None)])
        media.terminate.assert_called_once()
        self.assert_state(playing + idle, False)

    def test_suspension_failure_still_resumes(self):
        policy = app.load_policy()
        policy.suspend_media = ['*']
        with mock.patch.object(app, 'app_signal', side_effect=[RuntimeError('signal failed'), None]) as send:
            with self.assertRaisesRegex(RuntimeError, 'signal failed'):
                app.gaming_watch(policy)
        self.assertEqual([c.args[0] for c in send.call_args_list], ['SIGSTOP', 'SIGCONT'])


if __name__ == '__main__':
    unittest.main()
