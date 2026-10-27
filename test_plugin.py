"""Plugin packaging checks; live dummy-service testing is explicitly opt-in."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
import unittest
from unittest import mock

ROOT = Path(__file__).parent
loader = importlib.machinery.SourceFileLoader('plugin_service', str(ROOT / 'plugin-service'))
spec = importlib.util.spec_from_loader(loader.name, loader)
service = importlib.util.module_from_spec(spec)
loader.exec_module(service)


class PluginTests(unittest.TestCase):
    def test_manifest_and_opening(self):
        manifest = json.loads((ROOT / 'manifest.json').read_text())
        self.assertEqual(manifest['id'], 'dagelf.vampireslayer')
        self.assertEqual(manifest['kinds'], ['service', 'bar-widget'])
        self.assertTrue((ROOT / manifest['entryPoints']['service']).is_file())
        opening = "Chrome or Firefox eating CPU while you're out for lunch, even when they have nothing to do? Vampire Slayer to the rescue."
        self.assertIn(opening, manifest['description'])
        self.assertIn(opening, (ROOT / 'README.md').read_text())

    def test_command_has_cleanup_and_only_desktop_environment(self):
        path = Path('/tmp/plugin space%name$literal')
        command = service.service_command(path, {'DISPLAY': ':9', 'SECRET': 'not-for-unit'})
        self.assertIn('--collect', command)
        self.assertIn('--setenv=DISPLAY', command)
        self.assertFalse(any('SECRET' in part for part in command))
        self.assertEqual(command[-5:], ['/usr/bin/python3', str(path / 'background-suspend'), 'run', '--minutes', '15'])
        cleanup = next(p for p in command if p.startswith('--property=ExecStopPost='))
        self.assertIn('space%name$$literal', cleanup)
        self.assertTrue(cleanup.endswith(' resume'))
        self.assertNotIn('sh', command)

    def test_start_stops_previous_unit_before_launching(self):
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 3 if 'is-active' in command else 0)

        with mock.patch.object(sys, 'argv', ['plugin-service', 'start']), \
             mock.patch.object(service.subprocess, 'run', side_effect=run):
            service.main()
        self.assertIn('is-active', calls[0])
        self.assertEqual(calls[1], ['systemctl', '--user', 'stop', service.UNIT])
        self.assertEqual(calls[2][0], 'systemd-run')

    def test_active_legacy_service_is_not_changed(self):
        with mock.patch.object(sys, 'argv', ['plugin-service', 'start']), \
             mock.patch.object(service.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            with self.assertRaises(RuntimeError):
                service.main()
        self.assertEqual(run.call_count, 1)

    def test_explicit_config_takes_precedence_over_user_copy(self):
        from test_background_suspend import app
        with tempfile.TemporaryDirectory() as directory:
            user = Path(directory) / 'user.toml'
            user.write_text('')
            for options, expected in (([], user), (['--config', str(app.CONFIG)], app.CONFIG)):
                with mock.patch.object(sys, 'argv', ['background-suspend', 'resume', *options]), \
                     mock.patch.object(app, 'USER_CONFIG', user), \
                     mock.patch.object(app, 'load_policy', wraps=app.load_policy) as load, \
                     mock.patch.object(app, 'app_signal'):
                    self.assertEqual(app.main(), 0)
                    load.assert_called_once_with(expected)

    @unittest.skipUnless(os.environ.get('VAMPIRESLAYER_TEST_SYSTEMD') == '1',
                         'opt-in live systemd test with disposable dummy process')
    def test_live_systemd_stop_and_crash_cleanup(self):
        # No browser names or suspension code: only a waiting Python process.
        with tempfile.TemporaryDirectory(prefix='vampire service%$ ', dir=ROOT) as directory:
            root = Path(directory)
            marker = root / 'resumed'
            (root / 'background-suspend').write_text(
                'import pathlib,signal,sys\n'
                'if sys.argv[1]=="resume":\n'
                ' pathlib.Path(__file__).with_name("resumed").touch()\n'
                'else:\n signal.pause()\n')
            unit = 'vampireslayer-test-' + uuid.uuid4().hex + '.service'
            command = service.service_command(root, {})
            command[command.index('--unit=' + service.UNIT)] = '--unit=' + unit
            try:
                for crash in (False, True):
                    subprocess.run(command, check=True, capture_output=True)
                    if crash:
                        subprocess.run(['systemctl', '--user', 'kill', '--signal=KILL',
                                        '--kill-whom=main', unit], check=True)
                    subprocess.run(['systemctl', '--user', 'stop', unit], check=True)
                    self.assertTrue(marker.exists(), 'resume cleanup did not run')
                    marker.unlink()
            finally:
                subprocess.run(['systemctl', '--user', 'stop', unit], capture_output=True)

    def test_edit_config_preserves_existing_file_and_uses_omarchy_editor(self):
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}), \
             mock.patch.object(service.os, 'execvp') as launch:
            service.edit_config()
            path = Path(directory) / 'vampireslayer/background-suspend.toml'
            self.assertEqual(path.read_text(), (ROOT / 'background-suspend.toml').read_text())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.write_text('ignore = ["my-app"]\n')
            service.edit_config()
            self.assertEqual(path.read_text(), 'ignore = ["my-app"]\n')
            launch.assert_called_with('omarchy-launch-editor', ['omarchy-launch-editor', str(path)])

    def test_failed_stop_cannot_start_a_second_mode(self):
        def run(command, **kwargs):
            if 'is-active' in command:
                return subprocess.CompletedProcess(command, 3)
            if 'stop' in command:
                return subprocess.CompletedProcess(command, 1, '', 'Stop denied')
            if 'show' in command:
                return subprocess.CompletedProcess(command, 0, 'loaded\n', '')
            self.fail('A new service must not start after failed stop')
        with mock.patch.object(sys, 'argv', ['plugin-service', 'gaming']), \
             mock.patch.object(service.subprocess, 'run', side_effect=run):
            with self.assertRaisesRegex(RuntimeError, 'Stop denied'):
                service.main()

    def test_gaming_runs_managed_backend_with_cleanup(self):
        command = service.service_command(mode='gaming')
        self.assertIn('gaming-run', command)
        self.assertTrue(any(x.startswith('--property=ExecStopPost=') for x in command))

    def test_stop_needs_no_checkout_files(self):
        qml = (ROOT / 'Service.qml').read_text()
        self.assertIn('Quickshell.execDetached(["systemctl", "--user", "stop", "vampireslayer.service"])', qml)


if __name__ == '__main__':
    unittest.main()
