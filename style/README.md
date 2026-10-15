# Style · Appearance v1

**Owner: James. Status: extracted from the approved daily Wizard UX.** Decisions #50–#53 govern layering and transport. Source revision and file hashes live in `tokens.json`; this extraction introduces no skin choices. Accepted skins: **Nebula (dark default), Grove, Tide, Ember, Signal**.

## Canonical files

- `tokens.json`: the fourteen Appearance v1 colour roles for every skin, plus the existing UI/type, spacing, radius and motion defaults. Window material comes from `--sk-win`; surfaces are 6%/10% ink tints, exactly as the live appearance host resolves them.
- `tokens.css`: generated CSS custom properties, including all five skin defaults. Run `python3 style/generate_tokens.py` after a source edit; `--check` fails if JSON and CSS drift.
- `appearance-client.js`: framework-neutral, exact parent + same-origin + version/schema validation, strictly advancing revisions, revision acknowledgements, `wizard:theme` events. Only fourteen validated colour values are applied; no agent or app-data authority.
- `boot.js`: marks a hosted document before first paint.
- `ui.css`: the existing Chats-derived builder kit plus card, chip, bar, sheet, list row, button and empty state. The kit references the tokens above, rather than maintaining another palette.
- `demo.html`: executable component gallery, with a nested sheet handled by `__wizardCloseOverlay()`. Serve this directory with any static HTTP server to inspect it.

## Use

```html
<script src="boot.js"></script>
<link rel="stylesheet" href="tokens.css">
<link rel="stylesheet" href="ui.css">
<script defer src="appearance-client.js"></script>
```

Hosted `html` and `body` are transparent; the shell supplies the same window glass as Chats. Standalone paints `--wz-base`. Bars use `--wz-chrome`, sheets `--wz-overlay`, cards/chips `--wz-surface`. The shell marks a frame transparent after acknowledgement; older hosts retain their own safety fill. A skin update changes variables without reloading the document, preserving input, scroll and playback.

Type roles are opt-in: controls take `--wz-font-ui`; an app may use `--wz-font-reading`, `--wz-font-display` or `--wz-font-mono`. Reading/display defaults are existing system/Georgia fallbacks. Fonts and intentional app typography are never overwritten. Layout/type/motion roles stay CSS defaults: the approved v1 message carries colours only. Signal's existing square kit shape is selected by `data-skin`; unknown future skins retain the defaults and accept host colours. Generic light-scheme transport remains supported; no retired skin is reintroduced.

## Builder and updates

The portable [wizard-app-builder pointer](../system-skills/wizard-app-builder/SKILL.md) names this folder, the system apps, the hello template and the checker. WAM's source bundle includes a **generated, hash-locked snapshot** of these runtime assets so an offline builder works. Its lock records this repository's exact revision and source/destination paths. Refresh with WAM's `tools/sync_wizard_style.py --source <wizard-os> --revision <sha>`, then review both PRs. The kit/client in WAM are distribution artifacts, not a second authored style source; `--check` catches local drift and comparison with this source catches divergence.

Every build ends: **"is there a component here other apps could share?"**

## Locked

- [ICONS.md](ICONS.md): every app ships a sigil. `sigils/make_icon.py` exports it.
- [APPEARANCE.md](../spec/APPEARANCE.md): origin/schema/revision and transparent-canvas contract. The proposed manifest field still awaits Miguel's confirmation; this extraction does not change the admission checker.

The daily shell continues to resolve its own skin table; adopting generated imports there is a separate change. This package is an extracted app dependency, not a daily deployment.
