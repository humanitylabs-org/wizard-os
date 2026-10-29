# host-hop shared helpers. Sourced by every phase script. Generic: all box values come from hosts.env.
# shellcheck shell=bash
set -Eeuo pipefail

HOP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOP_ENV="${HOP_ENV:-$HOP_DIR/hosts.env}"
[ -r "$HOP_ENV" ] || { echo "host-hop: missing $HOP_ENV (copy hosts.env.example)" >&2; exit 2; }
# shellcheck disable=SC1090
. "$HOP_ENV"
: "${HOP_HOST_LOCAL_UNITS:=}" "${HOP_OS_ONLY_UNITS:=}" "${HOP_UNIT_SKIP_REGEX:=(^|[-_])(qa|test|candidate)([-_.]|$)}"
: "${HOP_TEST_EGRESS_EXEMPT:=$HOP_HOST_LOCAL_UNITS}"   # exact unit names whose egress stays open in test mode
: "${HOP_PG_DB:=tipi}" "${HOP_SHELL_PORT:=8444}" "${HOP_STATUS_PORT:=8979}" "${HOP_POST_ACTIVATE_HOOK:=}"

HOP_STATE_DIR_REL=".local/share/host-hop"          # per-host state, relative to $HOME, never synced
HOP_STATE_DIR="$HOP_HOME/$HOP_STATE_DIR_REL"
HOP_ROLE_FILE_REL=".wizard-os/host-role"            # per-host role file (never synced)
HOP_STANDBY_LOCK_REL=".wizard-os/standby.lock"      # present => user units refuse to start (see standby-install)
HOP_TEST_ALLOW_REL=".wizard-os/test-allow"          # test-mode allow-list directory
HOP_LOG_DIR="$HOP_DIR/logs"
mkdir -p "$HOP_LOG_DIR"

ts() { date -u +%Y%m%dT%H%M%SZ; }
log() { printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }
die() { log "FATAL: $*"; exit 1; }

hv() { local k="HOP_${1}_${2//-/_}"; printf '%s' "${!k:-}"; }    # hv SSH target-host
host_ssh()   { hv SSH "$1"; }
host_ip()    { hv TSIP "$1"; }
host_tsname(){ hv TSNAME "$1"; }
host_fqdn()  { printf '%s.%s' "$(host_tsname "$1")" "$HOP_TAILNET_SUFFIX"; }
# Role names (spec: clients address <agent>-main, never a machine name).
main_name()    { printf '%s-main' "$HOP_AGENT"; }
standby_name() { printf '%s-backup-%s' "$HOP_AGENT" "$(hv BACKUP_INDEX "$1")"; }   # standby_name HOSTKEY

is_self() { [ "$(hv MACHINE "$1")" = "$(hostname -s)" ]; }

# Machine-local or infrastructure units the hop never stops, moves or starts.
hop_unit_skipped() {
  local u="$1" g
  case "$u" in docker.service|dbus.service|gpg-agent.service|at-spi*|host-hop-*|hop-exempt-*) return 0;; esac
  for g in $HOP_HOST_LOCAL_UNITS; do
    # shellcheck disable=SC2254
    case "$u" in $g) return 0;; esac
  done
  [[ "$u" =~ $HOP_UNIT_SKIP_REGEX ]]
}

# Remote env so user systemd / rootless docker work from non-login ssh.
HOP_REMOTE_ENV="export XDG_RUNTIME_DIR=/run/user/\$(id -u) DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/\$(id -u)/bus DOCKER_HOST=unix:///run/user/\$(id -u)/docker.sock PATH=\$HOME/bin:\$HOME/.local/bin:\$HOME/$HOP_STATE_DIR_REL/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin;"

