#!/usr/bin/env bash
# host-hop phase 2: copy ACTIVE (FROM, = this machine) to STANDBY (TO). Idempotent delta; safe to rerun.
# Usage: sync.sh FROM TO [--only home|db|pg|images|volumes|units] [--final]
#   --final  : cutover mode (services on FROM are already stopped); same steps, plus a timing record.
# Read-only on FROM: nothing is stopped, paused or written there except files under $HOP_DIR/logs and
# the per-host state dir. Everything streams over ssh; nothing is staged on FROM's disk.
. "$(dirname "$0")/lib.sh"
[ "$#" -ge 2 ] || die "usage: $0 FROM TO [--only STEP] [--final]"
F="$1"; T="$2"; shift 2; known_host "$F"; known_host "$T"
ONLY=""; FINAL=0
while [ "$#" -gt 0 ]; do case "$1" in --only) ONLY="$2"; shift 2;; --final) FINAL=1; shift;; *) die "bad arg $1";; esac; done
is_self "$F" || die "run sync.sh on the source host ($F)"
# Final sync is legal only under the reviewed runner with immutable live inventory.
if [ "$FINAL" = 1 ]; then
  [ -n "${HOP_FROZEN_DIR:-}" ] && [ -f "$HOP_FROZEN_DIR/SHA256SUMS" ] || die 'final requires HOP_FROZEN_DIR'
  (cd "$HOP_FROZEN_DIR" && sha256sum -c SHA256SUMS >/dev/null) || die 'frozen inventory changed'
  [ "$(docker container inspect -f '{{.State.Running}}' "$HOP_PG_CONTAINER")" = false ] || die 'final requires stopped PostgreSQL'
fi
TS_SSH="$(host_ssh "$T")"
H="$HOP_HOME"
WORK="$HOP_STATE_DIR/sync"; mkdir -p "$WORK" "$HOP_STATE_DIR/bin"
CM="$HOP_STATE_DIR/cm-%r@%h:%p"
SSH_OPTS="-F $H/.ssh/config -o UserKnownHostsFile=$H/.ssh/known_hosts -o BatchMode=yes -o Compression=no -o ServerAliveInterval=15 -o ServerAliveCountMax=8 -o ControlMaster=auto -o ControlPath=$CM -o ControlPersist=300"
REMOTE_NS="$(hop_ns_sudo_prefix)"
READER="$(hop_ns_reader_prefix)"
[ -n "$READER" ] || die "no way to read rootless-docker-owned files on $F (need rootlesskit or sudo)"
want() { [ -z "$ONLY" ] || [ "$ONLY" = "$1" ]; }
t0=$(date +%s)
step_time() { log "step $1 took $(( $(date +%s) - $2 ))s"; echo "$1 $(( $(date +%s) - $2 ))" >> "$WORK/timings-$RUN_ID"; }
if on "$T" "test -e /run/user/\$(id -u)/host-hop/test-mode.active"; then die "test-mode is active on $T; run test-mode.sh $T stop first"; fi
RUN_ID="$(ts)"; [ "$FINAL" = 1 ] && RUN_ID="final-$RUN_ID"

