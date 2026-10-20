# Emergency repair: Wizard chat is down

You do not need a working Wizard agent to repair the box. You need **one independent way into the Linux box**, its owner's permission, and either a working Claude Code or Codex CLI login. A local terminal is enough if networking is broken. This runbook is for the current WAM/Runtipi installation; legacy host installs are called out separately. It is not an unattended repair authorization.

## Before something breaks

Keep these outside Wizard, in your password manager or an owner-only note:

- The Mac/physical box access method, Linux guest/host SSH user and address, and SSH key/recovery access. On Mac, repair the **Linux guest**, not macOS, unless the VM itself will not start; use the native application's VM console/access instructions for its installed version. Do not guess a universal VM username or port.
- Your provider sign-in and recovery methods. A subscription is not the same as an already installed, signed-in repair CLI.
- The location of the encrypted off-box backup, its decryption key, backup date, and the tested restore procedure for that backup tool.
- The direct Troubleshooter address, when provisioned. It must bypass the shell and Agent Service. Bookmark it independently of the Wizard launcher.

Read [CREDENTIALS.md](../CREDENTIALS.md). **Never send tokens, .env, raw Docker inspect output, databases or provider verification codes to a support chat.** Health/log output can also contain private names or content; inspect locally and redact before sharing.

## 1. Get an independent terminal

From a device that already has authorized SSH access:

```sh
# Replace both placeholders with your recorded values; do not paste the brackets.
ssh <linux-owner>@<box-address>
id
pwd
command -v wam
command -v docker
```

If SSH or the private network is down, use the box/VM's local console. Do not reset Tailscale, SSH keys or the VM to regain access. If the VM or physical disk cannot be opened, **stop**: this is a host/backup recovery problem, not an agent restart.

Use the installation owner's account. `sudo` is for a specifically justified host operation, not a way to choose a different Wizard home. Keep this terminal open while testing a second recovery session.

## 2. Discover the actual layout, without dumping secrets

```sh
uname -a
whoami
printf 'Wizard home: %s\nRuntipi root: %s\n' "${WIZARD_OS_HOME:-$HOME/.wizard-os}" "${RUNTIPI_ROOT:-$HOME/runtipi}"
wam --help
wam apps --json
wam slots --json
wam alongside --detect
wam links --dry-run --json
wam doctor
# Alongside host Hermes only (fresh boxes use WAM's agent-link checks):
wizard doctor
# Show names, state and port mappings, NOT container environment values.
docker ps -a --format '{{.Names}}\t{{.Status}}\t{{.Ports}}'
df -h
free -h
systemctl --user list-units --all 'wizard*' 'hermes*'
```

`wam apps`, `doctor` and `links --dry-run` are diagnostic, but not byte-for-byte read-only: they may refresh registry/projection files, create a missing API token or operator, or cache observations. `--dry-run` means no Serve route write. Do not run `doctor --fix`, bootstrap, update or restore during initial diagnosis. `wam alongside --detect` reports host Hermes detection; the saved alongside configuration and registry determine which runtime the installed shell actually uses.

Default WAM home is `~/.wizard-os`, Runtipi root `~/runtipi`, store **`wizardapps`**. Overrides win. Read `app-manager.json` and `alongside.json` selectively for paths, ports and mode; treat them as private, not something to paste wholesale. The main fresh Hermes app's data is normally `<runtipi>/app-data/wizardapps/hermes-agent/data`; additional managed agents have their own `agent.json` under `<wizard-home>/agents/<id>`. Do not inspect private agents' contents.

The current installer uses **native host Tailscale + Serve**, not the bespoke Caddy/user-Tailscale gateway on some development boxes. A development Troubleshooter's defaults (`8923`, `8928`, `wizard-mobile.service`, `wizard-interface-candidate`) are **not** a map of every install. Follow the installed registry and mounts.

## 3. Bring your own repair agent

