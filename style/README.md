# Style

**Owner: James. Status: to extract.** Design tokens (colour, type, spacing, radius, motion) and core components are pulled from `wizard-ux` into this folder, so every app looks like it belongs.

The `wizard-app-builder` skill reads this folder, the system apps and the checker. It ends every app build by asking: "is there a component here other apps could share?" New interfaces default to dark mode.

## Locked

- **App icons: [ICONS.md](ICONS.md).** Every app ships a sigil (one silhouette, one bite, one colour). `sigils/make_icon.py` exports the icon files for a new app.
