# The `wizard` CLI

One generic command for people and scripts to use any installed Wizard app's MCP tools. Apps ship MCP and never their own CLI ([ARCHITECTURE](../docs/ARCHITECTURE.md): "MCP over HTTP is the one way agents use apps"). This is the one CLI that sits on top of them.

- **Source:** [`tools/wizard`](../tools/wizard). A single file, Python 3.9+ standard library only.
- **Owner:** James + Archimedes.
- **Not** the agent's path to apps. The Agent Service registers each app's MCP with the agent (Jan). This CLI is for humans, scripts, cron jobs and break-glass.

## Install

```sh
sh tools/install_wizard_cli.sh                 # -> ~/.local/bin/wizard
sh tools/install_wizard_cli.sh --name wizard-os   # if something else is already called `wizard`
sh tools/install_wizard_cli.sh --prefix /usr/local/bin
```

The installer only replaces a file that is itself this CLI (it carries the marker `wizard-os-generic-cli`). If `DIR/wizard` is a different program it exits 1 and leaves it alone. You can also run `python3 tools/wizard …` straight from a checkout.

## Commands

```
wizard apps list [--json]
wizard tools <app> [--json]                   every tool: name, description, inputSchema, annotations
wizard tools <app>.<tool> [--json]            one tool's full definition
wizard call <app>.<tool> [ARGS] [--json]
```

`ARGS` is the tool's arguments as **one JSON object**:
- inline: `wizard call defleur-video.get_status '{"job_or_project": "p_123"}'`
- `-` reads the object from stdin: `jq -n '{a: 1, b: 2}' | wizard call calc.add -`
- `@file` reads it from a file: `wizard call calc.add @args.json`
- omitted means `{}`.

Anything else (bad JSON, an array, a number, an unreadable file) fails with `bad_arguments` before any network call. Before calling, the CLI checks `ARGS` against the tool's `inputSchema`: required keys, top-level JSON types, and extra keys when the schema sets `additionalProperties: false`. The app still runs its own validation.

Options work before or after the subcommand:

| Option | Env | Default | Meaning |
|---|---|---|---|
| `--json` | | off | Machine-readable output (below) |
| `--registry PATH` | `WIZARD_APPS_JSON` | `$WIZARD_OS_HOME/apps.json`, else `~/.wizard-os/apps.json` | Which registry to read |
| `--endpoint url\|internal` | `WIZARD_MCP_ENDPOINT` | `url` | `mcp.url` (from the host) or `mcp.internal` (from a container on the app network) |
| `--timeout SECONDS` | `WIZARD_TIMEOUT` | `120` | Per HTTP request |

## Linking an existing Hermes (alongside mode)

`spec/AGENT_BRIDGE.md` → "Installing over an existing Hermes". The installer runs these for you in alongside mode; they also work by hand.

```
wizard link [--restart]     connect this box's Hermes to the apps
wizard unlink [--restart]   reverse exactly what link changed
wizard doctor               PASS/FAIL lines + one live request through the bridge
```

`link` backs up `~/.hermes/config.yaml` and records every change in `~/.wizard-os/linked.json`. It makes three stock-config edits, through Hermes's own Python and ruamel round-trip so comments and layout survive:
1. `mcp_servers.wizard` (the gateway URL, plus a bearer header reading `${WIZARD_MCP_TOKEN}`);
2. `skills.external_dirs += ~/.wizard-os/skills`;
3. `plugins.enabled += wizard-os` (installed with stock `hermes plugins install`).

App tools, `wizard_apps` included, stay deferred behind Hermes's stock Tool Search: stock Hermes has no per-tool eager setting, so a planned fourth edit (`tools.tool_search.eager_tools`) was dropped (James, 11 Oct). The agent reaches `wizard_apps` through `tool_call`, which the weak-model gate passed ([AGENT_BRIDGE.md](AGENT_BRIDGE.md)).

It also adds `WIZARD_MCP_TOKEN` to the Hermes `.env`, plus `API_SERVER_KEY` only if Hermes had none.

`unlink` removes exactly those entries and the plugin, then restores `config.yaml` byte for byte. If the owner edited the file in between, their edits are kept and only Wizard's entries are removed. Values are never printed.