Install a CLI only from its official instructions if absent; inspect the current installer and platform support first. Do not curl an unreviewed repair script into a root shell. References: [Claude Code setup](https://code.claude.com/docs/en/setup), [Codex CLI](https://developers.openai.com/codex/cli/). Use an owner-approved subscription; do not silently spend an API key or switch another agent's provider.

```sh
command -v claude
claude --help
claude auth status
# If signed out, the OWNER completes the interactive flow:
claude auth login
```

Or:

```sh
command -v codex
codex --help
codex login status
# If signed out, the OWNER completes the interactive flow:
codex login
```

Run only the chosen provider's block. Login flags vary by installed CLI version; use its help if an interactive SSH browser cannot open. Never place a password, code or token in a prompt. Never copy refresh tokens from Hermes or a connection app to make the CLI work.

Make a **private** repair working directory outside the owner's files/media. Copy this repo's `docs/repair/AGENTS.md` there as `AGENTS.md` and `docs/repair/PROMPT.md` as `PROMPT.md` using a trusted checkout/download. Also copy this runbook and CREDENTIALS.md, or give the agent their paths. Start interactively in that directory:

```sh
claude
# OR, not both:
codex
```

Paste the [ready-to-paste prompt](repair/PROMPT.md). Claude should explicitly read AGENTS.md too. Keep normal approvals on; **do not use `--dangerously-bypass-approvals-and-sandbox` or bypassPermissions** just because the broken agent previously did. The CLI works outside Hermes/Agent Service. No Wizard MCP connection or model router is required for this recovery session.

## 4. Isolate the broken link

| Symptom | Inspect locally | Smallest next step |
|---|---|---|
| Phone cannot reach any page | `tailscale status`, `tailscale serve status`; console can reach the registry's loopback view? | Reconnect the phone first. If server sign-in expired, owner re-authenticates from a console/second route; never logout the only route. |
| Shell missing, Agent Service health works | Shell container status, its recent logs, registry view URL | Start only the stopped shell through WAM; no provider re-login. |
| Pages load but chat fails | Agent Service `/wizard/health`, upstream `/health`, service and agent logs | Check provider connection app/Test, actual upstream reachability and queue before a restart. |
| Expired Claude/ChatGPT login | Claude/ChatGPT connection page, correct runtime's auth manager | Re-login in the actual source of truth listed in CREDENTIALS; do not reinstall the agent. |
| Disk full | `df -h`, identify specific cache growth without reading private content | Remove only identified disposable caches with approval. Never prune all Docker volumes or delete app-data/DBs. |
| Failed immediately after update | `wam updates`, install status/log, source pins; queue status | Stop the update loop only with owner approval; select a verified previous release/backup using the installed tool. Do not replay unknown accepted runs. |

Use URLs printed by `wam apps --json`, not guessed ports. For example, once the **actual** Agent Service loopback health URL is known:

```sh
curl --fail --silent --show-error --max-time 20 "$AGENT_SERVICE_HEALTH_URL"
```

Set that variable yourself from the installed registry, preserving the full path. A 200 alone is not a successful chat; inspect `status`, upstream reachability and active/queued work. Do not print bearer tokens into the terminal. For protected endpoints let the chosen repair agent use locally loaded secrets without displaying them.

Logs:

```sh
journalctl --user -u wizard-app-manager-api.service --since '-30 min' --no-pager
# Substitute the one discovered container name, not every app:
docker logs --since 30m --tail 150 "$CONTAINER_NAME"
# Host Hermes only, if that unit exists:
journalctl --user -u hermes-gateway.service --since '-30 min' --no-pager
```

Installer progress is `<wizard-home>/install-status.json`, details `<wizard-home>/install.log`; review locally. Hermes logs are under its **actual** home `/logs`. Agent Service logs go to its container or host journal; durable queue/upload locations derive from its environment (`server/index.mjs`), not a single universal guest path.

## 5. Apply one reversible repair

Get approval before a disruptive action. Record what changed and the previous revision/config location. Back up state **off-box and encrypted** before an update or restore; use SQLite online backup or stop its writer, preserving WAL/SHM. Ensure sufficient free space for both target and rollback. Never run two Agent Services writing the same queue/runtime.

For normal Runtipi apps, the current WAM `app_lifecycle` path supports **start, stop and restart** (older help summaries may omit restart). Confirm the installed version before using it. For a stopped shell:

```sh
wam app start wizard-ux
```

For a genuinely broken Agent Service, after checking no active accepted work is being interrupted and obtaining approval:

```sh
wam app restart wizard-agent-service
```

For the WAM API process itself, when its user unit exists:

```sh
systemctl --user restart wizard-app-manager-api.service
```

Host Hermes only, when the API is actually broken and work is idle or the owner accepts interruption:

```sh
systemctl --user restart hermes-gateway.service
```

Do not run `hermes update`, `wam bootstrap`, `wam updates --apply` or rerun the entire installer as a speculative repair. Updates can interrupt the agent and change several app versions. They require a separate plan and rollback point. `wam doctor --fix` also changes state; explain its intended repairs before using it.

### Rollback is layout-specific

- **Normal app update/restore:** WAM forwards `wam app list-backups <app>` / `wam app restore ...` to the installed Runtipi CLI. First run `wam app restore --help` and `wam app list-backups --help` to learn that version's exact restore arguments, then select the verified backup. This document deliberately supplies no invented backup identifier or restore flag. Review what the backup includes; app backup is not whole-box/host/credential recovery.
- **Legacy bundled-shell split only:** `wam shell-split --rollback` is implemented, but applies only to a box retaining `wizard-shell`. It stops the split apps and starts the original bundle on its retained state. Work created after the split stays in the split Service folder; do not merge/erase it or run two writers.
- **Legacy host Agent Service deployment only:** if `~/.local/bin/wizard-agent-service-deploy` and its recorded releases/current layout actually exist, its existing `--rollback` path is the host Troubleshooter's action. That helper is not shipped by a normal WAM container install; do not invent it on a fresh box. Preserve queue state and reconcile ambiguous deliveries before reverting a source version.
- **Whole-box restore:** stop writers, verify the backup/key on a separate disposable target, restore by the chosen backup system's documented command, isolate outbound messaging/schedulers until verified, then cut over with only one active writer. WAM has no universal whole-box undo command. If backup coverage/key/restore instructions are missing, stop and report the exact gap rather than resetting the installation.

## 6. Prove recovery and leave a way back

1. Re-run the checks that failed, `wam doctor` and `wizard doctor`. Distinguish pre-existing unrelated FAILs.
2. Open the shell from the owner's phone and send a synthetic message through the intended provider. Read its real reply; a health-only pass is insufficient.
3. Verify the direct independent repair entry still opens. Close the repair terminal only after a second access path works.
4. Confirm preserved chats/files, provider account identity and queue state without exposing private agents. Explain any owner re-login or full fresh-box/restore acceptance still pending.
5. Report cause, exact changes, evidence, rollback point and remaining gate. Never call a reset or empty registry a successful recovery.

## Troubleshooter distribution gate

The existing Troubleshooter runs directly on the host, executes the owner's native Claude/Codex, invokes systemd/Docker and can undo a host deploy. **Putting that service inside a normal sandboxed app container cannot give it those host powers.** App format rule 12 intentionally rejects Docker socket, home/system mounts, host network/PID and privileged containers. Do not weaken the checker or mount the Docker socket just to make the package pass.

A safe distributable package needs a normal app-facing container plus a separately provisioned, explicitly trusted host repair component and independent owner authentication/route. The route must bypass Agent Service, shell and model router; the host component must discover fresh/alongside layouts. The current private repo and host-only installation are not evidence that a new owner's box has this path. Distribution PRs must carry this gate until a fresh installation proves host provisioning, owner-only chat, real re-login, surviving agent failure, update and recovery. See [source audit](REPAIR-SOURCE-AUDIT.md).
