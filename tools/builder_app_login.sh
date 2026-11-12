#!/bin/bash
# Release train (12 Nov 2026): log gh and git in as the GitHub App WizardOS Builder (wizardos-builder[bot]) and keep
# the 1-hour installation token fresh for the rest of the job (a promote runs up to ~3h). gh and git read gh's
# hosts.yml on every call, so GH_TOKEN must stay unset. Needs BUILDER_APP_KEY (the app's private key PEM).
set -euo pipefail
[ -n "${BUILDER_APP_KEY:-}" ] || { echo "::error::BUILDER_APP_PRIVATE_KEY is not set on $GITHUB_REPOSITORY (docs/RELEASE_AUTOMATION.md)"; exit 1; }
python3 -c "import cryptography" 2>/dev/null || pip install -q --user cryptography
K="$RUNNER_TEMP/builder-app.pem"; umask 077; printf '%s\n' "$BUILDER_APP_KEY" > "$K"
T="$(cd "$(dirname "$0")" && pwd)/builder_app_token.py"
login() { python3 "$T" "$K" | gh auth login -h github.com -p https --with-token; }
login; gh auth setup-git
nohup bash -c "while sleep 1500; do python3 '$T' '$K' | gh auth login -h github.com -p https --with-token || true; done" >/dev/null 2>&1 &
echo "logged in as wizardos-builder[bot]; the token refreshes every 25 minutes"
