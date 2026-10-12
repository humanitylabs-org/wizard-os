#!/usr/bin/env bash
# Box A baseline: stock Hermes (public installer) + owner sentinels, then sha256 baseline. Runs as the VM's lima user.
set -euo pipefail
E=~/evidence; mkdir -p "$E"
{
echo "== $(date -u +%FT%TZ) $(uname -m) $(. /etc/os-release; echo $PRETTY_NAME)"
command -v hermes >/dev/null || curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash -s -- --non-interactive --skip-browser --skip-computer-use
export PATH="$HOME/.local/bin:$PATH"
hermes --version
H=~/.hermes
# Owner sentinels (as round 2): commented config + sentinel MCP entry, SOUL.md, a skill, an auth stand-in.
grep -q 'owner sentinel' "$H/config.yaml" || cat >> "$H/config.yaml" <<'YML'
# owner sentinel: this comment and the entry below must survive install + unlink
mcp_servers:
  sentinel:
    url: http://127.0.0.1:9/mcp
    enabled: false
YML
hermes config get mcp_servers.sentinel.url || true
echo "Owner soul sentinel $(date -u +%s)" > "$H/SOUL.md"
mkdir -p "$H/skills/sentinel-skill"; printf -- '---\nname: sentinel-skill\ndescription: owner sentinel\n---\nkeep me\n' > "$H/skills/sentinel-skill/SKILL.md"
echo '{"sentinel": true}' > "$H/auth-sentinel.json"; chmod 600 "$H/auth-sentinel.json"
grep -q '^API_SERVER_ENABLED' "$H/.env" 2>/dev/null || { echo 'API_SERVER_ENABLED=true' >> "$H/.env"; }
chmod 600 "$H/.env"
hermes gateway install >/dev/null 2>&1 || true
systemctl --user restart hermes-gateway 2>/dev/null || hermes gateway restart || true
sleep 5; systemctl --user is-active hermes-gateway || true
cd "$H" && sha256sum config.yaml .env SOUL.md skills/sentinel-skill/SKILL.md auth-sentinel.json | tee "$E/sha.before"
} 2>&1 | tee "$E/a-00-baseline.log"
