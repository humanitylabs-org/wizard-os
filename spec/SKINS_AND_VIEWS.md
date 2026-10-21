# Skins, palettes and swappable views

**Status: approved by James (21 Oct 2026, after a skins discussion with Miguel), #70–#73. Chats views run in-document (§3, option B). Slice 1 is live.** Extends [APPEARANCE.md](APPEARANCE.md) and [SHELL.md](SHELL.md). Folds in the unmerged views proposal (`proposal/app-standard-views-layout`, `spec/VIEWS.md`) and the planned overlay folder (SHELL.md layer 4).

## The problem

Three things are all called a "skin" today, and two different jobs are being handled by one mechanism:

- James's five "skins" (Nebula, Grove, Tide, Ember, Signal) are five colour sets for **one** look. Miguel's three (Dark, Light, Landscapes) are three colour sets for **another** look. The picker lists all eight side by side, so it reads as eight unrelated choices.
- Miguel organises and uses Chats differently from James. Chats is built into the shell (`wizard-ux` `web/app.js` plus `web/core/chats.js`), so the only way to change how it works is a PR into the shared shell. Every taste difference becomes a fight about which PR merges.
- Skin authors want to restyle Home and Settings too. Where does restyling stop and replacing begin?

## Four concepts

| Concept | What it is | Who makes it | How many are active |
|---|---|---|---|
| **Palette** | A named colour set: tokens, orb tint, light or dark, backdrop scene | the skin's author | one |
| **Skin** | A look-and-feel package: one or more palettes, a window frame, type, optional `skin.css` and `skin.js` (the safe hooks) | anyone, shipped as a folder | one |
| **My skin** | The owner's own layer on top of whichever skin is picked | the owner or their agent | always present, empty by default |
| **View** | A screen that does a job: Chats, Home, an app's screen. A swappable view is an installed app that fills a slot | anyone, shipped as an app | one per slot is the default; others can be opened too |

A skin changes how things look and feel. A view changes what a screen does and how it is organised. A skin never replaces a view.

## 1. Palettes inside skins

- Each skin entry in `web/core/skins.js` gets a `family` (the skin) and keeps its own id (the palette). Today:
  - **Wizard** (James): Nebula, Grove, Tide, Ember, Signal.
  - **Mizel** (Miguel): Dark, Light, Landscapes.
