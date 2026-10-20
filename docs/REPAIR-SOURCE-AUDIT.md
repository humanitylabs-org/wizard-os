# Repair-kit source and command audit

Reviewed against current source on 20 October 2026. **Self-check**, not an independent reviewer and not a fresh-box acceptance run. Read-only source inspection plus CLI help was used; no live owner credentials, service restart, login, update, rollback or restore was exercised.

## Source revisions

| Repository | Reviewed revision |
|---|---|
| wizard-app-manager | [`23e4090bf329a6b47732f4ea16f80e607df3abbd`](https://github.com/humanitylabs-org/wizard-app-manager/tree/23e4090bf329a6b47732f4ea16f80e607df3abbd) |
| wizard-agent-service | [`142bcad047baf4b4badd8ba934aa0117cc7a8758`](https://github.com/humanitylabs-org/wizard-agent-service/tree/142bcad047baf4b4badd8ba934aa0117cc7a8758) |
| wizard-troubleshooter (private) | [`b5c555fd1f9b19216d2b3b64530c8163e27ca7b4`](https://github.com/humanitylabs-org/wizard-troubleshooter/tree/b5c555fd1f9b19216d2b3b64530c8163e27ca7b4) |
| claude-connection | [`3b2d6186b86a896f254150ad056b9eaa495e738e`](https://github.com/oscarhenrycollins/claude-connection/tree/3b2d6186b86a896f254150ad056b9eaa495e738e) |
| chatgpt-connection | [`f87d5ddc449535418ee92ebeb24aaec36cc58058`](https://github.com/oscarhenrycollins/chatgpt-connection/tree/f87d5ddc449535418ee92ebeb24aaec36cc58058) |
| wizard-os contracts | `860d0f442179f32c6644076d679e1fce448bb436` |

## Command-by-command check

All Wizard-specific runnable commands in REPAIR.md are covered below. Generic host commands (`ssh`, `id`, `pwd`, `command -v`, `uname`, `whoami`, `printf`, `df`, `free`, `systemctl`, `journalctl`, `docker ps/logs`, `curl`) use their native tools, not invented WAM wrappers. They are Linux-box instructions; `free` and systemd do not run on the Mac host. Placeholders and URL/container variables must be populated from the actual box, not evaluated literally.

| Command or claim | Source checked / result |
|---|---|
| `wam --help` | `wam/cli.py` module description, `main()` and parser. Help executed successfully in an isolated dependency environment. |
| `wam apps --json`, `wam slots --json` | `wam/cli.py` parser and dispatch; `write_registry()` writes apps.json; `wam/slots.py` loads defaults and capabilities. Not treated as strictly read-only. |
| `wam alongside --detect` | `wam/cli.py:alongside_cmd()` and parser; `wam/alongside.py:detect()`. Help executed. Detection precedes provision; not `--off`. |
| `wam links --dry-run --json` | `wam/cli.py` links parser and `wam/links.py:publish()` dry-run. Does not reset Serve. Registry/config side effects explicitly noted. |
| `wam doctor`, `wam doctor --fix` warning | `wam/cli.py:doctor()`: fix installs/repairs bundles and can ensure a store; no-fix still calls `Config.runtipi()` / operator discovery. Help executed. |
| `wizard doctor`, `wizard link`, `wizard unlink` warnings | `wizard-cli/wizard:cmd_doctor()` and parser. It reads host Hermes link/config and makes a live bridge request; runbook restricts it to alongside mode. Link/unlink are mutations, not diagnosis. |
| `wam app start/stop/restart <app>` | `wam/cli.py:LIFECYCLE_WANT`, `app_lifecycle()` and `main()`: all three verbs go through the authenticated Runtipi API. Exact app IDs are shell `wizard-ux`, Service `wizard-agent-service`. The module's older help summary omits restart, so source was checked rather than trusting that summary. |
| `wam app update`, `--no-backup` warning | `wam/cli.py:app_update()` uses API update and preserves running state; backup default true. Not executed as part of this documentation change. |
| `wam app list-backups --help`, `wam app restore --help`, `wam reset-password --help` | `wam/cli.py:RUNTIPI_COMMANDS`, `runtipi_cli()` forwards to the installed binary; WAM help lists backup/restore. The actual Runtipi binary is box/version-dependent, so no invented backup ID or restore/reset flag is supplied. |
| `wam shell-split --rollback` | `wam/cli.py:shell_split()` rollback path and source help. Legacy bundle only; newer split writes are not automatically merged back. |
| `wam updates`, apply/installer warning | `wam/updates.py:status()/apply()` and `get.sh`. Apply runs the installer; not a read-only repair. |
| `systemctl --user restart wizard-app-manager-api.service` | `install.sh` creates/enables/restarts exactly this user unit. Requires the owner's user systemd session. |
| `hermes-gateway.service`, native host rollback helper | Existing Troubleshooter `lib/checks.mjs` and `REPAIR_PROMPT.md`. This is host-layout-specific, explicitly not installed by the normal Runtipi app. No fabricated universal rollback binary. |
| Health path `/wizard/health` | Agent Service `server/index.mjs`, `server/service.mjs`, Runtipi recipe and Dockerfile. Actual URL/port comes from the registry. Health alone is not a real chat. |
| `claude auth login/status` | Installed Claude Code `claude auth --help` verified login/status subcommands. No actual owner login changed. Official setup URL supplied; installed version help wins. |
| `codex login`, `codex login status` | Installed `codex login --help` verified login/status and interactive/device auth options. No credential copied or login changed. |
| `hermes auth list/add openai-codex` | Installed `hermes auth --help` and `hermes auth list --help` verified add/list and optional provider filter. ChatGPT app MCP explicitly advises `hermes auth add openai-codex` for a host agent. Latest authoritative docs: [Hermes](https://hermes-agent.nousresearch.com/docs/). |
| `sudo tailscale up`, `tailscale status/serve status` | `scripts/setup-private-access.sh` calls standard host Tailscale and explicitly preserves settings. Runbook requires an independent path before network re-authentication. |

## Credential/path audit

- `wam/cli.py:Config`: home registry, **app-manager.json** (not config.json), RUNTIPI_ROOT override, default `~/runtipi`, port 7790, secrets and api-token. `Handler.token` is loaded when serve starts, so rotation requires restart.
- `wam/runtipi.py:from_install()/ensure_operator()`: Runtipi `.env` / JWT_SECRET, operator login and 0600 credential record. Exact store constant is **wizardapps** in cli.py.
- `wam/cli.py:build_form()` and `wam/alongside.py`: generated app password records, alongside state, API_SERVER_KEY, MCP token, user-config overrides. `wam/host_dashboard.py` supplies generated dashboard password/signing secret and consumer propagation.
- `wam/claude_login.py`: actual configuration-directory precedence and no copied refresh token. Claude recipe uses the fixed shared login volume. ChatGPT recipe targets the actual Hermes dashboard and holds no provider OAuth token.
- Agent Service `server/index.mjs`: secret environment/file names, default queue/upload SQLite paths and owner proof; `server/app-bindings.mjs` app-scoped delivery tokens. No universal rotate-all helper exists.
- Troubleshooter `lib/checks.mjs`, `lib/repair.mjs`, `server.mjs`: host-default probes/actions, native CLI paths, private state, guardian token and peer gate. Its process-level ping does not prove host repair readiness. Existing repair CLIs are run with broad permission bypass; the manual runbook deliberately does **not** inherit that policy.
- `spec/WIZARD_ID.md`: signing identity is phone-side; spec is a contract, not proof of deployed phone backup. Build publisher secrets must not be copied to each box.

## Limits of this evidence

The kit names no universal whole-box backup/restore command because current WAM does not supply one. Restore syntax must come from the installed backup tool and a real isolated rehearsal. Likewise, a private host-only Troubleshooter cannot be declared a working every-box app just because a manifest or default slot exists. Full fresh-install, independent owner auth, real model repair, phone, update and off-box restore remain launch acceptance gates.