# ssh wrapper used by sqlite3_rsync: drops its "-e none" options; remote side runs inside the
# rootless-docker uid map on TO (sudo unshare), so container-owned DBs land with the right owners.
cat > "$HOP_STATE_DIR/bin/hop-ssh-ns" <<EOF
#!/bin/sh
while [ \$# -gt 0 ]; do case "\$1" in -e|-p|-o|-l|-i) shift 2;; -*) shift;; *) break;; esac; done
host="\$1"; shift
exec ssh $SSH_OPTS "\$host" "$REMOTE_NS sh -c '\$*'"
EOF
chmod 755 "$HOP_STATE_DIR/bin/hop-ssh-ns"

# ---------- filter list (generic rules + hosts.env extras) ----------
FILTER="$WORK/filter.rules"
{
  echo "# generated $(ts)"
  # per-host state and role never travel
  echo "- /$HOP_STATE_DIR_REL/"; echo "- /$HOP_ROLE_FILE_REL"; echo "- /$HOP_STANDBY_LOCK_REL"; echo "- /$HOP_TEST_ALLOW_REL/"
  # user units are staged separately so they can never auto-start on the standby
  echo "- /.config/systemd/user/"
  # Preserve all host identities and recovery control-plane files in BOTH directions.
  echo '- /.ssh/'
  # the hop scripts themselves (each host keeps its own reviewed, digest-pinned copy)
  case "$HOP_DIR" in "$H"/*) echo "- /${HOP_DIR#"$H"/}/";; esac
  # target-owned paths: excluded (not sent) and therefore protected from --delete
  for p in $HOP_TARGET_OWNED; do echo "- $p"; done
  # docker data root: images/volumes handled explicitly
  echo "- /.local/share/docker/"
  # postgres data dir: pg_basebackup step
  if [ -n "${HOP_PG_DATADIR:-}" ]; then echo "- $HOP_PG_DATADIR/"; echo "- $HOP_PG_DATADIR.*/"; fi
  # installed JS toolchains are kept (not regenerable from a project lockfile)
  echo "+ /.local/lib/node_modules/***"; echo "+ /.nvm/versions/***"; echo "+ /.hermes/tools/***"; echo "+ /.hermes/node/***"
  # regenerable trees
  for p in node_modules/ .venv/ venv/ venvs/ cron-venv/ .release-venv/ __pycache__/ .pytest_cache/ .ruff_cache/ .mypy_cache/ \
           /.cache/ /.npm/ "Cache/" "Code Cache/" "GPUCache/" "ShaderCache/" "GrShaderCache/" "DawnCache/" "CacheStorage/"; do echo "- $p"; done
  for p in $HOP_EXTRA_EXCLUDES; do echo "- $p"; done
  # live SQLite files go through sqlite3_rsync (list generated below)
  echo "merge $WORK/sqlite-hot.rules"
} > "$FILTER"

# ---------- SQLite inventory (inside uid map so container-owned DBs are visible) ----------
if want db || want home || want inventory; then
  ts0=$(date +%s)
  $READER python3 -I - "$H" "$FILTER" "${HOP_SQLITE_HOT_ROOTS_EXTRA:-}" > "$WORK/sqlite-inventory.tsv" <<'PY'
import os, sys, time, fnmatch
home, filt = sys.argv[1], sys.argv[2]
ex_anch, ex_name = [], []
for line in open(filt):
    line=line.rstrip('\n')
    if not line.startswith('- '): continue
    p=line[2:]
    (ex_anch if p.startswith('/') else ex_name).append(p.rstrip('/'))
SQL_EXT=('.db','.sqlite','.sqlite3','.db3')
HOT_ROOTS=('/.hermes/','/runtipi/','/.wizard-os/','/.config/','/.local/share/',*sys.argv[3].split())
now=time.time()
for root, dirs, files in os.walk(home):
    rel=root[len(home):] or '/'
    keep=[]
    for d in dirs:
        r=(rel.rstrip('/')+'/'+d)
        if any(r==a or fnmatch.fnmatch(r,a) for a in ex_anch) or any(fnmatch.fnmatch(d,n) for n in ex_name): continue
        if os.path.islink(os.path.join(root,d)): continue
        keep.append(d)
    dirs[:]=keep
    for f in files:
        if not f.endswith(SQL_EXT): continue
        p=os.path.join(root,f); r=p[len(home):]
        if any(r==a or fnmatch.fnmatch(r,a) for a in ex_anch): continue
        try:
            st=os.lstat(p)
            if not os.path.isfile(p) or os.path.islink(p) or st.st_size<512: continue
            with open(p,'rb') as fh:
                if fh.read(16)!=b'SQLite format 3\x00': continue
        except OSError: continue
        side=any(os.path.exists(p+s) and os.path.getsize(p+s)>0 for s in ('-wal','-journal'))
        hot = (side or (now-st.st_mtime)<2*86400 or any(r.startswith(x) for x in HOT_ROOTS)) and not any(c.isspace() for c in r)
        print(f"{'hot' if hot else 'cold'}\t{st.st_size}\t{st.st_uid}\t{st.st_gid}\t{st.st_mode&0o7777:04o}\t{r}")
PY
  awk -F'\t' '$1=="hot"{print $6}' "$WORK/sqlite-inventory.tsv" | sed -e 's/[][*?\\]/\\&/g' | while read -r r; do
    printf -- '- %s\n- %s-wal\n- %s-shm\n- %s-journal\n' "$r" "$r" "$r" "$r"; done > "$WORK/sqlite-hot.rules"
  log "sqlite inventory: $(grep -c '^hot' "$WORK/sqlite-inventory.tsv") hot, $(grep -c '^cold' "$WORK/sqlite-inventory.tsv") cold"
  step_time sqlite-inventory "$ts0"
else
  [ -f "$WORK/sqlite-hot.rules" ] || : > "$WORK/sqlite-hot.rules"
fi

# ---------- 1. home tree ----------
if want home; then
  ts0=$(date +%s)
  on "$T" "mkdir -p $H"
  # rsync exit 24 (vanished files) is normal on a live source.
  set +e
  $READER rsync -aH --numeric-ids --no-specials --no-devices --delete-after --partial --inplace \
     --filter="merge $FILTER" --info=stats2 \
     -e "ssh $SSH_OPTS" --rsync-path="$REMOTE_NS rsync" \
     "$H/" "$TS_SSH:$H/" > "$WORK/rsync-home-$RUN_ID.log" 2>&1
  rc=$?; set -e
  tail -n 20 "$WORK/rsync-home-$RUN_ID.log" >&2
  case $rc in 0) ;; 24) [ "$FINAL" = 0 ] || die 'vanished files during frozen final sync';; *) die "rsync home failed rc=$rc (see $WORK/rsync-home-$RUN_ID.log)";; esac
  step_time home "$ts0"
