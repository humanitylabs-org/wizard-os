---
name: wizard-app-builder
description: Use when building an app for Wizard OS (a wizard.md package) with the shared style.
version: 1.0.0
---
# Build an app for Wizard OS

Use the installed `wizard-builder` system skill from [wizard-app-manager/system-skills/wizard-builder](https://github.com/humanitylabs-org/wizard-app-manager/tree/main/system-skills/wizard-builder) for the executable build, stage and check workflow.

Read [style/](../../style/README.md), the canonical Appearance v1 tokens, client and plain CSS components. Learn from the [system apps](../../docs/ARCHITECTURE.md), copy [hello-wizard](https://github.com/humanitylabs-org/wizard-app-manager/tree/main/templates/hello-wizard), and run [the checker](../../tools/check_wizard_md.py) plus the builder's hosted appearance checks. The template carries a hash-locked snapshot of style/, never an independently maintained style system.

Follow the [app design rules](../../style/APP-DESIGN-RULES.md) and its app checklist: the window is the page (no `max-width` on the frame), layout by window width via container queries, one pop-up (`.wz-sheet` + `style/sheet.js`), the connector pattern for account apps, and no hex colours in app CSS; `wam check` warns on breaks. Keep intentional app typography and layout. In a hosted frame the canvas is transparent; in a plain tab use the standalone base. New interfaces default to Nebula dark. Skin controls belong in the shell. Publication and production installation follow the owner's current approval gate.

End every build by asking: "is there a component here other apps could share?"
