# The shell (`shell` slot)

**Status: proposed (James, 10 Oct 2026).** "Shell" is the working name; we can rename it later.

## What the shell is

The shell is the system front end of a Wizard: the frame you're always inside. On a phone it's the launcher and dock; on a desktop it's the workspaces and tiling.

It owns what every screen relies on:
- the launcher, dock and window frame
- the orb, voice and the side-button/hotkey hooks
- Back (Back never exits; see `wizard-ux`)
- notifications and the Ready/Working attention model
- Chats (the one built-in view)
- the [native bridge](NATIVE_BRIDGE.md) to Android and Mac
- hosting other apps' views

Everything else is a **view**: a normal Wizard app with a screen (`view:` in `wizard.md`), opened by the shell by URL. Examples: Files, Day/Week review, Mizel, DeFleur, Reader, Hermes Desktop in Browser.

## Packaging

- The shell is a **system app** that fills the `shell` slot: `system: true`, `provides: [shell]`.
- Default provider: `wizard-ux`, its own Runtipi app (static files plus a pass-through for `/wizard/...`). It `uses: [agent-service]`; the Agent Service is a separate app in its own slot, so any shell can sit on it and either can be swapped alone (#33).
- Every box has **exactly one active shell**. `wam bootstrap` installs the default, and the App Manager refuses to uninstall the last provider of `shell`. Installing another shell (for example `hermes-frontend-3`) and making it the default swaps it.
- The shell talks only to the Agent Service (`/wizard/...`), never to Runtipi or the App Manager directly; the Agent Service relays install/uninstall to the App Manager's box-only API.

## Customizing without forking

"Fully customize your system" must never mean "maintain your own fork of the OS front end". Customization comes in layers, cheapest first, and each layer survives shell updates:

| Layer | What the owner (or their agent) changes | Where it lives | Status |
|---|---|---|---|
| 1. Settings | name, agent name, timezone, voice vocabulary, router | `~/.wizard-os/settings.json` | live |
| 2. Layout | which apps sit on the dock and home screen, in what order, plus own links | `~/.wizard-os/launcher.json` | live |
| 3. Theme / skin | colours, type, spacing, radius, motion, wallpaper, orb | `~/.wizard-os/theme.json` over the shared [style tokens](../style/) | to build |
| 4. Overlay | small user CSS/JS and per-view overrides, loaded last by the shell | `~/.wizard-os/shell/overlay/` (user data volume) | to build |
| 5. Fork | the shell's own behaviour | a new repo that `provides: [shell]` | always possible, last resort |

Rules:
- Layers 1–4 are plain files on the user's data volume. The agent edits them with a skill; no rebuild, no container change.
- Shell updates never write to layers 1–4. If an update breaks an overlay, the shell starts with the overlay off and says which file failed.
- New screens are **views (new apps)**, not shell edits. The agent builds them from `hello-wizard`.
- What's in the shell vs a view gets decided by one test: does every other screen depend on it? If not, it's a view. The Day/Week/Month review screens are the first to move out.

## Done when (first version)

1. `wizard-ux` + `wizard-agent-service` install as one Runtipi app with `provides: [shell]` on a stock Runtipi box beside `hermes-agent`.
2. A theme file changes the look on phone and desktop without a rebuild, and survives a shell update.
3. An overlay file adds a dock action, survives an update, and a broken overlay starts safely with it off.