fi

# ---------- 2. live SQLite via sqlite3_rsync (consistent snapshot of a live DB, delta pages only) ----------
if want db; then
  ts0=$(date +%s)
  awk -F'\t' '$1=="hot"{print $6}' "$WORK/sqlite-inventory.tsv" | sed 's#/[^/]*$##' | sort -u | sed "s#^#$H#" | \
    ssh $SSH_OPTS "$TS_SSH" "$REMOTE_NS sh -c 'while read -r d; do mkdir -p \"\$d\"; done'"
  cat > "$WORK/db-loop.sh" <<EOF
#!/bin/bash
n=0; fails=0
while IFS=\$'\t' read -r kind size uid gid mode rel; do
  [ "\$kind" = hot ] || continue; n=\$((n+1))
  if ! "$HOP_STATE_DIR/bin/sqlite3_rsync" "$H\$rel" "$TS_SSH:$H\$rel" --ssh "$HOP_STATE_DIR/bin/hop-ssh-ns" --exe /usr/local/bin/sqlite3_rsync >>"$WORK/sqlite-$RUN_ID.log" 2>&1; then
    fails=\$((fails+1)); echo "FAIL \$rel" >> "$WORK/sqlite-$RUN_ID.log"
  fi
done < "$WORK/sqlite-inventory.tsv"
echo "\$n \$fails"
EOF
  chmod 755 "$WORK/db-loop.sh"
  read -r n fails < <($READER "$WORK/db-loop.sh")
  # owner/mode as on source (replica files are created by ns-root on TO)
  awk -F'\t' '$1=="hot"{print $3" "$4" "$5" "$6}' "$WORK/sqlite-inventory.tsv" | \
    ssh $SSH_OPTS "$TS_SSH" "$REMOTE_NS sh -c 'while read u g m p; do [ -f \"$H\$p\" ] && chown -h \$u:\$g \"$H\$p\" && chmod \$m \"$H\$p\"; done'" || true
  log "sqlite3_rsync: $n databases, $fails failures"
  [ "$fails" = 0 ] || { grep FAIL "$WORK/sqlite-$RUN_ID.log" | head >&2; die "sqlite sync had $fails failures"; }
  step_time db "$ts0"
