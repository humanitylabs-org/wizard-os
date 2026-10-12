# Style

**Owner: James. Status: to extract.** Design tokens (colour, type, spacing, radius, motion) and core components are pulled from `wizard-ux` into this folder, so every app looks like it belongs.

The `wizard-app-builder` skill reads this folder, the system apps and the checker. It ends every app build by asking: "is there a component here other apps could share?" New interfaces default to dark mode.

## Locked

- **Shell · skin · app: [../spec/APPEARANCE.md](../spec/APPEARANCE.md).** Hosted apps paint a transparent canvas on the shell's window material and use only skin tokens for surfaces; layouts and intentional typography stay the app's own.
- **App icons: [ICONS.md](ICONS.md).** Every app ships a sigil (one silhouette, one bite, one colour). `sigils/make_icon.py` exports the icon files for a new app.
