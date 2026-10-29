#!/bin/bash
# Target-only promotion helper. Never start pollers without the source runner's promotion barrier.
# Usage (on TO, called by runner.py): promote.sh prepare|activate|verify FROM TO
. "$(dirname "$0")/lib.sh"
eval "$HOP_REMOTE_ENV"
export PYTHONOPTIMIZE=0
(cd "$HOP_DIR" && sha256sum -c RELEASE-SHA256SUMS >/dev/null) || die 'promotion artifact digest mismatch'
ACTION="${1:-}"; FROM="${2:-}"; TO="${3:-}"
[ -n "$FROM" ] && [ -n "$TO" ] || die 'usage: promote.sh prepare|activate|verify FROM TO'
known_host "$FROM"; known_host "$TO"
is_self "$TO" || die 'target only'
ST="$HOP_STATE_DIR/staged"
OLD_FQDN="$(host_fqdn "$FROM")"; OLD_IP="$(host_ip "$FROM")"
NEW_NAME="$(main_name)"; NEW_FQDN="$NEW_NAME.$HOP_TAILNET_SUFFIX"; NEW_IP="$(host_ip "$TO")"
UIDN="$(id -u)"
case "$ACTION" in
prepare)
 [ -e "$HOP_HOME/$HOP_STANDBY_LOCK_REL" ] || die 'standby lock missing'
 [ "$(systemctl --user show hermes-gateway.service -p MainPID --value)" = 0 ] || die 'gateway already running'
 [ -z "$(docker ps -q)" ] || die 'target containers running'
 (cd "$ST" && sha256sum -c SHA256SUMS >/dev/null)
 hop_ns_exec python3 -I "$HOP_DIR/rewrite.py" scan "$HOP_HOME" "$OLD_FQDN" "$OLD_IP" > "$HOP_STATE_DIR/promotion-rewrite.tsv"
 hop_ns_exec env HOP_HOME="$HOP_HOME" python3 -I "$HOP_DIR/rewrite.py" apply "$HOP_STATE_DIR/promotion-rewrite.tsv" "$HOP_STATE_DIR/promotion-config-backup" "$OLD_FQDN=$NEW_FQDN" "$OLD_IP=$NEW_IP"
 # Source copied its drain marker during final copy; target must never inherit it.
 rm -f "$HOP_HOME/.hermes/.drain_request.json"
 # Standalone registry has no compose file. Recreate inert from its captured contract.
 if grep -q $'^standalone\twizard-local-registry\t' "$ST/compose-projects.tsv"; then
  registryimage=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["wizard-local-registry"]["image"])' "$ST/containers.json")
  # Lesson 5: container-typed lookups; a same-named volume must not satisfy a container check.
  docker container inspect wizard-local-registry >/dev/null 2>&1 || docker create --name wizard-local-registry --restart=no -p 127.0.0.1:5000:5000 -v wizard-local-registry:/var/lib/registry "$registryimage" >/dev/null
  [ "$(docker container inspect --format '{{.Image}}' wizard-local-registry)" = "$registryimage" ] || die 'standalone registry image mismatch'
 fi
 systemctl --user daemon-reload
 # Unit gate (lesson 6), before the barrier: every captured unit must exist here, except source-OS user
 # units waived in HOP_OS_ONLY_UNITS. Any other gap fails now, while the source can still auto-recover.
 python3 - "$ST" "$HOP_OS_ONLY_UNITS" "$HOP_HOST_LOCAL_UNITS" "$HOP_UNIT_SKIP_REGEX" <<'PY'
import fnmatch,json,re,subprocess,sys,pathlib
st=pathlib.Path(sys.argv[1]);OS=set(sys.argv[2].split());local=sys.argv[3].split();disposable=sys.argv[4]
skip=('docker.service','dbus.service','gpg-agent.service','hermesui.service')
units=set((st/'enabled-units.txt').read_text().split())|set((st/'running-units.txt').read_text().split())|set(json.load(open(st/'active-schedules.json')))
bad=[]
for u in sorted(units):
 if u in skip or u.startswith(('at-spi','host-hop-','hop-exempt-')) or any(fnmatch.fnmatchcase(u,g) for g in local) or re.search(disposable,u):continue
 s=subprocess.run(['systemctl','--user','show',u,'-p','LoadState','--value'],capture_output=True,text=True).stdout.strip()
 if s!='loaded' and u not in OS:bad.append(u+'='+s)
if bad:sys.exit('FATAL: captured units missing on target: '+', '.join(bad))
PY
 ;;