fi

# ---------- 3. PostgreSQL (Runtipi) via pg_basebackup stream ----------
if want pg && [ -n "${HOP_PG_CONTAINER:-}" ] && docker container inspect "$HOP_PG_CONTAINER" >/dev/null 2>&1; then
  ts0=$(date +%s)
  PGD="$H$HOP_PG_DATADIR"
  if [ "$FINAL" = 1 ]; then
    # PG is cleanly stopped: copy physical bytes to a separate candidate. Never exec stopped PG.
    $READER test ! -e "$PGD/postmaster.pid" || die 'PostgreSQL postmaster.pid remains'
    on "$T" "$(hop_ns_sudo_prefix) mkdir -p '$PGD.final-new'"
    $READER rsync -aH --numeric-ids --delete -e "ssh $SSH_OPTS" --rsync-path="$REMOTE_NS rsync" "$PGD/" "$TS_SSH:$PGD.final-new/"
    $READER rsync -aHnc --numeric-ids --delete --itemize-changes -e "ssh $SSH_OPTS" --rsync-path="$REMOTE_NS rsync" "$PGD/" "$TS_SSH:$PGD.final-new/" > "$WORK/pg-final-verify.txt"
    [ ! -s "$WORK/pg-final-verify.txt" ] || die 'PostgreSQL final copy checksum mismatch'
    PGIMAGE=$(docker container inspect --format '{{.Image}}' "$HOP_PG_CONTAINER")
    on "$T" "docker run --rm --network none --read-only --entrypoint pg_controldata -v '$PGD.final-new:/verify:ro' '$PGIMAGE' /verify" > "$WORK/pg-control-final.txt"
    grep -qE 'Database cluster state:[[:space:]]+shut down$' "$WORK/pg-control-final.txt" || die 'PostgreSQL not cleanly shut down'
    on "$T" "$REMOTE_NS sh -c 'set -e; test -f \"$PGD.final-new/PG_VERSION\"; test -f \"$PGD.final-new/global/pg_control\"; test ! -e \"$PGD.final-new/postmaster.pid\"; test ! -e \"$PGD.before-final-$RUN_ID\"; mv \"$PGD\" \"$PGD.before-final-$RUN_ID\"; mv \"$PGD.final-new\" \"$PGD\"'"
  else
  docker exec "$HOP_PG_CONTAINER" pg_basebackup -U "$HOP_PG_USER" -D - -Ft -X fetch -c fast 2>"$WORK/pg-$RUN_ID.err" | \
    ssh $SSH_OPTS "$TS_SSH" "$REMOTE_NS sh -c 'set -e; rm -rf \"$PGD.new\"; mkdir -p \"$PGD.new\"; tar -xf - -C \"$PGD.new\" --numeric-owner; chown -R 999:999 \"$PGD.new\"; chmod 700 \"$PGD.new\"'"
  # Sender and receiver have both succeeded. Verify manifest before publication, retain predecessor.
  PGIMAGE=$(docker container inspect --format '{{.Image}}' "$HOP_PG_CONTAINER")
  on "$T" "docker run --rm --network none --read-only --entrypoint pg_verifybackup -v '$PGD.new:/verify:ro' '$PGIMAGE' /verify"
  on "$T" "$REMOTE_NS sh -c 'set -e; test ! -e \"$PGD.warm-before-$RUN_ID\"; if test -d \"$PGD\"; then mv \"$PGD\" \"$PGD.warm-before-$RUN_ID\"; fi; mv \"$PGD.new\" \"$PGD\"'"
  fi
  log "postgres backup copied (final=$FINAL)"
  step_time pg "$ts0"
