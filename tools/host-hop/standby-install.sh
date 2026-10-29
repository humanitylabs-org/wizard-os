#!/usr/bin/env bash
# host-hop phase 3: wire a synced STANDBY so it can take over, while keeping everything stopped.
# Usage (on the ACTIVE host):  standby-install.sh TARGET
#   Pushes these scripts to TARGET, runs `standby-install.sh --local` there, then ships docker images,
#   named volumes and the Postgres base backup with sync.sh.
# Idempotent. Never enables a staged unit, never creates an app container, never touches tailscale serve.
. "$(dirname "$0")/lib.sh"

guard_dropin() {  # print the standby guard drop-in
  # Triggering conditions (|): the unit may start only if the host is NOT a standby, or test-mode put an
  # allow file for exactly this unit. Units in HOP_TEST_NEVER_UNITS never get an allow file.
  printf '[Unit]\n# host-hop standby guard\nConditionPathExists=|!%%h/%s\nConditionPathExists=|%%t/host-hop/test-allow/%%n\n' \
    "$HOP_STANDBY_LOCK_REL"
}

local_install() {
  cd "$HOP_HOME"
  eval "$HOP_REMOTE_ENV"
  ROLE=$(sed -n 's/^HOP_ROLE=//p' "$HOP_HOME/$HOP_ROLE_FILE_REL" 2>/dev/null || true)
  [ "$ROLE" = standby ] || die "host-role is '$ROLE', expected standby; refusing"
  touch "$HOP_HOME/$HOP_STANDBY_LOCK_REL"
  ST="$HOP_STATE_DIR/staged"; [ -d "$ST/systemd-user" ] || die "nothing staged; run sync.sh first"
  REPORT="$HOP_STATE_DIR/standby-install-$(ts).log"; exec > >(tee -a "$REPORT") 2>&1

  # --- kernel bits rootless docker needs (persisted) ---
  sudo -n modprobe -a ip_tables iptable_nat iptable_filter nf_nat xt_MASQUERADE br_netfilter overlay 2>/dev/null || true
  printf 'ip_tables\niptable_nat\niptable_filter\nnf_nat\nxt_MASQUERADE\noverlay\n' | sudo -n tee /etc/modules-load.d/host-hop-docker.conf >/dev/null

  # --- user units: install files, add the standby guard to each, enable nothing ---
  U="$HOP_HOME/.config/systemd/user"; mkdir -p "$U"
  installed="$HOP_STATE_DIR/installed-units.txt"; : > "$installed"
  for f in "$ST/systemd-user"/*; do
    n=$(basename "$f")
    case "$n" in *.wants|*.requires) continue;; esac
    case " $HOP_TARGET_OWNED " in *"/.config/systemd/user/$n "*) log "skip target-owned $n"; continue;; esac
    if [ -d "$f" ]; then mkdir -p "$U/$n"; cp -a "$f"/. "$U/$n"/; else cp -a "$f" "$U/$n"; fi
    echo "$n" >> "$installed"
  done
  # guard: every staged unit and every staged drop-in dir (covers transient units such as hermesui.service)
  for n in $(sed -e 's/\.d$//' "$installed" | sort -u); do
    case "$n" in docker.service) continue;; *.service|*.timer|*.path|*.socket|*.target) ;; *) continue;; esac
    mkdir -p "$U/$n.d"; guard_dropin > "$U/$n.d/zz-host-hop-standby.conf"
  done
  systemctl --user daemon-reload
  # nothing staged may be enabled or running
  for n in $(grep -E '\.(service|timer|path|socket)$' "$installed"); do
    [ "$n" = docker.service ] && continue
    e=$(systemctl --user is-enabled "$n" 2>/dev/null || true); a=$(systemctl --user is-active "$n" 2>/dev/null || true)
    case "$e" in enabled|enabled-runtime|linked) systemctl --user disable "$n" >/dev/null 2>&1 || true; log "disabled $n";; esac
    [ "$a" = active ] && die "$n is active on the standby; investigate"
  done
  log "units installed: $(wc -l < "$installed"), all disabled, guard=$HOP_STANDBY_LOCK_REL"

  # --- rootless docker daemon (empty data root). Started, not enabled: a reboot leaves the standby cold. ---
  if ! docker info >/dev/null 2>&1; then
    systemctl --user start docker.service
    for _ in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 2; done
  fi
  docker info >/dev/null 2>&1 || die "rootless docker did not start"
  [ -z "$(docker ps -aq)" ] || log "WARN: containers exist on standby: $(docker ps -a --format '{{.Names}}' | tr '\n' ' ')"
  log "docker: $(docker version --format '{{.Server.Version}}') rootless, $(docker ps -q | wc -l) running"

  # --- virtualenvs: rebuilt from the source's freeze lists, same paths, same interpreter ---
  for r in "$ST/venvs"/*.txt; do
    [ -f "$r" ] || continue
    v=$(sed -n 's/^#venv //p' "$r"); home=$(sed -n 's/^#cfg home = //p' "$r"); ver=$(sed -n 's/^#cfg version\(_info\)\? = //p' "$r" | head -1)
    [ -n "$v" ] || continue
    sudo_cmd=""; case "$v" in "$HOP_HOME"/*) ;; *) sudo_cmd="sudo -n";; esac
    mm=$(printf '%s' "$ver" | cut -d. -f1-2); py=""
    for c in "$home/python$mm" "$home/python$ver"; do [ -x "$c" ] && { py="$c"; break; }; done
    [ -z "$py" ] && [ -x "$home/python3" ] && "$home/python3" -c "import sys;sys.exit(0 if '%d.%d'%sys.version_info[:2]=='$mm' else 1)" 2>/dev/null && py="$home/python3"
    [ -n "$py" ] || py="$mm"   # let uv provide a managed interpreter of the same version
    if [ -x "$v/bin/python" ] && cmp -s "$r" "$v/.host-hop-recipe" 2>/dev/null; then log "venv current: $v"; continue; fi
    log "venv build: $v (python $py)"
    # Built in place (venv scripts embed absolute paths). Safe: the standby runs nothing from it yet.
    $sudo_cmd rm -rf "$v"
    grep -vE '^#' "$r" > "$HOP_STATE_DIR/req.txt"
    cache="$HOP_HOME/.cache/uv"; pyd="$HOP_HOME/.local/share/uv/python"
    # system venvs get a world-readable interpreter (sandboxed DynamicUser services cannot see /root or /home)
    [ -n "$sudo_cmd" ] && { cache=/root/.cache/uv; pyd=/opt/host-hop/python; }
    if $sudo_cmd env UV_CACHE_DIR="$cache" UV_PYTHON_INSTALL_DIR="$pyd" "$HOP_HOME/.local/bin/uv" venv -q --python "$py" "$v" \
       && $sudo_cmd env UV_CACHE_DIR="$cache" UV_PYTHON_INSTALL_DIR="$pyd" "$HOP_HOME/.local/bin/uv" pip install -q --python "$v/bin/python" --no-deps -r "$HOP_STATE_DIR/req.txt"; then
      $sudo_cmd cp "$r" "$v/.host-hop-recipe"
    else
      log "WARN: venv build failed for $v"
    fi
  done

  # --- node_modules for trees that need them at runtime (npm ci from lockfile) ---
  for d in ${HOP_NODE_REBUILD:-}; do
    [ -f "$d/package-lock.json" ] || continue
    if [ -d "$d/node_modules" ] && cmp -s "$d/package-lock.json" "$d/node_modules/.host-hop-lock" 2>/dev/null; then continue; fi
    log "npm ci: $d"; (cd "$d" && npm ci --ignore-scripts --no-audit --no-fund --workspaces=false >/dev/null 2>&1 && cp package-lock.json node_modules/.host-hop-lock) || log "WARN: npm ci failed in $d"
  done

  # --- system pieces outside $HOME: copied, unit installed DISABLED ---
  for p in ${HOP_SYSTEM_PATHS:-}; do
    [ -d "$ST/system/root$p" ] || continue
    sudo -n mkdir -p "$p"; sudo -n rsync -a --exclude venv/ "$ST/system/root$p/" "$p/"; sudo -n chown -R root:root "$p"
  done
  for u in ${HOP_SYSTEM_UNITS:-}; do
    [ -f "$ST/system/$u" ] || continue
    sudo -n install -m 0644 "$ST/system/$u" "/etc/systemd/system/$u"
    sudo -n mkdir -p "/etc/systemd/system/$u.d"
    printf '[Unit]\nConditionPathExists=|!%s\nConditionPathExists=|/run/host-hop/test-allow/%%n\n' "$HOP_HOME/$HOP_STANDBY_LOCK_REL" | sudo -n tee "/etc/systemd/system/$u.d/zz-host-hop-standby.conf" >/dev/null
  done
  sudo -n systemctl daemon-reload
  for u in ${HOP_SYSTEM_UNITS:-}; do sudo -n systemctl disable "$u" >/dev/null 2>&1 || true; done

  # --- serve plan (applied by test-mode / cutover, not now) ---
  python3 - "$ST/serve.json" > "$HOP_STATE_DIR/serve-plan.tsv" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
for hostport, cfg in sorted(d.get("Web", {}).items()):
    port = hostport.rsplit(":", 1)[1]
    for path, h in sorted(cfg.get("Handlers", {}).items()):
        if "Proxy" in h: print(f"{port}\t{path}\t{h['Proxy']}")
PY
  log "serve plan: $(wc -l < "$HOP_STATE_DIR/serve-plan.tsv") handlers (not applied)"
  log "standby-install local: OK (report $REPORT)"
}

if [ "${1:-}" = "--local" ]; then local_install; exit 0; fi

require_args "$@"; T="$1"; known_host "$T"; is_self "$T" && die "run from the active host"
# push current scripts (the home sync also carries them, but this keeps them fresh)
rsync -a -e "ssh $HOP_SSH_BASE" "$HOP_DIR/" "$(host_ssh "$T"):$HOP_DIR/" --exclude logs/
on "$T" "bash $HOP_DIR/standby-install.sh --local"
F="$(self_key)"; [ -n "$F" ] || die "this machine is not in HOP_HOSTS"
"$HOP_DIR/sync.sh" "$F" "$T" --only images
"$HOP_DIR/sync.sh" "$F" "$T" --only volumes
"$HOP_DIR/sync.sh" "$F" "$T" --only pg
status "standby-install $T OK"
