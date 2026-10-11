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

`doctor` checks:
- the link;
- the three edits;
- the token;
- the Hermes API;
- **session history readable**: the shell container reads the host `state.db` read-only, which needs a matching uid until the agent bridge stops reading it;
- the shell, and that the shell reaches this Hermes;
- one live `wizard_apps` request through the gateway.

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
