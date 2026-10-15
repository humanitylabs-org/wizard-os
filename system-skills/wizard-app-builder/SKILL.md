---
name: wizard-app-builder
description: Use when building a Wizard app with the shared style.
version: 1.0.0
---
# Build a Wizard app

Use the installed `wizard-builder` system skill from [wizard-app-manager/system-skills/wizard-builder](https://github.com/humanitylabs-org/wizard-app-manager/tree/main/system-skills/wizard-builder) for the executable build, stage and check workflow.

Read [style/](../../style/README.md), the canonical Appearance v1 tokens, client and plain CSS components. Learn from the [system apps](../../docs/ARCHITECTURE.md), copy [hello-wizard](https://github.com/humanitylabs-org/wizard-app-manager/tree/main/templates/hello-wizard), and run [the checker](../../tools/check_wizard_md.py) plus the builder's hosted appearance checks. The template carries a hash-locked snapshot of style/, never an independently maintained style system.

Keep intentional app typography and layout. In a hosted frame the canvas is transparent; in a plain tab use the standalone base. New interfaces default to Nebula dark. Skin controls belong in the shell. Publication and production installation follow the owner's current approval gate.

End every build by asking: "is there a component here other apps could share?"