- Settings › Look shows two rows: **Skin** (one card per skin) and **Colours** (that skin's palettes). Picking a skin puts on the palette you last used in it, or its first one.
- The saved choice stays `wos.skin = <palette id>`, so nothing migrates and every existing install keeps its look. Retired palette ids map to Nebula, as before.
- Appearance v1 keeps `skin: <palette id>` and adds `family: <skin id>`. This is additive: existing apps ignore it.
- A palette may carry its own package folder (Landscapes uses `skins/landscapes/`, Dark and Light share `skins/obsidian/`). The skin's frame and `skin.js` apply to every palette in it unless a palette overrides them.

## 2. My skin becomes a folder

Miguel's My skin (`Skins/My skin.css` in Files, 20 Oct) is the CSS half of SHELL.md's planned overlay layer. It grows into the full layer, so the owner has one place for personal changes:

```
Skins/My skin/
  skin.css     what exists today (moved from Skins/My skin.css; the old file keeps working)
  skin.js      optional: the same safe hook API skin packages get (route, render, nav, part, gesture, toast, storage)
```

- Same guards as skin packages: `skin.js` loads as its own module, three errors a minute unloads it with a note naming the file, `?myskin=off` skips the layer for one load.
- **The owner switches each version of `skin.js` on.** Skin package scripts ship reviewed in the shell image; `Skins/My skin/skin.js` is a file the agent can write at any time, and it runs inside the shell page next to Settings' confirmations. So the shell runs it only after the owner taps **Turn on** in Settings › Look for that exact file (its SHA-256). Any edit turns it off until the owner turns the new version on. `skin.css` needs no approval: CSS can't act.
- This replaces `~/.wizard-os/shell/overlay/` (SHELL.md layer 4). Nothing else is built for it.

## 3. Swappable views (Chats first)

- **Chats leaves the shell** and becomes a view app that fills a new `chats` slot (App Manager parking spots, `wam/defaults.json`). The default provider is today's Chats, unchanged.
- Miguel forks it into his own repo (for example `mizel-chats`, `provides: [chats]`) and changes anything he likes. James never reviews his PRs; Miguel never reviews James's.
- **Several Chats can be installed at once.** The slot decides which one opens for "Chats", the dock and voice. Any other installed Chats opens like any other app, on any desk, so James can put Miguel's Chats next to his own on the same threads.
- Every Chats view reads and writes the same conversations through the Agent Service API. There is no per-view copy of threads, Ready state or read state.
- Adopting a feature from Miguel's Chats is a cherry-pick from his repo into the default.
- Order after Chats: Home (launcher and clock desk), then anything else that fails the SHELL.md test ("does every other screen depend on it?").
- **Settings stays in the shell.** It holds the privileged confirmations (installs, connections, agent permissions). Skins can restyle it; views cannot replace it.

### How a Chats view runs (decided: B for Chats and Home)

Chats is wired deeply into the orb, voice, desks, the outbox and Back. Two ways to host it:

- **A. Iframe app,** like every other view. Strongest isolation, uses Appearance v1 as is. It needs a Chats bridge for what the shell owns: voice target, open-thread-on-desk, Back steps, Ready badges and the outbox.
- **B. In-document module,** loaded like `skin.js` but owning a screen region, with the same banned-API lint. Feels exactly like today and is cheaper to extract. It is weaker isolation, so it is only allowed for apps the owner installed into the `chats` slot.

Decision: B for Chats and Home (first-party feel, owner-chosen code), A for everything else.

### Chats package and registry contract (`wizard.chats-view/1`)

A Chats provider is an ordinary installed Wizard app, with these additional fields
in `wizard.md` (the module path is relative to the pinned package source):

```yaml
id: mizel-chats
provides: [chats]
chats_view:
  contract: wizard.chats-view/1
  module: web/chats.js
```

Both fields are required together. `chats_view` has exactly `contract` and
`module`; it cannot declare an external URL, hash, default choice or Settings
replacement. `wizard-chats` is reserved for the shell's built-in Chats during
extraction. A package exports one default object with `contract`, matching `id`,
`name` and `mount(element, host)`; mount returns `update` and `unmount` hooks.
The host contract lives in `wizard-ux/docs/CHATS-VIEW.md`. Modules use the host's
Agent Service access to the same sessions, never their own conversation store.

WAM validates on both private-source and public-index install/update paths. The
module must be a regular, non-symlink, UTF-8 `.js` file inside that pinned source,
at most **128 KiB**. It is self-contained: no imports or secondary executable
files. Admission rejects the skin-package banned APIs (raw listeners, timers,
animation frames, network, storage, HTML injection, history, shell globals,
`eval`/`Function`, cookie access and dynamic/static imports). This deliberately
conservative token lint also scans comments and strings; it is a review guardrail,
**not a sandbox or proof against hostile JavaScript**. Installation is the owner's
trust decision for shell-origin code.

At install WAM records the module's SHA-256, byte count and fetched 40-hex source
commit in `.wizard-chats-view.json`. Registry refresh never re-seals modified
installed bytes. Only sealed modules, not repository trees, are copied into the
read-only Wizard share. `apps.json` preserves `provides` and projects:

```json
{
  "id": "mizel-chats",
  "provides": ["chats"],
  "chats_view": {
    "contract": "wizard.chats-view/1",
    "module": "/wizard/v1/chats-views/mizel-chats/<sha256>.js",
    "sha256": "<64 lowercase hex characters>",
    "bytes": 1024,
    "commit": "<40 lowercase hex characters>"
  }
}
```

`GET /wizard/v1/apps` adds `source: "apps.json"` and sets this provider's `url`
to `/wizard/v1/chats-views/mizel-chats/`, so the module is under its own same-origin
non-root app prefix, as required by shell admission. The ordinary app screen stays
in `view.url`; this does not turn an iframe screen or launcher link into shell code.
Only valid descriptors from installed apps are projected. The API includes:

```json
{
  "slots": { "chats": {
    "default": "wizard-chats",
    "candidates": ["wizard-chats", "mizel-chats"]
  } },
  "parking": [{ "slot": "chats", "active": "wizard-chats" }]
}
```

`chats` is additive/multi-provider, with the built-in fallback always available;
installing a second provider **does not** select it. Settings can read
`GET /wizard-os-home/store-install/_slots/chats` and, after the owner's explicit
confirmation, send `POST` there with JSON `{"default":"mizel-chats"}`. This uses
the existing privileged WAM Settings/Store listener: root-owned Serve peer,
verified tailnet owner, configured shell Origin, `X-Wizard-Store: 1` and JSON.
There is no slot-write method on the Agent Service, app bridge or Chats host API;
ordinary Settings PUTs cannot select a provider. Like the existing installation
confirmations, this relies on trusted shell-origin code: same-origin hostile code
is not isolated by headers or lint. Apps must not issue these owner mutations.

The module GET/HEAD route uses the existing Agent Service owner access gate,
serves only the installed provider's exact hash URL, rejects symlinks and traversal,
and checks size, SHA-256 and lint on every response. No redirects, external URLs,
imports, directory listing or source files are served. Responses are JavaScript,
`nosniff`, same-origin resource policy and `no-store`; changed bytes fail closed.

Uninstall removes the provider and shared module. Old module URLs are refused
even before physical cleanup once the registry no longer lists the app. A removed
or malformed default resolves to `wizard-chats`; valid owner choices survive
registry refresh. Several installed providers remain available side by side.


## 4. Skins can recommend views, never replace them

A skin's entry may list views it was designed with (`recommends: [mizel-chats]`). Picking the skin offers "This skin was made with Mizel Chats. Install it?" Saying yes installs the app and fills the slot. Each piece stays separately swappable: Mizel skin with James's Chats, or James's skin with Mizel Chats.

Why a skin does not carry its own views:
- James wants Miguel's Chats while keeping his own skin.
- Side-by-side needs two Chats at once, and only one skin is ever active.
- A skin change re-dresses the live page without a reload (drafts, open threads and scroll survive). Swapping views on every skin change would throw those away.

## 5. Customising an installed app's screen

Unchanged from the views proposal and already built in the App Manager (`wam views`, 12 Oct): an **overlay** (CSS/JS on the app's page) or an **own version** (a git copy of the screen that merges app updates) in `~/.wizard-os/views/<app-id>/`. Still missing: the shell opening `/views/<app-id>/` when an own version is active. Sharing a customised screen publishes it as a view app (`replaces_view: <app-id>`), which is the same mechanism as section 3.

## The ladder, cheapest first

1. Pick a palette.
2. Pick a skin.
3. My skin: CSS, then `skin.js`.
4. Customise an installed app's screen (overlay, then own version).
5. Swap a view: install another app for the slot (your own fork or someone else's).
6. Fork the shell (`provides: [shell]`). Always possible, last resort.

## Slices

| # | What the owner gets | Owner | Repo | Done when |
|---|---|---|---|---|
| 1 | Settings shows skins with their colours underneath | Archimedes | `wizard-ux` | The picker shows Wizard and Mizel as two skins. Switching skins restores the last palette. Saved choices load unchanged. Live on James's Wizard |
| 2 | My skin folder with optional `skin.js` | Archimedes | `wizard-ux`, `wizard-agent-service` | An agent adds a gesture through `Skins/My skin/skin.js`. A broken script switches off and names the file |
| 3 | Chats as a swappable view in a `chats` slot | Archimedes (extraction); Miguel forks it whenever he likes | `wizard-ux`, `wizard-app-manager` | Two Chats are installed. Each opens on its own desk on the same threads. The slot choice decides which one the dock opens |
| 4 | Skins recommend views | Archimedes | `wizard-ux` | Picking Mizel offers Mizel Chats. Declining leaves the slot unchanged |
| 5 | The shell opens owner-customised app screens | Archimedes | `wizard-ux`, `wizard-agent-service` | A `wam views` own version opens from the launcher. Revert brings the original back |
