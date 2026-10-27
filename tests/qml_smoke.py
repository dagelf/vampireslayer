"""Run on Omarchy: python3 tests/qml_smoke.py. Isolated fake backend; no app suspension."""
from pathlib import Path
import os, shutil, subprocess, tempfile
source=Path(__file__).resolve().parent.parent
omarchy=Path(os.environ.get('OMARCHY_PATH', '/usr/share/omarchy'))
quickshell=os.environ.get('QUICKSHELL', 'quickshell')
with tempfile.TemporaryDirectory(prefix='vampire-qml-') as directory:
 root=Path(directory)
 for name in ['Service.qml','Widget.qml','PixelVampire.qml']:
  shutil.copy2(source/name,root/name)
 os.mkfifo(root/'events')
 (root/'runtime').mkdir(mode=0o700)
 for name in ('Commons', 'Ui'):
  (root/name).symlink_to(omarchy/'shell'/name, target_is_directory=True)
 (root/'plugin-service').write_text('''import os,sys,json
from pathlib import Path
root=Path(__file__).parent
mode=sys.argv[1]
if mode=='observe':
 print(json.dumps({'mode':'watching','activeState':'active'}),flush=True)
 with os.fdopen(os.open(root/'events',os.O_RDWR),'r') as events:
  for line in events: print(line.strip(),flush=True)
else:
 with (root/'actions').open('a') as log: log.write(mode+'\\n')
 if mode!='edit-config':
  with (root/'events').open('w') as stream: stream.write(json.dumps({'mode':mode,'activeState':'inactive' if mode=='suspended' else 'active'})+'\\n')
''')
 (root/'shell.qml').write_text('''import QtQuick
import Quickshell
ShellRoot {
 id: root
 property int step: 0
 property int ticks: 0
 function check(value, message) { if (!value) { console.error("TEST FAILURE:", message); Qt.exit(1); } }
 Service { id: service }
 QtObject { id: facade; function serviceFor(id) { return service; } }
 FloatingWindow {
  visible: true; implicitWidth: 200; implicitHeight: 100
  Widget { id: widget; shell: facade; anchors.centerIn: parent }
 }
 function button() { for (let i=0;i<widget.children.length;i++) if (typeof widget.children[i].triggerPress === "function") return widget.children[i]; return null; }
 Timer {
  interval: 50; running: true; repeat: true
  onTriggered: {
   root.ticks++;
   if (root.ticks > 150) { root.check(false,"timed out at step " + root.step + " " + service.error); return; }
   if (!service.initialized || service.busy) return;
   if (root.step === 0) { root.check(service.mode === "watching","initial mode"); service.cycle(); root.step=1; }
   else if (root.step === 1 && service.mode === "gaming") { service.cycle(); root.step=2; }
   else if (root.step === 2 && service.mode === "suspended") { service.cycle(); root.step=3; }
   else if (root.step === 3 && service.mode === "watching") { root.check(!!root.button(),"button exists"); root.button().triggerPress(Qt.LeftButton); root.button().triggerPress(Qt.LeftButton); root.step=4; delay.start(); }
   else if (root.step === 5 && service.mode === "gaming") { root.check(service.setMode("invalid") === "invalid mode","invalid mode rejected"); console.log("PASS: QML mode cycle, double-click edit without cycling, single-click gaming"); Qt.quit(); }
  }
 }
 Timer {
  id: delay; interval: 800
  onTriggered: { root.check(service.mode === "watching","double click changed mode"); root.button().triggerPress(Qt.LeftButton); root.step=5; }
 }
}
''')
 env={**os.environ,'QT_QPA_PLATFORM':'offscreen','XDG_RUNTIME_DIR':str(root/'runtime')}
 result=subprocess.run(['dbus-run-session','--',quickshell,'--path',str(root/'shell.qml')],env=env,capture_output=True,text=True,timeout=20)
 print(result.stdout); print(result.stderr)
 if (root/'actions').exists():
  actions=(root/'actions').read_text().splitlines(); print('Actions:',actions)
  assert actions==['gaming','suspended','watching','edit-config','gaming'],actions
 assert result.returncode==0,result.returncode
 assert 'PASS: QML' in result.stdout+result.stderr