# All ssh goes through one shared ControlMaster per target. Reason: a target with Tailscale SSH in
# "check" mode demands a browser re-auth for every NEW connection; multiplexing keeps one authenticated
# session alive.
HOP_CM="$HOP_STATE_DIR/cm-%r@%h:%p"
mkdir -p "$HOP_STATE_DIR"
HOP_SSH_BASE="-F $HOP_HOME/.ssh/config -o UserKnownHostsFile=$HOP_HOME/.ssh/known_hosts -o BatchMode=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=8 -o ControlMaster=auto -o ControlPath=$HOP_CM -o ControlPersist=600"
hop_ssh() { ssh $HOP_SSH_BASE -o ConnectTimeout=20 "$@"; }
hop_ssh_check() { ssh $HOP_SSH_BASE -O check "$(host_ssh "$1")" >/dev/null 2>&1; }

# on HOST CMD... : run a shell command on a host (locally if it is this machine).
on() {
  local h="$1"; shift
  if is_self "$h"; then bash -c "$HOP_REMOTE_ENV $*"
  else hop_ssh "$(host_ssh "$h")" "$HOP_REMOTE_ENV $*" </dev/null; fi
}
# on_stdin HOST CMD : same, keeps stdin for streams.
on_stdin() {
  local h="$1"; shift
  if is_self "$h"; then bash -c "$HOP_REMOTE_ENV $*"
  else hop_ssh -o Compression=no "$(host_ssh "$h")" "$HOP_REMOTE_ENV $*"; fi
}

# Map of rootless-docker uids: ns uid 0 = HOP_USER, ns 1..N = subuid range. Same on every host.
HOP_NSMAP="--map-users=0:\$(id -u $HOP_USER):1 --map-users=1:$HOP_SUBID_START:$HOP_SUBID_COUNT --map-groups=0:\$(id -g $HOP_USER):1 --map-groups=1:$HOP_SUBID_START:$HOP_SUBID_COUNT"
# Writer-side namespace (needs sudo on that host): root inside sees files exactly as rootless docker does.
hop_ns_sudo_prefix() { printf 'sudo -n unshare --user %s --setuid 0 --setgid 0 --' "$HOP_NSMAP"; }
# Reader-side namespace without sudo: rootlesskit (shipped with rootless docker) gives the same map.
hop_ns_reader_prefix() {
  local rk; rk="$(command -v rootlesskit || true)"; [ -n "$rk" ] || rk="$HOP_HOME/bin/rootlesskit"
  if [ -x "$rk" ]; then printf '%s --net=host --disable-host-loopback=false --' "$rk"
  elif sudo -n true 2>/dev/null; then hop_ns_sudo_prefix
  else printf ''; fi
}

status() {  # status "line" : append a timestamped line to the local STATUS log
  printf -- '- %s %s\n' "$(date -u '+%F %H:%MZ')" "$*" >> "$HOP_DIR/STATUS.log"
}

require_args() { [ "$#" -ge 1 ] || die "usage: $0 TARGET_HOST_KEY (one of: $HOP_HOSTS)"; }
known_host() { case " $HOP_HOSTS " in *" $1 "*) ;; *) die "unknown host key '$1' (hosts.env HOP_HOSTS)";; esac; }

# Run a command locally inside the rootless-docker uid map as ns-root (needs sudo on this host).
hop_ns_exec() {
  local u g; u=$(id -u "$HOP_USER"); g=$(id -g "$HOP_USER")
  sudo -n unshare --user --map-users=0:$u:1 --map-users=1:$HOP_SUBID_START:$HOP_SUBID_COUNT \
    --map-groups=0:$g:1 --map-groups=1:$HOP_SUBID_START:$HOP_SUBID_COUNT --setuid 0 --setgid 0 -- "$@"
}
# Host key of this machine in hosts.env (matched by short hostname).
self_key() { local h; for h in $HOP_HOSTS; do is_self "$h" && { echo "$h"; return; }; done; }

# Before starting containers on a host: every single-file bind mount source must exist as a FILE,
# otherwise docker silently creates a directory (e.g. a SQLite -wal file that is absent on a replica).
hop_ensure_file_binds() {
  local m="$1" f; [ -f "$m" ] || return 0
  awk -F'\t' '$1=="filebind"{print $2}' "$m" | while read -r f; do
    [ -d "$f" ] && rmdir "$f" 2>/dev/null
    [ -e "$f" ] || { mkdir -p "$(dirname "$f")"; : > "$f"; }
  done
}
