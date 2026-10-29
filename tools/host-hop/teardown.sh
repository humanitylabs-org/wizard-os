#!/usr/bin/env bash
# Standby-only preview teardown; clients must be proven dead before lifting egress fences.
. "$(dirname "$0")/lib.sh"
eval "$HOP_REMOTE_ENV"
RUN="/run/user/$(id -u)/host-hop"
RTU="/run/user/$(id -u)/systemd/user"
ST="$HOP_STATE_DIR/staged"

unit_props() {
  local scope="$1" unit="$2" props
  # systemctl show may return nonzero for a collected transient unit, but still
  # supplies the authoritative not-found/inactive/MainPID=0 after-image.
  if props=$($scope show "$unit" -p MainPID -p ActiveState -p LoadState -p ControlGroup); then :
  else
    [[ "$props" == *'LoadState=not-found'* ]] || die "cannot inspect $unit"
  fi
  printf '%s\n' "$props"
}
unit_cold() {
  local scope="$1" unit="$2" props cg p
  props=$(unit_props "$scope" "$unit") || return 2
  if [[ "$unit" = *.service ]]; then grep -qx 'MainPID=0' <<<"$props" || return 1; fi
  grep -Eq '^ActiveState=(inactive|failed)$' <<<"$props" || return 1
  cg=$(sed -n 's/^ControlGroup=//p' <<<"$props")
  if [ -n "$cg" ] && [ -d "/sys/fs/cgroup$cg" ]; then
    while IFS= read -r p; do [ -z "$(<"$p")" ] || return 1; done < <(find "/sys/fs/cgroup$cg" -name cgroup.procs)
  fi
  return 0
}
stop_unit() {
  local scope="$1" unit="$2"
  if unit_cold "$scope" "$unit"; then return 0; else local rc=$?; [ "$rc" = 1 ] || die "cannot prove unit state: $unit"; fi
  if $scope stop "$unit"; then :
  elif [ "$scope" = 'systemctl --user' ] && [ "$unit" = hermesui.service ]; then
    # The protected UI rejects manual stop. Validate the exact running provider
    # and process before using the existing exact-unit TERM maintenance path.
    [ -n "${HOP_UI_CMDLINE:-}" ] || die 'HOP_UI_CMDLINE unset; refusing to signal hermesui.service'
    python3 - "$HOP_UI_CMDLINE" <<'PY'
import os,pathlib,subprocess,sys
u=os.getuid()
s=subprocess.check_output(['systemctl','--user','show','hermesui.service','-p','MainPID','-p','ControlGroup','-p','FragmentPath'],text=True)
p=dict(l.split('=',1) for l in s.splitlines());pid=int(p['MainPID'])
assert pid>0 and p['ControlGroup']==f'/user.slice/user-{u}.slice/user@{u}.service/app.slice/hermesui.service'
assert p['FragmentPath']==f'/run/user/{u}/systemd/transient/hermesui.service'
a=pathlib.Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')[:-1]
assert a==[x.encode() for x in sys.argv[1].split()]
assert pathlib.Path(f'/proc/{pid}/cgroup').read_text().strip()=='0::'+p['ControlGroup']
subprocess.run(['systemctl','--user','kill','--kill-who=all','--signal=TERM','hermesui.service'],check=True)
PY
  else
    # A stop can return failure after quiescence. Never ignore a live after-image.
    unit_cold "$scope" "$unit" || die "stop failed: $unit"
  fi
  local i
  for i in {1..90}; do if unit_cold "$scope" "$unit"; then return 0; fi; sleep 1; done
  die "unit did not quiesce: $unit"
}
preview_stop() {
  [ "$(sed -n 's/^HOP_ROLE=//p' "$HOP_HOME/$HOP_ROLE_FILE_REL")" = standby ] || die 'teardown requires standby role'
  [ -e "$HOP_HOME/$HOP_STANDBY_LOCK_REL" ] || die 'teardown requires standby guard'
  unit_cold 'systemctl --user' hermes-gateway.service || die 'standby gateway is live'
  # Stop launchers first, then listeners. Machine-local units (HOP_TEST_EGRESS_EXEMPT) are never stopped.
  local u p kind wd files envs svcs ipt props running
  stop_unit 'systemctl --user' hermesui-launcher.service
  stop_unit 'systemctl --user' host-hop-history.service
  for u in $HOP_TEST_UNITS; do
    case " $HOP_TEST_EGRESS_EXEMPT " in *" $u "*) die "native unit in preview stop set: $u";; esac
    stop_unit 'systemctl --user' "$u"
  done
  for u in ${HOP_TEST_SYSTEM_UNITS:-}; do stop_unit 'sudo -n systemctl' "$u"; done
  # Only destroy captured preview projects, never stop arbitrary native containers.
  if [ -f "$ST/compose-projects.tsv" ]; then
    while IFS=$'\t' read -r kind p wd files envs svcs; do
      [ "$kind" = project ] || continue
      local args=(--project-directory "$wd") f
      for f in ${files//,/ }; do args+=(-f "$f"); done
      for f in ${envs//,/ }; do if [ -f "$f" ]; then args+=(--env-file "$f"); fi; done
      docker compose -p "$p" "${args[@]}" down --remove-orphans >/dev/null
    done < "$ST/compose-projects.tsv"
  fi
  running=$(docker ps -q) || die 'cannot inspect containers'
  [ -z "$running" ] || die 'containers remain; refusing firewall removal (unknown/native containers are preserved)'
  running=$(cat "$HOP_STATE_DIR/installed-units.txt") || die 'installed unit inventory missing'
  for u in $running; do
    case "$u" in docker.service) continue;; *.service|*.timer|*.path|*.socket) ;; *) continue;; esac
    case " $HOP_TEST_EGRESS_EXEMPT " in *" $u "*) continue;; esac
    unit_cold 'systemctl --user' "$u" || die "still active after stop: $u"
  done
  running=$(ss -ltnH sport = :8797) || die 'cannot inspect UI listener'
  [ -z "$running" ] || die 'preview UI listener remains'
  running=$(ss -ltnH sport = :8642) || die 'cannot inspect history listener'
  [ -z "$running" ] || die 'preview history listener remains'
  hop_ensure_file_binds "$ST/compose-projects.tsv"
  # Restore files only after quiescence. Retain backups on any restore failure.
  if [ -d "$HOP_STATE_DIR/test-rewrite-backup" ]; then
    hop_ns_exec env HOP_HOME="$HOP_HOME" python3 -I "$HOP_DIR/rewrite.py" restore "$HOP_STATE_DIR/test-rewrite-backup"
    rm -rf "$HOP_STATE_DIR/test-rewrite-backup"
  fi
  if [ -e "$RUN/test-serve" ]; then timeout 25 tailscale serve reset </dev/null; rm -f "$RUN/test-serve"; fi
  rm -rf "$RUN/test-allow" "$RUN/test-projects"
  sudo -n rm -rf /run/host-hop/test-allow
  rm -f "$RTU/host-hop-history.service"
  rm -rf "$RUN/history-api-key" "$RUN/history-runtime"
  rm -f "$RUN/shell-nginx.read-only.conf" "$RUN/shell-nginx.before-history.conf"
  # Inspect the full ruleset: an absent chain is an idempotent success, not a
  # reason to suppress arbitrary iptables errors. All clients are stopped first.
  for ipt in iptables ip6tables; do
    props=$(sudo -n "$ipt" -S)
    if grep -q '^-N HOP-TEST$' <<<"$props"; then
      while sudo -n "$ipt" -C OUTPUT -j HOP-TEST 2>/dev/null; do sudo -n "$ipt" -D OUTPUT -j HOP-TEST; done
      sudo -n "$ipt" -F HOP-TEST
      sudo -n "$ipt" -X HOP-TEST
    fi
    props=$(sudo -n "$ipt" -S)
    if grep -q 'HOP-TEST' <<<"$props"; then die "preview firewall remains: $ipt"; fi
  done
  for u in $HOP_TEST_EGRESS_EXEMPT; do rm -f "$RTU/$u.d/zz-host-hop-test.conf"; done
  stop_unit 'systemctl --user' hop-exempt-anchor.service
  rm -f "$RTU/hopexempt.slice"
  systemctl --user daemon-reload
  sudo -n systemctl daemon-reload
  rm -f "$RUN/test-mode.active"
  [ -e "$HOP_HOME/$HOP_STANDBY_LOCK_REL" ] || die 'standby guard lost'
  log 'test mode stopped; standby cold/fenced; machine-local units preserved'
}
if [ "${BASH_SOURCE[0]}" = "$0" ]; then preview_stop; fi
