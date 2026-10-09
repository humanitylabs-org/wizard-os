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
- Readers ignore unknown fields. Adding a field is not a version bump; removing or renaming one is.
- `status` is Runtipi's status (`running`, `stopped`, `installing`, …). Apps that are installed but missing from the compiled store still appear, with only their id, urn and status.
- `mcp.url` is reachable from the host; `mcp.internal` is reachable from containers on Runtipi's network. The Agent Service uses whichever matches where the agent runs.
- `skill` is a local path to the app's full skill. The Agent Service builds its own short pointer skills from `provides`.
- Writes are atomic (temp file + rename). Readers may watch the file.
