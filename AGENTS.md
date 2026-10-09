# For agents working on Wizard OS

1. Read `docs/ARCHITECTURE.md` and `docs/DECISIONS.md` before proposing structure. A locked decision wins over your preference; propose changes as a PR that names what it reverses.
2. Find your component in the repo table in `README.md`. Stay inside its contracts in `spec/`. If you need a contract to change, change the spec first and say who must agree.
3. Building an app? Copy `wizard-app-manager/templates/hello-wizard`, keep `wizard.md` passing `tools/check_wizard_md.py`, ship an MCP endpoint and a skill, and tag the repo `wizard-os-app`.
4. Runtipi stays stock and the agent harness (Hermes) stays unmodified. Wizard behaviour goes in the Agent Service, the App Manager, the UX, or an app.
5. Picking up work? Take an item from `docs/WORK_OUTSTANDING.md`, put your name on it in a PR, and close it with evidence (test output, a link, a screenshot).
6. Never commit secrets, personal data, or real conversation content. Private repos are still shared with every org member.
