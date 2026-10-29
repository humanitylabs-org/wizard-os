#!/usr/bin/env bash
# host-hop phase 4: boot the STANDBY in an isolated test mode, check it, stop it.
# Usage (on the ACTIVE host):  test-mode.sh TARGET start [--serve] | verify | stop | status
#
# Isolation contract (all must hold, `verify` proves each one):
#   1. The Hermes gateway (messaging platforms + cron ticker) and every unit in HOP_TEST_NEVER_UNITS stay
#      blocked by the standby guard; only HOP_TEST_UNITS get a runtime allow file.
#   2. Compose projects in HOP_TEST_DENY_APPS (messaging bridges, device control) and the Runtipi controller
#      are never started.
#   3. A host firewall chain rejects every non-loopback packet from the whole user service manager
#      (all user units, rootless docker and every container), except target-owned units in
#      HOP_TEST_EGRESS_EXEMPT (machine-local jobs). So nothing in test mode can send mail/SMS/Telegram/webhooks or reach the
#      active host, whatever its config says.
#   4. Host identity in configs is rewritten to the standby's own tailnet name (backed up; restored on stop;
#      the next sync overwrites it anyway).
# --serve publishes the standby's own tailnet URLs with `tailscale serve` (needs owner OK on that host).
. "$(dirname "$0")/lib.sh"

