#!/usr/bin/env bash
# Runs only inside the disposable/persistent isolated Ubuntu guest.
set -euo pipefail
: "${WIZARD_LAUNCH_FIXTURE:?fixture guard}"
: "${AUDIT_STATE:?mounted evidence directory}"
: "${AUDIT_RELEASE:?explicit candidate}"
mkdir -p "$AUDIT_STATE"
curl -fsSL --retry 2 https://aiwizards.com/os.sh -o "$AUDIT_STATE/public-installer.sh"
sha256sum "$AUDIT_STATE/public-installer.sh" > "$AUDIT_STATE/public-installer.sha256"
# No credentials, tailnet enrollment or personal data. All other defaults/pins remain intact.
sudo -n env WIZARD_USER="$(id -un)" WIZARD_MODE=fresh WIZARD_PRIVATE_ACCESS=none \
  WIZARD_RELEASE="$AUDIT_RELEASE" WIZARD_TAILSCALE_WAIT=1 \
  bash "$AUDIT_STATE/public-installer.sh"
