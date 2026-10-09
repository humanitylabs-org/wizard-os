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