fi

# ---------- 4. images: pull public by digest on TO, docker save|load local-only ones ----------
running_containers() { if [ "$FINAL" = 1 ]; then cat "$HOP_FROZEN_DIR/running-containers.txt"; else docker ps --format '{{.Names}}' | grep -Ev "$HOP_CONTAINER_SKIP_REGEX" || true; fi; }
if want images; then
  ts0=$(date +%s)
  on "$T" "docker info >/dev/null 2>&1" || die "docker is not running on $T (run standby-install first)"
  : > "$WORK/images-$RUN_ID.tsv"
  for c in $(running_containers); do docker container inspect --format '{{.Image}}' "$c"; done | sort -u | while read -r id; do
    tags=$(docker image inspect --format '{{join .RepoTags " "}}' "$id" | tr ' ' '\n' | grep -v '@' | tr '\n' ' ' || true)
    digs=$(docker image inspect --format '{{join .RepoDigests " "}}' "$id")
    if on "$T" "docker image inspect $id >/dev/null 2>&1"; then
      # present; make sure tags match
      for t in $tags; do on "$T" "docker tag $id $t" >/dev/null 2>&1 || true; done
      printf 'present\t%s\t%s\n' "$id" "$tags" >> "$WORK/images-$RUN_ID.tsv"; continue
    fi
    remote=""
    for d in $digs; do
      if on "$T" "docker pull -q '$d' >/dev/null 2>&1"; then remote="$d"; break; fi
    done
    if [ -n "$remote" ]; then
      for t in $tags; do on "$T" "docker tag '$remote' $t" >/dev/null 2>&1 || true; done
      printf 'pulled\t%s\t%s\n' "$id" "$remote" >> "$WORK/images-$RUN_ID.tsv"
    else
      docker save $tags $([ -z "$tags" ] && echo "$id") | ssh $SSH_OPTS "$TS_SSH" "$HOP_REMOTE_ENV docker load -q" >/dev/null
      printf 'loaded\t%s\t%s\n' "$id" "$tags" >> "$WORK/images-$RUN_ID.tsv"
    fi
  done
  cut -f1 "$WORK/images-$RUN_ID.tsv" | sort | uniq -c >&2
  step_time images "$ts0"
fi

# ---------- 5. named volumes: tar-stream from the data dir (no container started on FROM) ----------
if want volumes; then
  ts0=$(date +%s)
  on "$T" "docker info >/dev/null 2>&1" || die "docker is not running on $T"
  vols=$(for c in $(running_containers); do docker container inspect --format '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}} {{end}}{{end}}' "$c"; done | tr ' ' '\n' | sort -u | sed '/^$/d')
  VROOT_F="$(docker info --format '{{.DockerRootDir}}')/volumes"
  for v in $vols; do
    labels=$(docker volume inspect --format '{{range $k,$v := .Labels}}--label {{$k}}={{$v}} {{end}}' "$v")
    on "$T" "docker volume inspect $v >/dev/null 2>&1 || docker volume create $labels $v >/dev/null"
    VROOT_T=$(on "$T" "docker info --format '{{.DockerRootDir}}'")/volumes
    # live SQLite files inside the volume are skipped by tar and copied with sqlite3_rsync instead
    $READER python3 -I -c 'import os,sys
