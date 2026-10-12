# Native bridge v0 (Wizard UX ↔ native shells)

The native shells (Wizard for Mac, Android `ai.wizards.os`) add what a browser can't. This contract lets any Wizard UX build work with any shell, without the shell clicking CSS selectors.

## Page → native

```js
window.webkit?.messageHandlers?.wizardNative?.postMessage({id, method, params})   // macOS (exists today)
window.WizardNative?.postMessage(JSON.stringify({id, method, params}))            // Android
// reply: window.wizardNativeReply({id, result})
```

Methods today (Wizard for Mac 0.4.0):
- `app.info` returns the version, backend and capabilities
- `meeting.*` drives the recorder

Origin check: only the active Wizard origin.

## Native → page (new; replaces selector clicking)

The shell dispatches DOM events on `window`. The UX listens and acts:

| Event | When | UX does |
|---|---|---|
| `wizard:orb` `{action: "toggle"}` | Right ⌘ tap | No chat open → new thread + start voice. Recording → finish and send. Busy → ignore. Returns state via `wizard:orb-state`. |
| `wizard:open` `{path}` | Caps Lock launcher pick, search result | Navigate in-app to `path` (`/wizard/`, `/apps`, `/files`, `/meetings`, a thread). |
| `wizard:dictation` `{text}` | Right ⌥ result while Wizard is focused | Insert at the composer cursor. |
| `wizard:back` | Hardware/gesture back (Android) | One in-app back step; never exits at root. |

The UX answers `wizard:orb` with `window.dispatchEvent(new CustomEvent("wizard:orb-state", {detail: {state: "voice"|"sent"|"busy"|"none"}}))`.

**Transition:** Wizard for Mac keeps its current selector script as a fallback for one release. It sends `wizard:orb` first, and falls back to the script if no `wizard:orb-state` arrives within 300 ms.

## v0.1 additions (Wizard UX, 9 Oct 2026; all optional for shells, v0 still works)

Implemented in `wizard-ux` `web/core/bridge.js`. Both Wizard UX shells (phone and desktop) handle every event above.

- **Ready signal.** Once the UX can take events it sets `window.wizardUX = {shell: "phone"|"desktop", version: "wux-bridge-0.1", events: [...]}` and dispatches `wizard:ready` with the same detail. A shell that sees it can skip its selector fallback without waiting 300 ms. Measured answer time for `wizard:orb`: ~16 ms.
- **`wizard:orb` actions.** Besides `toggle`: `start` (start if idle), `send` (finish and send if recording), `cancel` (drop the take). `toggle` stays the default.
- **Where a voice take lands.** If a thread is open in the focused window, the take is sent as a reply to that thread; otherwise it starts a new thread. Audio goes through the durable outbox (transcribed, kept as a voice note, retried).
- **`wizard:open` targets.** Besides `{path}`: `{app: "<id or name>"}` (for example `"mizel"`, `"cinequeue"`) and `{thread: "<session id>"}`. Paths understood: `/wizard/`, `/wizard/?session=<id>`, `/apps` and `/search` (open the launcher/palette), `/inbox`, and any app URL in the registry (`/meetings/`, `/files/`, …). On the desktop an unknown same-origin path opens in a new window.
- **`wizard:dictation`** inserts at the composer cursor of the focused thread. On the desktop with the Chats list in front, it opens a new chat and inserts there.
- **Shell choice.** The desktop shell is chosen automatically when `window.webkit.messageHandlers.wizardNative` exists, so Wizard for Mac should load `/wizard-os-home/` and will land on `desktop.html`. The Android app (`WizardOS-Android/` user agent or `window.WizardOSNative`) always gets the phone shell.
- **Keys inside the page.** The desktop shell uses ⌥ (Option) as its window-manager modifier and ⌘K for search, so it doesn't fight Wizard for Mac's Caps Lock / Right ⌘ / Right ⌥ keys.

## Background audio v1 (staged Android pilot)

See [BACKGROUND_AUDIO.md](BACKGROUND_AUDIO.md) for the implemented Music-only admission, native canonical session/queue, authenticated media fetch and optional web adapter contract. Runtime discovery controls availability; existing shells and the wizard.md schema remain compatible.
