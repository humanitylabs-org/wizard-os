#!/bin/bash
# 03 (as wizard): `wam install humanitylabs-org/wisdom` through the real private-repo path (token on stdin, env only).
set -uo pipefail
W=/Volumes/ThalesMedia/wizard-os/wisdom-63
exec > >(tee $W/receipts/03-install.log) 2>&1
export PATH="$HOME/.local/bin:$PATH"
read -r GITHUB_TOKEN; export GITHUB_TOKEN
SHA=$1
date -u +%FT%TZ
# PR #10 is unmerged; the private path installs the default-branch HEAD. Pin only that choice (head_commit -> the PR
# head SHA). Fetch, wizard.md check, compose risk check, store compile, Runtipi install, registry and skill copy are
# the unmodified `wam install` path.
# The private prerelease image is loaded locally (README install contract: "Registry access is not implied").
# Stock Runtipi install runs `compose down --rmi all` before `up`; a stopped retention container keeps the exact
# Thales-built image from being deleted (documented archive-only pattern), so `up` uses it with no pull.
docker rm -f wisdom-image-retain >/dev/null 2>&1; docker create --name wisdom-image-retain ghcr.io/humanitylabs-org/wisdom:0.3.0-private.5 true >/dev/null && echo "retention container: $(docker inspect -f '{{.Image}}' wisdom-image-retain)"
ls -ld ~/runtipi/repos/wizardapps/apps 2>&1
if [ -d ~/runtipi/repos/wizardapps/apps ] && [ "$(stat -c %U ~/runtipi/repos/wizardapps/apps)" != wizard ]; then
  echo "FINDING: store apps dir not owned by wizard; handing it to the box user (known App Manager issue)"; sudo chown wizard:wizard ~/runtipi/repos/wizardapps/apps
fi
cd ~/wizard-app-manager
time python3 -c "import sys, wam.private as p; p.head_commit=lambda repo, tok: '$SHA'; from wam.cli import main; sys.exit(main(['install','humanitylabs-org/wisdom']))" 2>&1 | grep -v -i token; echo "WAM-INSTALL-EXIT=${PIPESTATUS[0]}"
cd ~
unset GITHUB_TOKEN
cat ~/runtipi/repos/wizardapps/apps/wisdom/.wizard-commit 2>/dev/null; echo; cat ~/runtipi/repos/wizardapps/apps/wisdom/.wizard-source 2>/dev/null; echo
ls ~/runtipi/repos/wizardapps/apps/wisdom/
python3 - <<'PY'
import json; from pathlib import Path
a=[x for x in json.loads((Path.home()/'.wizard-os/apps.json').read_text())['apps'] if x['id']=='wisdom']
print('apps.json wisdom:', json.dumps({k:a[0].get(k) for k in ('status','version','commit','view','api','mcp','skill','provides','recommends')} if a else None))
PY
ls -la ~/.wizard-os/skills/wisdom/ ~/runtipi/app-data/wizard-os/skills/wisdom/ 2>&1
sha256sum ~/.wizard-os/skills/wisdom/SKILL.md ~/wisdom/skill/SKILL.md
docker ps --filter name=wisdom --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}'
C=$(docker ps -q --filter name=wisdom_wizardapps-wisdom)
echo "running image $(docker inspect -f '{{.Image}}' $C) built $(docker image inspect ghcr.io/humanitylabs-org/wisdom:0.3.0-private.5 -f '{{.Id}}')"
docker exec $C sh -c 'grep -E "^(Uid|CapEff)" /proc/1/status'
docker inspect $C --format 'readonly={{.HostConfig.ReadonlyRootfs}} capdrop={{.HostConfig.CapDrop}}'
date -u +%FT%TZ