r=sys.argv[1]
for d,_,fs in os.walk(r):
  for f in fs:
    p=os.path.join(d,f)
    try:
      if os.path.isfile(p) and not os.path.islink(p) and open(p,"rb").read(16)==b"SQLite format 3\x00": print(os.path.relpath(p,r))
    except OSError: pass' "$VROOT_F/$v/_data" > "$WORK/vol-$v.sqlite"
    { cat "$WORK/vol-$v.sqlite"; sed 's/$/-wal/' "$WORK/vol-$v.sqlite"; sed 's/$/-shm/' "$WORK/vol-$v.sqlite"; sed 's/$/-journal/' "$WORK/vol-$v.sqlite"; } | sed 's#^#/#' > "$WORK/vol-$v.exclude.rsync"
    $READER rsync -aH --numeric-ids --delete --exclude-from="$WORK/vol-$v.exclude.rsync" \
      -e "ssh $SSH_OPTS" --rsync-path="$REMOTE_NS rsync" "$VROOT_F/$v/_data/" "$TS_SSH:$VROOT_T/$v/_data/" \
      || [ $? = 24 ] || die "volume rsync failed for $v"
    while read -r rel; do
      [ -n "$rel" ] || continue
      $READER "$HOP_STATE_DIR/bin/sqlite3_rsync" "$VROOT_F/$v/_data/$rel" "$TS_SSH:$VROOT_T/$v/_data/$rel" --ssh "$HOP_STATE_DIR/bin/hop-ssh-ns" --exe /usr/local/bin/sqlite3_rsync \
        || die "sqlite3_rsync failed for volume $v file $rel"
      own=$($READER stat -c '%u:%g %a' "$VROOT_F/$v/_data/$rel")
      ssh $SSH_OPTS "$TS_SSH" "$REMOTE_NS sh -c 'chown ${own% *} \"$VROOT_T/$v/_data/$rel\" && chmod ${own#* } \"$VROOT_T/$v/_data/$rel\"'"
    done < "$WORK/vol-$v.sqlite"
    log "volume $v copied"
  done
  step_time volumes "$ts0"
fi

# ---------- 6. stage user units + system bits (never enabled here; standby-install wires them) ----------
if { want units || want home; } && [ "$FINAL" = 0 ]; then
  ts0=$(date +%s)
  on "$T" "mkdir -p ~/$HOP_STATE_DIR_REL/staged/systemd-user ~/$HOP_STATE_DIR_REL/staged/system"
  rsync -a --delete -e "ssh $SSH_OPTS" "$H/.config/systemd/user/" "$TS_SSH:$H/$HOP_STATE_DIR_REL/staged/systemd-user/"
  # snapshot of what is enabled/running on FROM, used by cutover/test-mode
  systemctl --user list-unit-files --state=enabled --no-legend | awk '{print $1}' > "$WORK/enabled-units.txt"
  systemctl --user list-units --state=running --type=service --no-legend | awk '{print $1}' > "$WORK/running-units.txt"
  docker ps --format '{{.Names}}' > "$WORK/running-containers.txt"
  tailscale serve status --json > "$WORK/serve.json" 2>/dev/null || true
  rsync -a -e "ssh $SSH_OPTS" "$WORK/enabled-units.txt" "$WORK/running-units.txt" "$WORK/running-containers.txt" "$WORK/serve.json" \
     "$TS_SSH:$H/$HOP_STATE_DIR_REL/staged/"
  # compose manifest: how to recreate every running (non-skipped) container on another host
  python3 - "${HOP_COMPOSE_PATHMAP_CONTAINER:-}" "$HOP_CONTAINER_SKIP_REGEX" > "$WORK/compose-projects.tsv" <<'PY2'
import json, re, subprocess, sys
pm_name, skip = sys.argv[1], re.compile(sys.argv[2])
def insp(ids): return json.loads(subprocess.check_output(["docker","container","inspect",*ids]))
names=[n for n in subprocess.check_output(["docker","ps","--format","{{.Names}}"],text=True).split() if not skip.search(n)]
pmap=[]
if pm_name:
    try: pmap=sorted(((m["Destination"],m["Source"]) for m in insp([pm_name])[0]["Mounts"]), key=lambda x:-len(x[0]))
    except Exception: pass
