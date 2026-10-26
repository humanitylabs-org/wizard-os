#!/usr/bin/env bash
# host-hop phase 1: make TARGET able to run the stack. Idempotent; safe to rerun.
# Usage: prepare-target.sh TARGET
# Installs OS packages, checks user/uid/subuid/linger, creates the dir layout, installs pinned sqlite tools,
# sets the tailscale operator. Starts nothing except the rootless docker daemon (empty; no containers).
. "$(dirname "$0")/lib.sh"
require_args "$@"; T="$1"; known_host "$T"
is_self "$T" && die "target is this machine"
log "prepare-target: $T ($(host_ssh "$T"))"

# 1. Identity checks: same user, uid, subuid range, linger.
src_uid=$(id -u "$HOP_USER")
on "$T" "id -u" | grep -qx "$src_uid" || die "uid of $HOP_USER differs on $T (need $src_uid)"
on "$T" "grep -qx '$HOP_USER:$HOP_SUBID_START:$HOP_SUBID_COUNT' /etc/subuid && grep -qx '$HOP_USER:$HOP_SUBID_START:$HOP_SUBID_COUNT' /etc/subgid" \
  || die "subuid/subgid on $T must be $HOP_USER:$HOP_SUBID_START:$HOP_SUBID_COUNT"
on "$T" "sudo -n true" || die "need passwordless sudo on $T"
on "$T" "loginctl show-user $HOP_USER -p Linger | grep -q yes || sudo -n loginctl enable-linger $HOP_USER"

# 2. Packages. Only what the user-level stack needs; no desktop / no services enabled.
PKGS="uidmap dbus-user-session iptables slirp4netns rsync jq zstd sqlite3 git curl ca-certificates unzip python3 python3-venv python3-yaml python3-cryptography build-essential ffmpeg"
on "$T" "export DEBIAN_FRONTEND=noninteractive; missing=\$(for p in $PKGS; do dpkg -s \$p >/dev/null 2>&1 || echo \$p; done); \
  if [ -n \"\$missing\" ]; then sudo -n apt-get update -qq && sudo -n apt-get install -y -qq --no-install-recommends \$missing; fi"
# Node: same major as source's /usr/bin/node (several user services call /usr/bin/node).
NODE_MAJOR=$(/usr/bin/node --version 2>/dev/null | sed -E 's/^v([0-9]+).*/\1/' || true)
if [ -n "$NODE_MAJOR" ]; then
  on "$T" "v=\$(/usr/bin/node --version 2>/dev/null | sed -E 's/^v([0-9]+).*/\1/'); [ \"\$v\" = $NODE_MAJOR ] && exit 0; \
    export DEBIAN_FRONTEND=noninteractive; sudo -n install -d -m 0755 /usr/share/keyrings; \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | sudo -n gpg --dearmor --yes -o /usr/share/keyrings/nodesource.gpg; \
    printf 'Types: deb\nURIs: https://deb.nodesource.com/node_${NODE_MAJOR}.x\nSuites: nodistro\nComponents: main\nArchitectures: amd64\nSigned-By: /usr/share/keyrings/nodesource.gpg\n' | sudo -n tee /etc/apt/sources.list.d/nodesource.sources >/dev/null; \
    sudo -n apt-get update -qq && sudo -n apt-get install -y -qq nodejs"
fi
# Runtipi bind-mounts /etc/timezone; Debian lacks it and docker would create a directory there.
on "$T" "[ -f /etc/timezone ] || { readlink /etc/localtime | sed 's#.*/zoneinfo/##' | sudo -n tee /etc/timezone >/dev/null; }"

# 3. Layout + per-host state dir + pinned sqlite tools (sqlite3_rsync must be on the remote PATH).
on "$T" "mkdir -p ~/$HOP_STATE_DIR_REL/bin ~/.wizard-os ~/.config/systemd/user ~/.local/share ~/bin"
mkdir -p "$HOP_STATE_DIR/bin"
for b in sqlite3 sqlite3_rsync; do
  install -m 0755 "$HOP_DIR/bin/$b" "$HOP_STATE_DIR/bin/$b"
  if ! on "$T" "cmp -s ~/$HOP_STATE_DIR_REL/bin/$b /dev/stdin" < "$HOP_DIR/bin/$b"; then
    on_stdin "$T" "cat > ~/$HOP_STATE_DIR_REL/bin/$b.new && chmod 755 ~/$HOP_STATE_DIR_REL/bin/$b.new && mv ~/$HOP_STATE_DIR_REL/bin/$b.new ~/$HOP_STATE_DIR_REL/bin/$b" < "$HOP_DIR/bin/$b"
  fi
done
on "$T" "sudo -n install -m 0755 ~/$HOP_STATE_DIR_REL/bin/sqlite3_rsync /usr/local/bin/sqlite3_rsync"
install -m 0755 "$HOP_DIR/bin/sqlite3_rsync" "$HOP_STATE_DIR/bin/sqlite3_rsync"

# 4. Role file (never synced). A host that has no role yet becomes a standby.
on "$T" "[ -f ~/$HOP_ROLE_FILE_REL ] || printf 'HOP_ROLE=standby\nHOP_AGENT=$HOP_AGENT\nHOP_TSNAME=$(host_tsname "$T")\nHOP_TSIP=$(host_ip "$T")\n' > ~/$HOP_ROLE_FILE_REL"
on "$T" "touch ~/$HOP_STANDBY_LOCK_REL"   # guard read by every staged unit (see standby-install)

# 5. Tailscale operator so serve/rename work without sudo later. Nothing else tailscale.
on "$T" "tailscale debug prefs 2>/dev/null | grep -q '\"OperatorUser\": \"$HOP_USER\"' || sudo -n tailscale set --operator=$HOP_USER"

# 6. Rootless docker: binaries arrive with the home sync (~/bin). Daemon is set up by standby-install.
log "prepare-target: OK"
status "prepare-target $T OK"
