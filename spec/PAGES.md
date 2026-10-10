# Pages

**Status: proposed (James, 10 Oct 2026; DECISIONS #35).**

Most things the agent makes for its owner are something to look at: a report, a write-up, a dashboard, a storyboard, a doc to edit together. None of these needs a container, a port or a server of its own. They are **pages**: folders of files in the user's Files, served by the one Wizard web server and versioned with git.

## Page or app

| | Page | App |
|---|---|---|
| What it is | a folder in `media/Pages/<slug>/` | a repo with `wizard.md`, a container, an MCP and a skill |
| Who serves it | the Agent Service, at `/pages/<slug>/` | its own container, proxied at `/apps/<id>/` |
| Made by | the agent writing files | building from the app template (`hello-wizard`) and installing |
| Examples | reports, audits, write-ups, dashboards, previews, storyboards, shared docs | DeFleur, Mizel, Transcriber, Files |

**The test:** start as a page. It becomes an app only when it needs one of these:
- a process of its own that keeps running
- its own database or writes beyond its own folder
- an MCP endpoint the agent calls
- installing on other people's Wizards

A screen alone never makes an app.

## Layout

```
media/Pages/
  .git/                     one repo for every page (history, diff, restore)
  <slug>/
    page.json               title, kind, source thread, project, status
    index.html              a built page   ─┐ at least one
    doc.md                  a shared doc   ─┘
    data.json               optional: data the page reads, rewritten by a job
    assets/                 images, CSS, JS
```

`page.json`:

```json
{
  "title": "Wizard OS · Pages",
  "kind": "report",
  "thread": "<session id>",
  "project": "Wizard OS",
  "status": "ready",
  "created": "2026-10-10T19:30:00Z",
  "updated": "2026-10-10T19:30:00Z",
  "data": {"file": "data.json", "refreshed_by": "cron:wizard-shipments"}
}
```

- `kind`: `report | doc | dashboard | preview | storyboard | other`.
- `status`: `draft | ready | archived`. Archived pages drop out of the list but stay on disk and in git.
- `data` is only there for pages whose data changes. A page with changing data is still a page: same folder, same serving. The only difference is that a scheduled job rewrites its `data.json`.
- Big media (video, DMG, APK) stays in Files and is linked from the page, so the git history stays small.

The agent sees this as `/files/Pages/` (the one user-files convention, [SYSTEM_APPS.md](../docs/SYSTEM_APPS.md#files)). On a Mac it's a real Mac folder and survives uninstalling Wizard.

## Who does what

The Agent Service owns pages, so every shell gets them for free (shell and Agent Service are separate apps once #33 in PR #5 lands):

- **Agent Service:** serves `/pages/<slug>/...` read-only from `media/Pages/`, with the sandbox header below. It also:
  - lists pages: `GET /wizard/v1/pages` (from each `page.json`)
  - saves an owner edit: `PUT /wizard/v1/pages/<slug>/<file>` with the version the editor started from. A stale version returns 409 with both texts, and nothing is lost.
  - shows history: `GET /wizard/v1/pages/<slug>/history`
  - restores: `POST /wizard/v1/pages/<slug>/restore {"commit": "…"}`
  - commits `media/Pages/` after every agent write and every owner save (author = agent or owner, message = file + thread).
- **Shell (Wizard UX, or any shell):**
  - passes `/pages/` through like `/wizard/`
  - shows the Pages list (recent, pinned, by project)
  - opens a page link from a chat on a review desk
  - renders `doc.md` in an editor that saves through the API
  - sends feedback from a page to its source thread
- **Agent:** writes the files with ordinary file tools and sends the link `/pages/<slug>/`. There's no install step and no service to start.

## Security

Pages are written by an agent, and an agent can be tricked by what it reads. A page must never act as the owner. So every `/pages/` response carries:

```
Content-Security-Policy: sandbox allow-scripts allow-forms allow-popups allow-downloads
```

Without `allow-same-origin`, the page runs in an opaque origin:
- it can't read the shell's storage
- the Agent Service refuses its `Origin: null` on `/wizard/...`

The page reaches Wizard only through a small `postMessage` bridge that the shell answers when it hosts the page:
- `feedback(text)`: goes to the source thread
- `save(file, text, version)`: limited to the page's own folder
- later, read-only `query(app, tool, args)` for live data

This goes in from the first version; adding it later means breaking every page.

## Migration

The 28 reports under James's `/reports/<slug>/` move into `media/Pages/<slug>/` with a `page.json` each. The old URLs redirect to `/pages/<slug>/`.

## Done when (first version)

1. The agent writes `media/Pages/demo/index.html` and `page.json`, and `/pages/demo/` opens on phone and desktop with no new container or service.
2. The page is sandboxed: from inside it, a request to `/wizard/v1/sessions` is refused.
3. A `doc.md` edited in the shell and by the agent at the same time ends in a 409, and nothing is lost. Both edits show in history, and restore brings back the earlier one.
4. Feedback from a page arrives in its source thread.
5. The Pages list shows title, kind, project and updated time from `page.json`.