def hp(p):
    for d,s in pmap:
        if p==d or p.startswith(d.rstrip("/")+"/"): return s+p[len(d):]
    return p
projs={}
for c in insp(names):
    L=c["Config"]["Labels"] or {}; p=L.get("com.docker.compose.project")
    if not p: print(f"standalone\t{c['Name'].lstrip('/')}\t{c['Config']['Image']}"); continue
    e=projs.setdefault(p,{"wd":hp(L.get("com.docker.compose.project.working_dir","")),
      "files":",".join(hp(x) for x in L.get("com.docker.compose.project.config_files","").split(",") if x),
      "env":",".join(hp(x) for x in L.get("com.docker.compose.project.environment_file","").split(",") if x),"svc":set()})
    e["svc"].add(L.get("com.docker.compose.service",""))
for p,e in sorted(projs.items()):
    print(f"project\t{p}\t{e['wd']}\t{e['files']}\t{e['env']}\t{' '.join(sorted(e['svc']))}")
import os
fb=set()
for c in insp(names):
    for m in c.get("Mounts",[]):
        if m.get("Type")=="bind" and os.path.isfile(m["Source"]) and not m["Source"].startswith(("/etc/","/proc")): fb.add(m["Source"])
for f in sorted(fb): print(f"filebind\t{f}")
PY2
  rsync -a -e "ssh $SSH_OPTS" "$WORK/compose-projects.tsv" "$TS_SSH:$H/$HOP_STATE_DIR_REL/staged/"
  # system services that live outside $HOME (read-only copy of files; installed disabled by standby-install)
  for u in ${HOP_SYSTEM_UNITS:-}; do
    systemctl cat "$u" 2>/dev/null | grep -v '^# /' > "$WORK/$u" && rsync -a -e "ssh $SSH_OPTS" "$WORK/$u" "$TS_SSH:$H/$HOP_STATE_DIR_REL/staged/system/" || true
  done
  for p in ${HOP_SYSTEM_PATHS:-}; do
    [ -e "$p" ] && rsync -aR --exclude venv/ --exclude backups/ -e "ssh $SSH_OPTS" "$p" "$TS_SSH:$H/$HOP_STATE_DIR_REL/staged/system/root/" || true
  done
  step_time units "$ts0"
fi

# ---------- 7. venv recipes (freeze lists; venvs themselves are rebuilt on TO by standby-install) ----------
if want units || want home || want venvs; then
  ts0=$(date +%s); mkdir -p "$WORK/venvs"; rm -f "$WORK/venvs/"*
  for v in ${HOP_VENVS:-}; do
    [ -f "$v/pyvenv.cfg" ] || continue
    key=$(printf '%s' "$v" | tr '/' '_')
    { echo "#venv $v"; grep -E '^(home|version|version_info)' "$v/pyvenv.cfg" | sed 's/^/#cfg /'; uv pip freeze --python "$v/bin/python" 2>/dev/null; } > "$WORK/venvs/$key.txt" || true
  done
  rsync -a --delete -e "ssh $SSH_OPTS" "$WORK/venvs/" "$TS_SSH:$H/$HOP_STATE_DIR_REL/staged/venvs/"
  step_time venvs "$ts0"
fi

total=$(( $(date +%s) - t0 ))
log "sync $F -> $T done in ${total}s (run $RUN_ID)"
echo "total $total" >> "$WORK/timings-$RUN_ID"
rsync -a -e "ssh $SSH_OPTS" "$WORK/timings-$RUN_ID" "$WORK/sqlite-inventory.tsv" "$TS_SSH:$H/$HOP_STATE_DIR_REL/staged/" 2>/dev/null || true
status "sync $F->$T ${ONLY:-all} ok in ${total}s run=$RUN_ID"