**A failed link leaves nothing behind.** `linked.json` is a write-ahead journal: it is saved (fsync'd, 0600) before the first edit, and each edit is added to it before it is made. If any step fails (a config edit, `hermes plugins install`, the `.env`), `link` rolls everything back to the backed-up bytes and exits non-zero with `"stage": "rolled_back"`. If the process is killed mid-way, the journal stays in state `linking`: `doctor` reports `no unfinished link` as FAIL, and the next `wizard unlink` or `wizard link` rolls it back first. Owner edits made in between are kept; only WizardOS's keys are removed. Fault-injection tests cover a failure and a kill before and after every step (`tools/tests/test_wizard_link.py`).

`doctor` checks:
- the link;
- the three edits;
- the token;
- the Hermes API;
- **the Hermes home is not shared** (default): the shell reads chats over the Hermes API and sees only the agent's images folder (`~/.hermes/cache/images`), not the rest of `~/.hermes`. Agent thread titles, turns running on other surfaces and the archived list need `state.db`, so they are off. An owner can opt in with `wam alongside --share-history`; then the line is **session history readable** (matching uid, read-only), and doctor says the shell can read every file in the Hermes home, credentials included;
- the shell, and that the shell reaches this Hermes;
- one live `wizard_apps` request through the gateway.

## Updating this box's Hermes (alongside mode)

```
wizard hermes status [--release V|FILE|URL] [--json]
wizard hermes update --stable [--dry-run] [--release V|FILE|URL] [--quiet-timeout S] [--health-timeout S] [--no-chat] [--json]
```

On an alongside box the owner installed Hermes, so WizardOS does not move it on its own. These two commands carry out step 4 of [HERMES_STABLE](../docs/HERMES_STABLE.md) (DECISIONS #74). `status` compares the running Hermes with the release that Wizard stable pins. `update --stable` moves Hermes to exactly that release, and only when the owner runs it.

**Which release.** The command reads the `hermes` block (`tag`, `commit`) of the release file that `releases/stable` names. Both files come from the same place `get.sh` uses: `$WIZARD_RELEASE_BASE`, which defaults to `wizard-app-manager/main/releases`. `--release` picks another version, a local file or a URL, which is how a candidate is tested before promotion. The command refuses to run in any of these cases:

- the tag is not a final release, i.e. it is an `rc`, `canary`, `alpha`, `beta`, `dev`, `stable`, `latest` or `main` tag;
- the commit is not a full 40-character hash;
- upstream's tag does not resolve to the pinned commit.

The last check guards against the trap PR #149 found: the published v0.21.6 image was built from `a28a5d03`, not from the tag's commit `818c13be`. The command installs by tag commit and records that commit in its receipt. It never runs `hermes update`, and it never follows `main` or `latest`.

**What it updates.** It updates a Hermes that the stock installer put in place: a git checkout with a venv, such as `~/.hermes/hermes-agent` (`$WIZARD_HERMES_REPO` overrides the path). It leaves the install alone, exits 10 with `update_by_hand`, and names the target tag when any of these is true:

- Hermes is not a git checkout;
- the checkout has no venv;
- `install-stamp.json` hands updates to another mechanism (for example `updateMechanism: external`).

It also refuses, again with exit 10, when the checkout has local changes or when the target is not proven to descend from the running commit. On a shallow installer clone it completes the tag's history before proving ancestry; commit dates are never ordering evidence. WizardOS never moves a Hermes backwards.

**Order of work.**

1. **Quiet moment.** The command waits until no gateway run is active, no background delegation is running, no cron job is running or due within two minutes, and no kanban task is running. It reads these from Hermes's own state files. It then writes Hermes's own drain marker (`.drain_request.json`, principal `wizard-hermes-update`) so no new work starts. The wait is bounded by `--quiet-timeout` (default 3600 s). On timeout it exits 11 with `not_quiet` and lists what kept Hermes busy. Nothing has changed at that point.
2. **Backup.** It copies the Hermes home into `$WIZARD_OS_HOME/hermes-update/<UTC stamp>/backup/` (directory mode 0700, files 0600):
   - every SQLite database at the top of the home and in `cron/`, using SQLite's online-backup API, with each copy integrity-checked;
   - `config.yaml`, `.env`, `auth.json`, `SOUL.md` and `cron/jobs.json`;
   - `skills/` and `memories/`;
   - the `hermes` commands on PATH and the gateway's systemd user units, so a rollback can put them back as they were.
3. **Install.** Before changing code or dependencies it stops the gateway and verifies both that `/health` is down and the recorded gateway PID is gone. An unsuccessful stop blocks the swap. It fetches the tag, checks that the tag still resolves to the pinned commit, and checks out that commit (on the same branch, or detached). It then installs that commit's dependencies with `uv pip install -e .[all]`, falling back to `pip`. It does not use `uv sync`, because that removes packages the owner added. Finally it runs Hermes's own `hermes_cli.post_update --scope home` maintenance and an import smoke test.
4. **Restart and check.** It removes the drain marker and runs `hermes gateway restart`, which is Hermes's own drain-aware restart. The stable checks then require all of the following:
   - the checkout is the exact commit and carries the tag;
   - `hermes --version` runs and prints no setup warning (a settings formatting error, "install out of sync", "source-update completion failed");
   - `config.yaml` parses with Hermes's own YAML. Hermes may keep running on its last good settings when the file is broken, so a gateway that answers is not proof that the owner's settings still apply;
   - `/health` answers with the version that `hermes --version` names. The command waits for that version, not just for any answer;
   - a chat round trip through the API server succeeds (`--no-chat` skips this);
   - `state.db` passes its integrity check and has at least as many sessions and messages as before, including five recent sessions sampled by id;
   - every cron job is still in `jobs.json`, and `hermes cron list` runs.
5. **Rollback.** If anything after the backup fails, including Ctrl-C, the command puts the old version back:
   - it stops the gateway and verifies its absence before touching code or restoring state; a failed stop yields `rollback_failed`, with the backup retained, rather than writing into a live database;
   - it checks out the previous commit and reinstalls its dependencies;
   - it restores every backed-up settings file and folder whose content changed;
   - it puts back the `hermes` commands on PATH (`~/.local/bin/hermes`, `hermes-agent`, `hermes-acp`, `$HERMES_HOME/bin/hermes*`) and the gateway's systemd user units exactly as they were. From v0.21.6 on, Hermes re-mints its launchers for its own dependency manager, and the old code cannot run through them;
   - it keeps each database when it is intact, so conversations, runs and tasks written since the backup survive. It restores a database from the backup only when that database fails its integrity check, or, for `state.db`, when it lost sessions or messages;
   - it starts the gateway, waits until `/health` reports the previous version (an old process can keep answering for a while after a restart), and runs the same checks against the previous commit.

   It then exits 12 with `update_rolled_back` and reports which checks failed. If the rollback itself cannot be verified, it exits 13 with `rollback_failed` and gives the backup path.

**Dry run.** `--dry-run` runs every read-only check (pin, install, cleanliness, upstream tag, order, what is busy right now) and prints the plan. It writes nothing: no receipt, no lock file and no backup. The acceptance test proves this by hashing the Hermes home before and after.

**Receipt.** Every real run writes `$WIZARD_OS_HOME/hermes-update/<UTC stamp>/receipt.json` (0600) as it goes. The receipt records:

- the plan, the previous and target commits, and how their order was proven;
- the busy reasons it waited on;
- the backup items with their hashes;
- each event with its time, the dependency route, the restart result and every check;
- the rollback results, when there was one;
- the final `status`: `updated`, `rolled_back`, `rollback_failed`, `not_quiet`, `refused` or `backup_failed`.

Only one update can run per box (`$WIZARD_OS_HOME/.hermes-update.lock`).

**Acceptance.** `tools/acceptance/hermes-update/run.sh` runs the test on Thales: a fresh Lima VM, stock Hermes from the official installer, `wizard link`, seeded sessions and a cron job. It then checks a dry run, a busy box, a forced failure with automatic rollback, and the real update. The record is [docs/acceptance/hermes-update-stable.md](../docs/acceptance/hermes-update-stable.md). `WIZARD_HERMES_UPDATE_FAULT` (`break-config`, `fail:after-backup`, `fail:after-swap`) exists only for that test.

## `--json` output

With `--json`, stdout carries **exactly one JSON document**, and nothing goes to stderr. Without it, stdout gets readable text and errors go to stderr as `wizard: <message>`.

Success always has `"ok": true` and exit code 0:

```jsonc
// wizard apps list --json
{"ok": true, "registry": "/home/me/.wizard-os/apps.json", "schema": 2,
 "apps": [{ /* the apps.json row */, "mcp": {"url": "...", "internal": "...", "transport": "streamable-http", "auth": null},
           "callable": true }]}

// wizard tools defleur-video --json
{"ok": true, "app": "defleur-video", "tools": [{"name": "...", "description": "...", "inputSchema": {...}}]}

// wizard call calc.add '{"a": 2, "b": 40}' --json
{"ok": true, "app": "calc", "tool": "add", "arguments": {"a": 2, "b": 40},
 "text": "{\"sum\": 42}",          // all text content blocks joined with \n
 "data": {"sum": 42},              // structuredContent, else the single text block parsed as JSON, else null
 "result": { /* the raw MCP CallToolResult */ }}
```

In `apps list`, rows are the registry's own fields (spec [APPS_JSON](APPS_JSON.md)). Fields starting with `_` are dropped, and MCP URLs lose any `user:pass@` and query string. `callable` is true when the app is `running`, has an MCP address and speaks a supported transport.

Failure always has `"ok": false` and a non-zero exit:

```json
{"ok": false, "error": {"code": "tool_not_found", "exit": 6, "message": "defleur-video has no tool 'x'; it has: …",
                        "app": "defleur-video", "tool": "x", "tools": ["…"]}}
```

| Exit | `error.code` | When |
|---|---|---|
| 2 | `usage`, `bad_arguments` | Bad command line; `ARGS` not a JSON object; missing or wrongly typed required argument |
| 3 | `registry_not_found`, `registry_invalid` | No `apps.json`, or it isn't a registry |
| 4 | `app_not_found` | No installed app with that id (`installed` lists the ids) |
| 5 | `app_not_running`, `app_has_no_mcp`, `unsupported_transport` | Installed, but not callable right now |
| 6 | `tool_not_found` | The app's `tools/list` has no such tool (`tools` lists them) |
| 7 | `unreachable`, `timeout`, `http_error`, `protocol_error` | Endpoint down, slow, non-2xx, or not speaking JSON-RPC |
| 8 | `auth_missing`, `auth_failed` | No token configured, or the app answered 401/403 |
| 9 | `tool_error` | The tool ran and reported failure (`isError`, or a JSON-RPC error on `tools/call`) |
| 10 | `update_refused`, `update_by_hand` | `wizard hermes update`: the pin or the install is not safe to move (nothing changed) |
| 11 | `not_quiet` | `wizard hermes update`: Hermes stayed busy for `--quiet-timeout` (nothing changed) |
| 12 | `update_rolled_back` | `wizard hermes update`: the update failed and the previous Hermes runs again, verified |
| 13 | `rollback_failed` | `wizard hermes update`: the update failed and the rollback did not verify; see the receipt and backup |

Codes and exit numbers are stable. Adding a code or a detail field is not a breaking change.

## Transport

- **Supported:** MCP streamable HTTP (`mcp.transport: streamable-http`, the [WIZARD_MD](WIZARD_MD.md) default). The CLI sends `initialize`, then `notifications/initialized`, carries `Mcp-Session-Id` and `MCP-Protocol-Version` when the server sets them, and accepts either a JSON or a `text/event-stream` reply. It follows `tools/list` pagination (`nextCursor`) and ends the session with `DELETE` at the end.
- **Not supported:** stdio and the legacy HTTP+SSE transport. Apps that use them show `callable: false` and fail with `unsupported_transport`.
- Requests go straight to the registry address; HTTP proxy variables are ignored, because app endpoints are box-local.

## Auth

Today's apps are reachable only from the box and need no token. When an app's MCP does want a bearer token, the CLI takes it from existing box configuration, never from the command line (`ps` would show it). It checks these in order:

1. `WIZARD_MCP_TOKEN_<APP_ID>`: the app id upper-cased, with non-alphanumerics as `_` (for example `WIZARD_MCP_TOKEN_DEFLEUR_VIDEO`).
2. An optional `mcp.auth` object on the app's registry row:
   - `{"type": "bearer", "secret": "MCP_TOKEN"}`: read key `MCP_TOKEN` from `$WIZARD_OS_HOME/secrets/<id>.json`, the 0600 file the App Manager already writes for an app's generated passwords;
   - `{"type": "bearer", "env": "VAR"}`: read the environment variable `VAR`.

Tokens never appear on stdout, stderr or in error messages; the tests assert this. `mcp.auth` is an optional reader-side field: the App Manager does not write it yet, and adding it to [APPS_JSON](APPS_JSON.md) is a change for the App Manager owner to accept.

## Tests

```sh
python3 -m unittest discover -s tools/tests -v
```

The tests are real end-to-end runs with no mocks. Each test starts [`tools/tests/mcp_fixture.py`](../tools/tests/mcp_fixture.py), a strict streamable-HTTP MCP server that requires sessions and, when set, a bearer token, and that can answer in SSE and paginate. It also writes a throwaway `WIZARD_OS_HOME`, then runs the CLI as a subprocess. Coverage: empty, missing and corrupt registry; missing, stopped, view-only and wrong-transport apps; unknown tool; bad JSON and schema mismatches; unreachable endpoint; tool errors; token from env and from the secrets file; argument round-trip through inline, stdin and `@file`; SSE and pagination; and install into a fresh `HOME`, including refusing to replace a foreign `wizard`.
