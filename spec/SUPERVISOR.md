# Supervisor — approved prototype

James approved this prototype on 2026-10-16: “Sounds good. Lock it in as prototype and build it out.”

Supervisor is a Wizard OS system component. Its first job is self-maintenance: detect current impact, privately diagnose, decide within existing authority, execute, independently verify, then report a useful result or a genuine owner-only decision with a recommendation. Workers never publish raw maintenance alerts. A timeout or unnecessary worker approval request stays system-owned.

Prototype identity: `wizard-supervisor`, system slot `supervisor`, version `0.1.0-prototype`. Source was initially staged under `prototypes/supervisor/` on this named branch. The installed isolated prototype now lives in `humanitylabs-org/wizard-supervisor`, branch `prototype/supervisor-package`; extraction retained the component history. Prototype adoption does not change the default install or take over existing production recovery.

Acceptance:
1. Managed packaged service recovers a real disposable target and records functional evidence without owner approval when a grant exists.
2. Missing grant produces a specific action, immutable one-use approval and verified resume; worker requests cannot expand grants.
3. Restarts, duplicate events and late results preserve one owner and never falsely resolve.
4. Scoped owner feedback changes the next matching decision, preserves contrasting cases, and can be reversed.
5. A real System-facing view exposes Now, Recent decisions and Maintenance rules; scheduled-job recovery uses the same incident contract.

Smallest prototype delivery is isolated and opt-in. Existing alerts and recovery remain unchanged until an explicit production cutover. Use the existing Agent Service for private reasoning and conversation transport, ordinary App Manager packaging/lifecycle for installation, and a narrow execution adapter enforcing exact target/action grants. Never mount an unrestricted container-control socket in a reasoning component or modify core Hermes.

Implementation route: direct Hermes outcome owner; Claude Opus supplies the bounded view design; fresh read-only review of authority, state and approval boundaries is required before delivery. Builds, container execution, sustained tests and browser QA run on Thales external media. Shared commits are pushed immediately on the prototype branch. No full VM image rebuild.

Prototype baseline constitution: own the outcome; act inside explicit grants; preserve work/data/commitments; investigate technical uncertainty; recommend consequential choices; verify the affected function; learn with scoped evidence. Separate product defaults, owner rules and candidate lessons. One-time approval stays one-time.
