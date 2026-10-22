#!/usr/bin/env bash
# Hermes stable-candidate test (docs/HERMES_STABLE.md, step 2): one fresh Lima VM on Thales, stock Hermes
# images pinned by digest, the pinned Wizard Agent Service and shell, and a deterministic fake model.
#
#   tools/acceptance/hermes/run.sh <candidate image@digest> <current pin image@digest>
#
# Env: WORK (default /Volumes/ThalesMedia/wizard-os/hermes-stable), WAS_IMAGE, UX_IMAGE, FAKE_IMAGE (all by
# digest), KEEP_VM=1 to leave the VM running. Writes $WORK/runs/<UTC stamp>/{results.json,RECEIPT.md,evidence/}.
# To wait for Thales' shared heavy-worker lock first: CANDIDATE=... FROM=... WIZARD_WORK_ROOT=... locked.py Images are fetched on the host and side-loaded,
# digest-checked, because GHCR blob downloads fail inside the vz guest (TLS "bad record MAC").
set -euo pipefail
export PATH=/opt/homebrew/bin:$PATH
HERE=$(cd "$(dirname "$0")" && pwd)
CANDIDATE=${1:-${CANDIDATE:?candidate image@sha256:...}}
FROM=${2:-${FROM:?current pin image@sha256:...}}
WORK=${WORK:-/Volumes/ThalesMedia/wizard-os/hermes-stable}
WAS_IMAGE=${WAS_IMAGE:-ghcr.io/humanitylabs-org/wizard-agent-service@sha256:cb92d01c5656e89f8280e54f6972bc486de3d04f1e50203e00c8acf0d8bb0389}
UX_IMAGE=${UX_IMAGE:-ghcr.io/humanitylabs-org/wizard-ux@sha256:c60920e7da9fadbc7d9c322c26df6068c9fa505eb30cf1cf6e9829268acfebec}
FAKE_IMAGE=${FAKE_IMAGE:-python@sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
RUN=$WORK/runs/$STAMP
VM=hs-$(echo "$STAMP" | tr 'A-Z' 'a-z' | tr -cd 'a-z0-9' | tail -c 12)
export LIMA_HOME=$WORK/lima
mkdir -p "$RUN/harness" "$WORK/images" "$LIMA_HOME"
cp "$HERE"/{check.py,fake_model.py,fetch_image.py,render_lima.py,lima.yaml} "$RUN/harness/"
exec > >(tee -a "$RUN/run.log") 2>&1
echo "run $STAMP vm $VM candidate $CANDIDATE from $FROM"

# 1. Fetch every image on the host, digest-verified, into a shared cache.
tags=()
for ref in "$CANDIDATE" "$FROM" "$WAS_IMAGE" "$UX_IMAGE" "$FAKE_IMAGE"; do
  f="$WORK/images/$(echo "$ref" | tr '/:@' '___').tar"
  [ -s "$f" ] || python3 "$HERE/fetch_image.py" "$ref" "$f.part" > "$f.json"
  [ -s "$f.part" ] && mv "$f.part" "$f"
  tags+=("$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["tag"])' "$f.json")")
done
printf '%s\n' "${tags[@]}"

# 2. Fresh VM.
python3 "$RUN/harness/render_lima.py" "$WORK" "$RUN/harness/lima.rendered.yaml"
limactl create --tty=false --name "$VM" "$RUN/harness/lima.rendered.yaml"
cleanup() { [ "${KEEP_VM:-0}" = 1 ] || { limactl stop -f "$VM" >/dev/null 2>&1; limactl delete -f "$VM" >/dev/null 2>&1; }; }
trap cleanup EXIT
limactl start --tty=false "$VM"
vm() { limactl shell --workdir / "$VM" sudo "$@"; }
vm sh -c 'until docker info >/dev/null 2>&1; do sleep 2; done; docker version --format "docker {{.Server.Version}}"; uname -a'
for ref in "$CANDIDATE" "$FROM" "$WAS_IMAGE" "$UX_IMAGE" "$FAKE_IMAGE"; do
  vm docker load -i "$WORK/images/$(echo "$ref" | tr '/:@' '___').tar"
done

# 3. Checks (update from the current pin, run, roll back), then the receipt.
set +e
vm python3 "$RUN/harness/check.py" --image "${tags[0]}" --from-image "${tags[1]}" --was-image "${tags[2]}" \
  --ux-image "${tags[3]}" --fake-image "${tags[4]}" --out "$RUN"
rc=$?
set -e
python3 - "$RUN" "$CANDIDATE" "$FROM" "$VM" "$(hostname)" <<'PY'
import json, sys, pathlib
run, cand, frm, vm, host = sys.argv[1:]
r = json.loads(pathlib.Path(run, "results.json").read_text())
ok = all(c["pass"] for c in r["checks"]) and len(r["checks"]) == 7
lines = [f"# Hermes stable-candidate test — {'PASS' if ok else 'FAIL'}", "",
         f"- Candidate: `{cand}` ({r.get('version')})", f"- Updated from and rolled back to: `{frm}` ({r.get('from_version')})",
         f"- Agent Service: `{r['was_image']}`", f"- Shell (Markdown renderer): `{r['ux_image']}`",
         f"- Fresh VM `{vm}` on `{host}`, {r['started']} → {r.get('finished')}", "- Model: deterministic fake (fake_model.py), no accounts or paid inference", ""]
for c in r["checks"]:
    lines.append(f"- {'PASS' if c['pass'] else 'FAIL'} — {c['check']}: {c['detail']}")
for o in r.get("observations", []):
    lines.append(f"- Observation — {o['topic']}: {o['detail']}")
pathlib.Path(run, "RECEIPT.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
PY
exit $rc