activate)
 # Query the source's durable barrier through the restricted, pinned raw-IP channel.
 /usr/local/bin/host-hop-recovery status | python3 -c 'import json,sys;d=json.load(sys.stdin);assert d["promotion_barrier"] and d["source_stopped"] and d["phase"]=="target-may-write"'
 [ -e "$HOP_HOME/$HOP_STANDBY_LOCK_REL" ] || die 'standby lock missing before activation'
 hop_ensure_file_binds "$ST/compose-projects.tsv"
 printf 'HOP_ROLE=active\nHOP_AGENT=%s\nHOP_TSNAME=%s\nHOP_TSIP=%s\n' "$HOP_AGENT" "$NEW_NAME" "$NEW_IP" > "$HOP_HOME/$HOP_ROLE_FILE_REL"
 rm -f "$HOP_HOME/$HOP_STANDBY_LOCK_REL"
 systemctl --user enable docker.service
 # Start precisely the captured compose service set, with no implicit dependencies.
 HOP_EXPECT_MACHINE="$(hv MACHINE "$TO")" python3 "$HOP_DIR/check-startup.py" "$ST" --activate
 # Postgres data identity rewrite after DB ready; no schedule starts yet.
 if [ -n "${HOP_PG_CONTAINER:-}" ]; then
  for _ in $(seq 1 40); do docker exec "$HOP_PG_CONTAINER" pg_isready -U "$HOP_PG_USER" >/dev/null && break; sleep 2; done
  # SQL on stdin so psql interpolates the quoted :'vars' (it does not for -c).
  echo "update app set config=replace(replace(config::text,:'old_fqdn',:'new_fqdn'),:'old_ip',:'new_ip')::jsonb;" | \
   docker exec -i "$HOP_PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$HOP_PG_USER" -d "$HOP_PG_DB" \
    -v old_fqdn="$OLD_FQDN" -v new_fqdn="$NEW_FQDN" -v old_ip="$OLD_IP" -v new_ip="$NEW_IP" >/dev/null
 fi
 # Exact enabled state, including paused timers, is retained from frozen source inventory.
 while read -r u; do
  hop_unit_skipped "$u" && continue
  [ "$(systemctl --user show "$u" -p LoadState --value)" = loaded ] || continue  # source-OS unit, gated in prepare
  systemctl --user enable "$u" >/dev/null 2>&1 || { [ "$(systemctl --user is-enabled "$u" 2>/dev/null || true)" = static ] || die "enable failed $u"; }
 done < "$ST/enabled-units.txt"
 while read -r u; do
  if [ "$u" = hermesui.service ]; then systemctl --user start hermesui-launcher.service; continue; fi
  hop_unit_skipped "$u" && continue
  systemctl --user start "$u"
 done < "$ST/running-units.txt"
 for u in ${HOP_SYSTEM_UNITS:-}; do sudo -n systemctl enable --now "$u"; done
 python3 - "$ST/active-schedules.json" <<'PY'
import json,subprocess,sys
for u in json.load(open(sys.argv[1])):
 if subprocess.run(['systemctl','--user','show',u,'-p','LoadState','--value'],capture_output=True,text=True).stdout.strip()!='loaded':continue
 subprocess.run(['systemctl','--user','start',u],check=True)
PY
 # Machine-local fixups (e.g. a target-owned job that called the old main over SSH; lesson 7).
 if [ -n "$HOP_POST_ACTIVATE_HOOK" ]; then "$HOP_POST_ACTIVATE_HOOK" "$FROM" "$TO"; fi
 ;;
verify)
 # Lesson 2: services listen a few seconds after systemd reports them started; wait (bounded) before judging.
 for _ in $(seq 1 60); do curl -fsS -m 3 http://127.0.0.1:8642/health >/dev/null 2>&1 && curl -fsS -m 3 http://127.0.0.1:8797/health >/dev/null 2>&1 && break; sleep 2; done
 systemctl --user is-active --quiet hermes-gateway.service
 [ "$(systemctl --user show host-hop-history.service -p MainPID --value 2>/dev/null)" = 0 ] || die 'preview history active'
 [ ! -e "/run/user/$UIDN/host-hop/test-mode.active" ] || die 'preview marker remains'
 [ ! -e "$HOP_HOME/$HOP_STANDBY_LOCK_REL" ] || die 'standby guard remains'
 curl --fail --silent --show-error --max-time 10 http://127.0.0.1:8642/health >/dev/null
 curl --fail --silent --show-error --max-time 10 http://127.0.0.1:8797/health >/dev/null
 RESOLVE="$NEW_FQDN:$HOP_SHELL_PORT:$NEW_IP"
 curl --fail --silent --show-error --max-time 20 --resolve "$RESOLVE" "https://$NEW_FQDN:$HOP_SHELL_PORT/wizard-os-home/" >/dev/null
 python3 - "https://$NEW_FQDN:$HOP_SHELL_PORT/wizard/hermes/api/" "$RESOLVE" <<'PY'
import json,subprocess,sys,urllib.parse
base,resolve=sys.argv[1],sys.argv[2]
def get(path):
 return json.loads(subprocess.check_output(['curl','--fail','--silent','--show-error','--max-time','20','--resolve',resolve,base+path],text=True))
d=get('sessions?view=list&limit=2');assert d.get('data') and isinstance(d['data'],list)
sid=d['data'][0]['id'];m=get('sessions/'+urllib.parse.quote(sid,safe='')+'/messages?limit=2');assert isinstance(m['data'],list)
print('PASS authenticated TLS hostname, shell, actual native list and messages')
PY
 owner=$(systemctl --user show hermes-gateway.service -p MainPID --value)
 ss -ltnpH sport = :8642 | grep -q "pid=$owner," || die 'native API listener is not owned by promoted gateway'
 ;;
*) die 'usage: promote.sh prepare|activate|verify FROM TO';;
esac
