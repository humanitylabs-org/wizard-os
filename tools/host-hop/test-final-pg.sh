#!/bin/bash
# Exercise the ACTUAL final-PG block of sync.sh with disposable, networkless PostgreSQL.
# No production container/service/role/Serve/firewall is changed, but it needs a real second machine:
#   HOP_TEST_TARGET=<host key from HOP_HOSTS> bash test-final-pg.sh
# Without HOP_TEST_TARGET it skips. Never point it at a machine that is a live main.
if [ -z "${HOP_TEST_TARGET:-}" ]; then echo 'SKIP test-final-pg: set HOP_TEST_TARGET=<standby host key> to run against a real remote'; exit 0; fi
. "$(dirname "$0")/lib.sh"
T="$HOP_TEST_TARGET"; known_host "$T"; is_self "$T" && die 'HOP_TEST_TARGET must be another machine'
FIX="$HOP_HOME/.cache/host-hop-pg-fixture-$(date +%s)"
mkdir -p "$FIX/pg" "$FIX/work"
NAME=host-hop-pg-fixture-test
IMAGE=$(docker container inspect --format '{{.Image}}' "$HOP_PG_CONTAINER")
[ -z "$(docker ps -aq --filter name=^/$NAME$)" ] || die 'fixture container name occupied'
cleanup() {
 docker rm -f "$NAME" >/dev/null 2>&1 || true
 on "$T" "docker rm -f '$NAME' >/dev/null 2>&1 || true; $(hop_ns_sudo_prefix) rm -rf '$FIX'" || true
 hop_ns_exec rm -rf "$FIX" 2>/dev/null || "$HOP_HOME/bin/rootlesskit" --net=host -- rm -rf "$FIX"
}
trap cleanup EXIT
# Extract exact reviewed final-PG code, not a reimplementation.
python3 - "$HOP_DIR/sync.sh" "$FIX/pg-block.sh" <<'PY'
import pathlib,sys
s=pathlib.Path(sys.argv[1]).read_text();start=s.index('if want pg &&');end=s.index('# ---------- 4. images:',start)
pathlib.Path(sys.argv[2]).write_text(s[start:end])
PY
docker run -d --name "$NAME" --network none -e POSTGRES_HOST_AUTH_METHOD=trust -v "$FIX/pg:/var/lib/postgresql/data" "$IMAGE" >/dev/null
for _ in $(seq 1 40); do docker exec "$NAME" pg_isready -U postgres >/dev/null 2>&1 && break; sleep 1; done
docker exec "$NAME" psql -v ON_ERROR_STOP=1 -U postgres -c 'create table hop_probe(id int primary key); insert into hop_probe values (731);' >/dev/null
# Target preimage must survive a failed live-PG copy and remain as before-final on success.
on "$T" "$(hop_ns_sudo_prefix) mkdir -p '$FIX/pg'; printf 'previous-target\n' > '$FIX/pg/prior-marker'"
HOP_PG_CONTAINER="$NAME"; HOP_PG_USER=postgres; HOP_PG_DATADIR="${FIX#"$HOP_HOME"}/pg"
PGD="$FIX/pg"; H="$HOP_HOME"; WORK="$FIX/work"; RUN_ID=fixture; FINAL=1; TS_SSH=$(host_ssh "$T")
READER=$(hop_ns_reader_prefix); REMOTE_NS=$(hop_ns_sudo_prefix); SSH_OPTS="$HOP_SSH_BASE"
want() { [ "$1" = pg ]; }; step_time() { :; }
set +e
(bash -c 'exit 0'; . "$FIX/pg-block.sh") >/dev/null 2>&1
rc=$?
set -e
[ "$rc" != 0 ] || die 'live PostgreSQL unexpectedly accepted'
on "$T" "test -f '$FIX/pg/prior-marker'" || die 'live-PG failure changed target preimage'
echo 'PASS live PostgreSQL refused, previous target retained'
FINAL=0
. "$FIX/pg-block.sh"
on "$T" "test -f '$FIX/pg.warm-before-fixture/prior-marker'" || die 'warm backup did not retain predecessor'
echo 'PASS online pg_basebackup manifest verified before publication, predecessor retained'
FINAL=1; RUN_ID=fixture-final
docker stop -t 60 "$NAME" >/dev/null
. "$FIX/pg-block.sh"
on "$T" "$(hop_ns_sudo_prefix) test -f '$FIX/pg.before-final-fixture-final/PG_VERSION'" || die 'previous target not retained'
on "$T" "docker run -d --name '$NAME' --network none -e POSTGRES_HOST_AUTH_METHOD=trust -v '$FIX/pg:/var/lib/postgresql/data' '$IMAGE' >/dev/null"
for _ in $(seq 1 40); do on "$T" "docker exec '$NAME' pg_isready -U postgres >/dev/null 2>&1" && break; sleep 1; done
value=$(on "$T" "docker exec '$NAME' psql -U postgres -Atc 'select id from hop_probe'")
[ "$value" = 731 ] || die 'restored row mismatch'
on "$T" "docker stop -t 60 '$NAME' >/dev/null; docker rm '$NAME' >/dev/null"
# Lesson 4: every attempt names its own backups; an earlier before-final must not block a later run.
FINAL=1; RUN_ID=fixture-final-2
. "$FIX/pg-block.sh"
on "$T" "$(hop_ns_sudo_prefix) test -f '$FIX/pg.before-final-fixture-final-2/PG_VERSION'" || die 'second final run did not retain predecessor'
echo 'PASS repeated final copy succeeds when an earlier before-final exists'
echo 'PASS stopped PostgreSQL copied, checksums verified, control state shut down, previous target retained, restored SQL row=731'