local_main() {
  eval "$HOP_REMOTE_ENV"
  local action="$1"; shift || true
  local RUN="/run/user/$(id -u)/host-hop"; local ALLOW="$RUN/test-allow"; local ACTIVE="$RUN/test-mode.active"
  local ST="$HOP_STATE_DIR/staged"; local EV="$HOP_STATE_DIR/test-mode-evidence.txt"
  local UCG="user.slice/user-$(id -u).slice/user@$(id -u).service"
  local RTU="/run/user/$(id -u)/systemd/user"
  local ROLE; ROLE=$(sed -n 's/^HOP_ROLE=//p' "$HOP_HOME/$HOP_ROLE_FILE_REL" 2>/dev/null || true)
  local SELF_FQDN; SELF_FQDN="$(sed -n 's/^HOP_TSNAME=//p' "$HOP_HOME/$HOP_ROLE_FILE_REL").$HOP_TAILNET_SUFFIX"
  local SELF_IP; SELF_IP="$(sed -n 's/^HOP_TSIP=//p' "$HOP_HOME/$HOP_ROLE_FILE_REL")"
  local ACTK="${HOP_ACT:-}"; local ACT_FQDN ACT_IP; ACT_FQDN="$(host_fqdn "$ACTK")"; ACT_IP="$(host_ip "$ACTK")"
  compose_args() {  # project line -> docker compose args
    local wd="$1" files="$2" envs="$3" a="--project-directory $wd"
    for f in ${files//,/ }; do a="$a -f $f"; done
    for e in ${envs//,/ }; do [ -f "$e" ] && a="$a --env-file $e"; done
    printf '%s' "$a"
  }
  denied() { local p="$1"; for d in $HOP_TEST_DENY_APPS; do [ "$p" = "${d}_wizardapps" ] || [ "$p" = "$d" ] && return 0; done; return 1; }

  case "$action" in
  start)
    [ "$ROLE" = standby ] || die "role is '$ROLE'; test mode only runs on a standby"
    [ -n "$ACTK" ] || die "HOP_ACT (source host key) not set; run test-mode.sh from the source"
    [ -e "$HOP_HOME/$HOP_STANDBY_LOCK_REL" ] || die "standby lock missing"
    [ -e "$ACTIVE" ] && die "test mode already active"
    docker info >/dev/null 2>&1 || systemctl --user start docker.service
    mkdir -p "$ALLOW"; date -u +%FT%TZ > "$ACTIVE"
    # -- 3. firewall first, before anything starts
    systemctl --user daemon-reload
    mkdir -p "$RTU"; printf '[Unit]\nDescription=host-hop egress-exempt slice (target-owned jobs)\n' > "$RTU/hopexempt.slice"
    for u in $HOP_TEST_EGRESS_EXEMPT; do
      mkdir -p "$RTU/$u.d"; printf '[Service]\nSlice=hopexempt.slice\n' > "$RTU/$u.d/zz-host-hop-test.conf"
    done
    systemctl --user daemon-reload
    # an anchor process keeps the slice cgroup present so the firewall rule can reference it
    systemctl --user is-active hop-exempt-anchor.service >/dev/null 2>&1 || \
      systemd-run --user --quiet --unit=hop-exempt-anchor --slice=hopexempt.slice sleep infinity
    [ -d "/sys/fs/cgroup/$UCG/hopexempt.slice" ] || die "exempt slice cgroup missing"
    for ipt in iptables ip6tables; do
      sudo -n $ipt -N HOP-TEST 2>/dev/null || sudo -n $ipt -F HOP-TEST
      sudo -n $ipt -A HOP-TEST -o lo -j RETURN
      sudo -n $ipt -A HOP-TEST -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN   # replies to inbound only
      sudo -n $ipt -A HOP-TEST -m cgroup --path "$UCG/hopexempt.slice" -j RETURN
      for u in $HOP_TEST_EGRESS_EXEMPT; do   # already-running exempt units keep their current cgroup
        [ -d "/sys/fs/cgroup/$UCG/app.slice/$u" ] && sudo -n $ipt -A HOP-TEST -m cgroup --path "$UCG/app.slice/$u" -j RETURN
      done
      sudo -n $ipt -A HOP-TEST -m cgroup --path "$UCG" -j REJECT
      sudo -n $ipt -C OUTPUT -j HOP-TEST 2>/dev/null || sudo -n $ipt -I OUTPUT 1 -j HOP-TEST
    done
    log "firewall: HOP-TEST active (user manager egress rejected except loopback and $HOP_TEST_EGRESS_EXEMPT)"
    # -- 4. identity rewrite to this host
    if [ -f "$HOP_DIR/rewrite-targets.txt" ]; then
      rm -rf "$HOP_STATE_DIR/test-rewrite-backup"
      hop_ns_exec env HOP_HOME="$HOP_HOME" python3 -I "$HOP_DIR/rewrite.py" apply "$HOP_DIR/rewrite-targets.txt" \
        "$HOP_STATE_DIR/test-rewrite-backup" "$ACT_FQDN=$SELF_FQDN" "$ACT_IP=$SELF_IP"
    fi
    # -- 1. units: allow only the test set (never-units are filtered even if listed)
    for u in $HOP_TEST_UNITS; do
      case " $HOP_TEST_NEVER_UNITS " in *" $u "*) log "refusing never-unit $u"; continue;; esac
      touch "$ALLOW/$u"
    done
    sudo -n mkdir -p /run/host-hop/test-allow
    for u in ${HOP_TEST_SYSTEM_UNITS:-}; do sudo -n touch "/run/host-hop/test-allow/$u"; done
    systemctl --user daemon-reload; sudo -n systemctl daemon-reload
    # -- 2. containers
    hop_ensure_file_binds "$ST/compose-projects.tsv"
    if [ -f "$ST/compose-projects.tsv" ]; then
      while IFS=$'\t' read -r kind p wd files envs svcs; do
        [ "$kind" = project ] && [ "$p" = "$HOP_CORE_PROJECT" ] || continue
        keep=""; for s in $svcs; do case " $HOP_TEST_CORE_SKIP_SERVICES runtipi-db runtipi-queue " in *" $s "*) ;; *) keep="$keep $s";; esac; done
        docker compose -p "$p" $(compose_args "$wd" "$files" "$envs") up -d --no-deps --pull never --no-build $keep >/dev/null 2>>"$EV.err" \
          && log "core: started$keep" || log "WARN core start failed"
      done < "$ST/compose-projects.tsv"
      while IFS=$'\t' read -r kind p wd files envs svcs; do
        [ "$kind" = project ] || continue; [ "$p" = "$HOP_CORE_PROJECT" ] && continue
        if denied "$p"; then log "skip (denied in test): $p"; continue; fi
        if docker compose -p "$p" $(compose_args "$wd" "$files" "$envs") up -d --pull never --no-build >/dev/null 2>>"$EV.err"; then
          echo "$p" >> "$RUN/test-projects"; else log "WARN project failed: $p"; fi
      done < "$ST/compose-projects.tsv"
    fi
    for u in $HOP_TEST_UNITS; do [ -e "$ALLOW/$u" ] && { systemctl --user start "$u" || log "WARN start failed: $u"; }; done
    for u in ${HOP_TEST_SYSTEM_UNITS:-}; do sudo -n systemctl start "$u" || log "WARN start failed: $u"; done
    if [ "${1:-}" = "--serve" ]; then
      while IFS=$'\t' read -r port path target; do
        timeout 25 tailscale serve --bg --https="$port" --set-path="$path" "$target" </dev/null >/dev/null 2>&1 || log "WARN serve $port$path"
      done < "$HOP_STATE_DIR/serve-plan.tsv"
      touch "$RUN/test-serve"; log "serve: https://$SELF_FQDN (tailnet only)"
    fi
    sleep 20; local_main verify
    ;;
  verify)
    [ -e "$ACTIVE" ] || die "test mode not active"
    {
      echo "== host-hop test-mode evidence $(date -u +%FT%TZ) on $(hostname -s)"
      echo "-- never-units (must be inactive):"
      for u in $HOP_TEST_NEVER_UNITS; do printf '  %-42s %s\n' "$u" "$(systemctl --user is-active "$u" 2>/dev/null)"; done
      echo "-- gateway processes (must be none): $(pgrep -u "$(id -u)" -fc 'hermes.* gateway run' || true)"
      echo "-- denied app containers (must be none): $(docker ps --format '{{.Names}}' | grep -cE "^($(echo $HOP_TEST_DENY_APPS | tr ' ' '|'))_" || true)"
      echo "-- runtipi controller running: $(docker ps --format '{{.Names}}' | grep -cx runtipi || true)"
      echo "-- firewall chain:"; sudo -n iptables -S HOP-TEST | sed 's/^/  /'
      echo "-- egress probe from a user unit (must fail):"
      if systemd-run --user --wait --pipe --quiet -p TimeoutStartSec=20 curl -sS -m 8 -o /dev/null https://api.telegram.org 2>&1; then echo "  FAIL: reached api.telegram.org"; else echo "  ok: blocked"; fi
      echo "-- egress probe from a container (must fail):"
      img=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -m1 '^python:3.12-alpine$' || true)
      if [ -n "$img" ] && docker run --rm --pull never "$img" python -c "import socket;socket.create_connection(('1.1.1.1',443),timeout=6)" >/dev/null 2>&1; then echo "  FAIL: container reached 1.1.1.1:443"; else echo "  ok: blocked"; fi
      echo "-- egress probe to active host tailnet IP (must fail):"
      if systemd-run --user --wait --pipe --quiet curl -sS -m 6 -o /dev/null "http://$ACT_IP:8444/" 2>/dev/null; then echo "  FAIL: reached active host"; else echo "  ok: blocked"; fi
      echo "-- running test containers: $(docker ps -q | wc -l)"
      echo "-- local health (port path -> http code):"
      awk -F'\t' '{print $3}' "$HOP_STATE_DIR/serve-plan.tsv" | sort -u | while read -r url; do
        printf '  %-48s %s\n' "$url" "$(curl -s -m 6 -o /dev/null -w '%{http_code}' "$url/" || true)"; done
    } | tee "$EV"
    if grep -q 'FAIL' "$EV" || grep -A40 'never-units' "$EV" | grep -qE '^\s+\S+\s+active$'; then die "ISOLATION NOT PROVEN (see $EV)"; fi
    log "isolation proven: evidence in $EV"
    ;;
  stop)
    bash "$HOP_DIR/teardown.sh"
    ;;
  status)
    [ -e "$ACTIVE" ] && echo "test-mode ACTIVE since $(cat "$ACTIVE")" || echo "test-mode off"
    docker ps --format '{{.Names}}' 2>/dev/null | wc -l | sed 's/^/containers running: /'
    ;;
  *) die "usage: test-mode.sh TARGET start [--serve]|verify|stop|status";;
  esac
}

if [ "${1:-}" = "--local" ]; then shift; local_main "$@"; exit 0; fi
[ "$#" -ge 2 ] || die "usage: $0 TARGET start [--serve]|verify|stop|status"
T="$1"; shift; known_host "$T"; is_self "$T" && die "run from the active host against the standby"
[ -n "$(self_key)" ] || die "this machine is not in HOP_HOSTS"
rsync -a -e "ssh $HOP_SSH_BASE" --exclude logs/ "$HOP_DIR/" "$(host_ssh "$T"):$HOP_DIR/"
on "$T" "HOP_ACT=$(self_key) bash $HOP_DIR/test-mode.sh --local $*"
status "test-mode $T $*"
