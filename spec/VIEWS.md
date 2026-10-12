# Changing how an app looks (views)

**Status: proposed (James, 12 Oct 2026; DECISIONS #52).** The owner says "move this here, hide that, make it look like X" about any installed app, and their Wizard does it without forking the app and without losing the change when the app updates.

## The ladder: cheapest first

The agent picks the lowest step that does the job. The `wizard-builder` skill holds this table.

| The owner asks | The agent makes | Where | Survives app updates |
|---|---|---|---|
| "Make Wizard darker", "put Mizel on the dock" | a shell setting, theme or layout change | `~/.wizard-os/` layers 1–4 ([SHELL.md](SHELL.md)) | yes |
| "Make me a report / dashboard of X" | a **page** | `media/Pages/<slug>/` ([PAGES.md](PAGES.md)) | n/a |
| "Move the add button to the top", "hide the sidebar", "bigger text in Mizel" | an **overlay** on the app's screen | `views/<app-id>/overlay/` | yes; switched off with a note if it stops matching |
| "Redesign Mizel's screen" | the owner's **own version** of the screen | `views/<app-id>/` (git) | yes; app updates are merged in |
| "Give me a completely different screen for Mizel's data" | an own version **started from scratch** | `views/<app-id>/` (git) | yes; it only depends on the API |
| "…and it needs its own database / a background job / to share with Miguel" | a **view app** | `dev/<id>/` → installed and published like any app | it's a normal app |

The rule from PAGES.md holds: start light; something becomes an app only when it needs its own process, database or MCP, or installs on other people's Wizards. A screen alone never makes an app.

## One folder per customized app

`~/.wizard-os/views/<app-id>/` exists only for apps the owner has customized. **No folder means the app's own screen opens unchanged.** Nothing is copied at install.

```
views/mizel/
  view.json        { "app": "mizel", "mode": "overlay" | "own", "base": "<app commit>" | "none",
                     "build": "npm ci && npm run build", "dist": "dist", "active": true }
  overlay/         overlay.css, overlay.js       (overlay mode)
  src/ …           the screen's source            (own mode; git branches `upstream` and `main`)
```

### Overlay

- The Wizard proxy adds two tags (`overlay.css`, `overlay.js`) to the app's HTML on the way to the browser. The app is untouched.
- Works for **every** app with a screen, including ones rendered on the server.
- If the shell detects a broken overlay (a script error, or selectors that match nothing after an app update), it turns the overlay off, opens the app normally and tells the owner which change stopped applying. The agent can then fix it.

### Own version

1. **Start.** The agent copies the screen's source from where `view.source` says it lives (the app's repo, or upstream at the pinned `ref`) at the installed commit. It commits that to a branch called `upstream`, then makes the owner's changes on `main`. "From scratch" skips the copy (`base: none`) and builds against the app's `api` spec.
2. **Build and switch.** The agent builds; the shell opens the owner's version only after the build passes. Until then the app's own screen keeps working.
3. **Serving.** The Agent Service serves the build at `/views/<app-id>/` and forwards `/views/<app-id>/api/…` to that app's declared `api` and nowhere else. That's the same door that enforces grants and logs calls.
4. **App updates.** When the App Manager updates the app, it puts the new screen source on `upstream`. The agent merges it into `main` and rebuilds. If the merge or build fails, the owner keeps the last working version and gets a note.
5. **Undo.** "Put Mizel back to normal" sets `active: false` (or deletes the folder). History stays in git.

### Which apps support which step

From [WIZARD_MD.md](WIZARD_MD.md#every-app-with-a-back-end-has-an-api-and-an-mcp-51): every screen can take an overlay; `view.source` plus a screen that talks only to the documented `api` allows an own version; `api` alone allows a from-scratch screen.

## Sharing a customized screen

"Share my Mizel screen with Jan": the agent turns `views/mizel/` into a view app in `dev/mizel-<name>/` (`type: view`, `backend: none`, `uses: [mizel]`, `replaces_view: mizel`), runs the checker and publishes it like any app. Installing it on Jan's Wizard swaps Mizel's screen in his launcher; uninstalling it brings the original back.

## Shell side

- The launcher reads `apps.json` and `views/*/view.json`. An app whose own version is active opens at `/views/<app-id>/`; every other app opens at `/apps/<id>/`, with the overlay added if one exists.
- Settings → Apps shows "Customized · Put back to normal" on any app with an active `views/` folder.

## Done when (first version)

1. On a test box, "move the add button in Hello Wizard to the top" produces an overlay that survives `wam update hello-wizard`.
2. "Redesign Hello Wizard as a dark card list" produces an own version; an app update that changes its screen merges in and rebuilds without losing the redesign.
3. "Share it with Miguel" publishes a view app that installs on a second box and swaps the screen there.
4. All three pass on a flash-tier model as well as the default model.
