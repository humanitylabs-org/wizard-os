#!/usr/bin/python3
"""Exercise exact Bash teardown body in disposable dependency fixtures, no real services."""
import os,pathlib,subprocess,tempfile,unittest
D=pathlib.Path(__file__).resolve().parent
class Teardown(unittest.TestCase):
 def exercise(self,mode='cold',repeat=False):
  with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as t:
   p=pathlib.Path(t);(p/'home/.wizard-os').mkdir(parents=True);(p/'home/.wizard-os/host-role').write_text('HOP_ROLE=standby\n');(p/'home/.wizard-os/standby.lock').touch()
   for n in ['state/staged','run/test-allow','rtu','units']:(p/n).mkdir(parents=True)
   (p/'state/installed-units.txt').write_text('preview.service\nlast-inactive.service\nschedule.timer\nignored.service.d\n')
   (p/'state/staged/compose-projects.tsv').write_text('project\tpreview\t/fixture\t/fixture/compose.yml\t\tweb\n')
   for n in ['test-mode.active','test-serve','history-api-key']:(p/'run'/n).touch()
   (p/'units/host-hop-history.service').write_text('active' if mode in ('partial','stop-fail') else 'inactive')
   if mode in ('partial','restore-fail'):(p/'state/test-rewrite-backup').mkdir()
   for n in ['iptables','ip6tables']:
    if mode!='cold':(p/n).touch()
   body=(D/'teardown.sh').read_text();body=body[body.index('unit_props()'):body.index('if [ "${BASH_SOURCE[0]}"')]
   prefix=r'''
set -Eeuo pipefail
P="$1"; MODE="$2"; HOP_HOME="$P/home"; HOP_DIR="$P"; HOP_STATE_DIR="$P/state"; HOP_ROLE_FILE_REL=.wizard-os/host-role; HOP_STANDBY_LOCK_REL=.wizard-os/standby.lock
RUN="$P/run"; RTU="$P/rtu"; ST="$P/state/staged"; HOP_TEST_UNITS=preview.service; HOP_TEST_SYSTEM_UNITS=; HOP_TEST_EGRESS_EXEMPT='example-local-scan.service example-local-relay.service'
die() { printf 'FATAL %s\n' "$*" >&2; exit 1; }
log() { printf '%s\n' "$*"; }
systemctl() {
 echo "systemctl $*" >> "$P/calls"
 [ "${1:-}" != --user ] || shift
 case "$1" in
 show)
  u="$2"; state=inactive; [ ! -f "$P/units/$u" ] || state=$(<"$P/units/$u")
  [ "$MODE" != query-fail ] || return 1
  if [ "$state" = active ]; then printf 'MainPID=99\nLoadState=loaded\nActiveState=active\nControlGroup=\n'; else printf 'MainPID=0\nLoadState=not-found\nActiveState=inactive\nControlGroup=\n'; return 1; fi;;
 stop) [ "$MODE" != stop-fail ] || return 1; echo inactive > "$P/units/$2";;
 daemon-reload) :;;
 *) return 2;;
 esac
}
docker() {
 echo "docker $*" >> "$P/calls"
 if [ "$1" = compose ]; then [ "$MODE" != compose-fail ]; return; fi
 [ "$MODE" != docker-fail ] || return 1
 if [ "$MODE" = unknown-container ]; then echo native-container; fi
 return 0
}
ss() { [ "$MODE" != listener ] || echo LISTEN; }
hop_ensure_file_binds() { :; }
hop_ns_exec() { echo restore >> "$P/calls"; [ "$MODE" != restore-fail ]; }
timeout() { echo serve-reset >> "$P/calls"; }
sudo() {
 [ "$1" != -n ] || shift
 case "$1" in
 systemctl) shift; systemctl "$@";;
 rm) echo system-allow-removed >> "$P/calls";;
 iptables|ip6tables)
  ipt="$1"; shift; echo "$ipt $*" >> "$P/calls"
  [ "$MODE" != firewall-fail ] || return 1
  case "$1" in
   -S) if [ -f "$P/$ipt" ]; then echo '-N HOP-TEST'; fi;;
   -C) return 1;;
   -F|-D) :;;
   -X) rm "$P/$ipt";;
   *) return 2;;
  esac;;
 *) return 2;;
 esac
}
'''
   script=p/'fixture.sh';script.write_text(prefix+'\n'+body+'\npreview_stop\n'+('preview_stop\n' if repeat else ''))
   r=subprocess.run(['bash',str(script),str(p),mode],capture_output=True,text=True,timeout=10)
   return r,(p/'calls').read_text(),{n:(p/n).exists() for n in ['iptables','ip6tables','run/test-mode.active','run/history-api-key','state/test-rewrite-backup','home/.wizard-os/standby.lock']}
 def test_repeated_cold_and_collected_history_succeed(self):
  r,c,s=self.exercise(repeat=True);self.assertEqual(r.returncode,0,r.stderr);self.assertFalse(s['run/test-mode.active']);self.assertFalse(s['run/history-api-key']);self.assertTrue(s['home/.wizard-os/standby.lock']);self.assertNotIn('stop example-local-scan',c);self.assertNotIn('stop example-local-relay',c)
 def test_partial_teardown_stops_history_restores_then_unfences(self):
  r,c,s=self.exercise('partial',True);self.assertEqual(r.returncode,0,r.stderr);self.assertIn('stop host-hop-history.service',c);self.assertLess(c.index('stop host-hop-history.service'),c.index('restore'));self.assertLess(c.index('restore'),c.index('iptables -X'));self.assertFalse(s['state/test-rewrite-backup']);self.assertFalse(s['iptables']);self.assertFalse(s['ip6tables'])
 def test_failure_boundaries_preserve_fences(self):
  for mode in ['stop-fail','query-fail','docker-fail','unknown-container','listener','compose-fail','restore-fail','firewall-fail']:
   with self.subTest(mode=mode):
    r,c,s=self.exercise(mode);self.assertNotEqual(r.returncode,0,r.stdout);self.assertTrue(s['iptables']);self.assertTrue(s['run/test-mode.active']);self.assertNotIn('iptables -X',c);self.assertTrue(s['home/.wizard-os/standby.lock'])
 def test_original_errexit_assignment_reproduced(self):
  r=subprocess.run(['bash','-ec','running=$(for u in inactive; do [ "$u" = active ] && echo "$u"; done); echo unreachable'],capture_output=True,text=True);self.assertEqual(r.returncode,1);self.assertEqual(r.stdout,'')
if __name__=='__main__':unittest.main(verbosity=2)
