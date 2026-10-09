# The mass-market Mac path

The Mac is where most people try Wizard. Wizard for Mac (`try-wizard`) is a native app that runs the full Wizard OS Linux stack in a small VM and shows the Wizard UX in a native window. It also has system-wide keys:

- **Caps Lock:** the Wizard key, with launcher and search.
- **Right ⌘:** talk to your Wizard (orb).
- **Right ⌥:** dictate anywhere (Wizard STT).

## Where files live

**Default: a normal Mac folder, `~/Wizard`, shared into the VM** as the user-files root (`/files`, the same folder Runtipi apps see as `media/`). The App Manager and system state stay inside the VM disk.

| | Files inside the VM disk | Mac folder shared into the VM (default) |
|---|---|---|
| Uninstalling Wizard | Files are gone with the VM image | Files stay in `~/Wizard` |
| Finder, Spotlight, Time Machine, iCloud | No | Yes: they're ordinary Mac files |
| Moving to always-on | Bundle the VM disk | Sync `~/Wizard` + system state; the files are already portable |
| Speed for big media | Fastest | Close to native with virtio-fs (Apple Virtualization framework) |
| Risks | Hidden from the user; lost on uninstall | Permissions (uid mapping), many-small-file speed, and apps writing junk into a visible folder |

The fixes for the shared-folder risks:
- The App Manager keeps app databases and caches inside the VM. Only user files go in `~/Wizard`.
- File ownership maps to the VM's uid-1000 app user.
- `~/Wizard` gets a readable layout: `Inbox/`, `Videos/`, `Documents/`, `Meetings/`, `Exports/`.

The Mac app asks once on first run: "Keep your Wizard's files in ~/Wizard?", with a Choose folder button.

## Picking up where Claude or ChatGPT left off

**The idea:** most Mac users already work in ChatGPT, Claude or Claude Code. Wizard reads that context, so it starts already dialled in. They can hand it one task on the same project and compare.

**Feasibility, by source:**

| Source | Where the history is | Feasible? |
|---|---|---|
| **Claude Code** | `~/.claude/projects/<project-path>/<session>.jsonl`, one JSON line per message/tool call, plus `CLAUDE.md` files in projects | **Yes, live.** Plain local files. Note Claude Code deletes old sessions after `cleanupPeriodDays` (default 30), so import early. |
| **Codex CLI** | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`, `AGENTS.md` in projects | **Yes, live.** Same shape. |
| **Project folders** | The code, docs, `CLAUDE.md` / `AGENTS.md` | **Yes, live.** This is what the meetup guy did: point the agent at the folder. |
| **ChatGPT app / Claude desktop app** | On the provider's servers; the Mac apps cache little or nothing usable locally | **Export only.** Settings → Export data gives a zip with `conversations.json`. Wizard imports it. No live sync without the user re-exporting. |
| **ChatGPT/Claude Projects** | Server-side | **Export only**, partially. Project files are not always in the export. |

So:
- **Live pickup works for coding agents and project folders**, which is exactly the "work keeps happening in Claude Code, then I ask Wizard" case.
- **Chat-app history is a one-time import**, refreshed whenever the user re-exports.

**How it's built:**
- A **Context bridge** app (a normal Wizard app).
- The Mac app shares chosen folders into the VM **read-only**: `~/.claude`, `~/.codex`, and project folders the user picks. The bridge indexes them.
- MCP tools:
  - `search_past_work(query)` across sessions and imported chats
  - `load_project_context(path)`, which returns the project's `CLAUDE.md`/`AGENTS.md`, the latest session's goal, the last decisions and open TODOs
  - `import_export(zip)` for ChatGPT/Claude exports dropped in `~/Wizard/Inbox`
- The Agent Service adds one line to the agent's instructions: "If the user mentions a project, call `load_project_context` first."

**Difficulties:**
- **Permission prompt.** macOS asks the user before the app can read `~/.claude` (Full Disk Access is not needed for dotfiles in the home folder, but sandboxed builds need an explicit folder grant). Use a folder picker.
- **Formats change.** Claude Code and Codex JSONL are undocumented internal formats. Keep the parsers small, version-tolerant and tested against real files.
- **Privacy.** Old sessions contain secrets and API keys pasted into chats. The bridge indexes locally, never uploads, and redacts obvious keys before anything enters agent context.
- **Size.** Heavy users have gigabytes of sessions. Index summaries and the last N sessions per project; fetch full text on demand.
- **Writes.** Read-only by default. Wizard never edits Claude's or Codex's files.

**Pitch line:** "Keep using Claude. Give Wizard one task on the same project and see what happens."

## Desktop UX

- Wizard for Mac shows whatever UX the VM serves. Today its payload (`ux-dist.tgz`) is the older **wizard-mobile** React build, so the Right ⌘ orb script clicks `button.voice-fab` / `button.new-thread-fab` in that UI.
- `wizard-ux` (the current front end) is the target. The switch needs:
  - the payload built from `wizard-ux`
  - a desktop layout
  - the [native bridge](../spec/NATIVE_BRIDGE.md) events, so hotkeys stop depending on CSS class names
