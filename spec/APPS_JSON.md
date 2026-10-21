# apps.json v1

The one list of installed Wizard apps.
- **Written by:** `wizard-app-manager`, after every install, uninstall or refresh.
- **Read by:** the Agent Service, the Wizard UX Apps screen, and `wizard apps list --json`.
- **Location:** `$WIZARD_OS_HOME/apps.json` (default `~/.wizard-os/apps.json`). Also served at `GET :8790/api/apps`.

```json
{
  "schema": 1,
  "updated_at": 1791543706,
  "store": "wizard",
  "apps": [
    {
      "id": "defleur-video",
      "name": "DeFleur Video",
      "type": "service",
      "version": "0.6.5-testing",
      "status": "running",
      "system": false,
      "summary": "Edit a talking-head video into a finished vertical short.",
      "provides": ["video-editing", "short-form-video"],
      "uses": ["transcriber", "browser", "files"],
      "needs": ["files"],
      "recommends": {"agent": "hermes", "model": "claude-opus-5-5"},
      "agent_binding": {"required": true, "purpose": "Where your recaps go"},
      "urn": "defleur-video:wizard",
      "mcp": {"url": "http://192.168.5.3:8787/mcp", "internal": "http://defleur-video:8787/mcp", "transport": "streamable-http"},
      "skill": "/home/me/.wizard-os/skills/defleur-video/SKILL.md",
      "view": null
    }
  ],
  "slots": {
    "video-editing": {"default": "defleur-video", "candidates": ["defleur-video"]}
  }
}
```

**Rules:**
- `view` is `null` for apps without a screen (MCP-only services such as DeFleur and hello-wizard live in the agent, not the launcher). For apps with a screen it is `{"url": "/apps/<id>/", "route": "/apps/<id>/", "upstream": "http://<host>:<port><path>"}`. `url` is what the Agent Service's `GET /wizard/v1/apps` hands the Wizard UX launcher; `upstream` is where the host proxies that route.
- Readers ignore unknown fields. Adding a field is not a version bump; removing or renaming one is.
- `status` is Runtipi's status (`running`, `stopped`, `installing`, …). Apps that are installed but missing from the compiled store still appear, with only their id, urn and status.
- `mcp.url` is reachable from the host; `mcp.internal` is reachable from containers on Runtipi's network. The Agent Service uses whichever matches where the agent runs.
- `agent_binding` is copied unchanged from `wizard.md` when the app declares one; absent otherwise. The Agent Service reads it to offer the app's "Sends its work to" picker ([AGENTS.md](AGENTS.md) section 7). The chosen agent is not stored here; it lives in the Agent Service's `app-bindings.json`.
- `skill` is a local path to the app's full skill. The Agent Service builds its own short pointer skills from `provides`.
- `grants` (top level, optional) mirrors the App Manager's app-to-app grants from `wizard-grants.json`, same objects, never keys ([PERMISSIONS.md](PERMISSIONS.md)). Display only; enforcement uses each app's own grants file.
- Writes are atomic (temp file + rename). Readers may watch the file.
