#!/usr/bin/env bash
# Wizard OS two-box acceptance (wizard-os#29). Run on Thales against two Lima VMs:
#   box A = Ubuntu 24.04 with stock Hermes already installed (the cohort's shape), box B = fresh Ubuntu 24.04.
#
#   two_box.sh <step> [<vm>]      run one step inside a VM, evidence to ~/evidence/<step>.log in the VM
#   two_box.sh status             print every step, what it proves and what gates it
#
# Environment: LIMA_HOME (VMs live there), WIZARD_RELEASE (default: stable), WIZARD_RELEASE_BASE (default: wizard-os
# main releases/), WAM_GET (get.sh URL, default App Manager main). Steps never touch a real user's box.
set -euo pipefail
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH

# step | box | proves | gated by (empty = runnable on today's main)
STEPS=$(cat <<'EOF'
baseline|A|stock Hermes + owner sentinels (commented config, sentinel MCP entry, SOUL.md, skill, auth stand-in); sha256 baseline|
install|A,B|one public command; A goes alongside, B fresh; exit code truthful|WAM#19 (truthful outcome), WAM#20 + OS#33 (pins)
pins|A,B|~/.wizard-os/release.json: App Manager commit + image digests PASS against the release|WAM#20 + OS#33; wizard-os public or releases served publicly (DECISIONS #14)
doctor|A|wizard doctor all PASS incl. live wizard_apps through the gateway|relink key mismatch (wizard-os#28 comment, 12 Oct)
containers|A,B|agent-service and shell are two containers with their own digests; shell restart keeps a run alive|service#4
chat|A|a typed chat from the shell API lands in box A's own Hermes state.db and uses an app tool|needs a model route for the VM
private-url|A|installer prints a tailnet URL; a second device opens shell + one app; public interface closed|WAM#18
store|A|Get Apps opens the standalone Store window with the live index; Back never leaves Wizard|ux#2
app-install|A|install from the Store via the authenticated Service -> WAM -> Runtipi; tile opens; host Hermes calls its tool; no Hermes restart|service#11
files|A|upload in the shell; host Hermes reads the same bytes|service#12
voice|A|dictation through the local transcriber; bootstrap and status agree; screen context reaches the run|service#13
background|A|a reply finishing while the service is down arrives exactly once after restart|service#14
build-share|A,B|"build me a habit tracker" -> staged app with UI+API+MCP on A; prepared publication; B installs the same candidate|WAM#16
custom-view|A|customise an app's view, update the app, customisation survives or is resolved; revert works|OS#30
restart|A,B|reboot: Hermes, service, shell come back; first chat after boot uses app tools (park/self-probe <=5 min)|
link-faults|A|kill/raise at each link step with the real hermes plugins install; unlink or next link restores bytes|OS#31 (passed on Thales 12 Oct; evidence/release-pins-27/a-06)
unlink|A|wizard unlink --restart: config.yaml, .env, SOUL.md, skill, auth stand-in byte-identical to baseline; hermes chat still works|
EOF
)

if [ "${1:-}" = status ] || [ -z "${1:-}" ]; then
  printf '%-12s %-4s %s\n' STEP BOX "PROVES  [gated by]"
  while IFS='|' read -r step box proves gate; do
    printf '%-12s %-4s %s%s\n' "$step" "$box" "$proves" "${gate:+  [gated by: $gate]}"
  done <<<"$STEPS"
  exit 0
fi

step=$1; vm=${2:?vm name}
run_in() { limactl shell --workdir / "$vm" -- bash -lc "$1"; }
case "$step" in
  baseline) run_in "$(cat "$(dirname "$0")/steps/baseline.sh")" ;;
  install|pins) run_in "export WIZARD_RELEASE='${WIZARD_RELEASE:-}' WIZARD_RELEASE_BASE='${WIZARD_RELEASE_BASE:-}';
      curl -fsSL '${WAM_GET:-https://raw.githubusercontent.com/humanitylabs-org/wizard-app-manager/main/get.sh}' -o /tmp/get.sh;
      mkdir -p ~/evidence; bash /tmp/get.sh </dev/null 2>&1 | tee ~/evidence/install.log; echo exit \${PIPESTATUS[0]};
      cat ~/.wizard-os/release.json 2>/dev/null || echo 'no release.json (unpinned install)'" ;;
  doctor) run_in 'export PATH=$HOME/.local/bin:$PATH; wizard doctor 2>&1 | tee ~/evidence/doctor.log' ;;
  unlink) run_in 'export PATH=$HOME/.local/bin:$PATH; wizard unlink --restart 2>&1 | tee ~/evidence/unlink.log;
      cd ~/.hermes && sha256sum -c ~/evidence/sha.before 2>&1 | tee -a ~/evidence/unlink.log;
      cmp ~/.hermes/config.yaml ~/evidence/config.yaml.before && echo config.yaml byte-identical' ;;
  *) gate=$(awk -F'|' -v s="$step" '$1==s{print $4}' <<<"$STEPS")
     echo "step $step is not scripted yet${gate:+; gated by: $gate}"; exit 2 ;;
esac
