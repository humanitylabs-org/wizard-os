# Wizard app style audit

Source snapshot: 29 Oct 2026. Scope: **45 organization repositories plus one local Mizel UI source snapshot, 1,263 source files**, default branches pinned in [style-audit.json](style-audit.json). This is lexical debt, **not a visual compliance certificate**. Product data, account state, content directories, tests, dependencies and generated builds were not read. Zero fetch errors; no truncated source trees.

C = literal colour expressions, F = literal font-family declarations, P = px type declarations, B = non-kit `<button>` candidates. Counts exclude exact approved kit bytes and locked shell palette definitions; comments/tests are excluded. B is a review lead (dynamic templates can overcount), not a lint failure. Kit “stale” means not byte-identical to the canonical snapshot; no semantic version is advertised by these files. The OS guide/token additions change the current kit hash in this PR.

| Repository | C | F | P | B | Kit at audit |
|---|---:|---:|---:|---:|---|
| wizard-photos-app | 10 | 0 | 11 | 11 | No vendored kit found |
| wizard-ux | 1969 | 6 | 1039 | 456 | current fbec58ef / stale 398d9637 / stale 40c0ea40 |
| wizard-voice-service | 0 | 0 | 0 | 0 | No vendored kit found |
| wizard-manager | 0 | 0 | 16 | 6 | stale 4fb7e73b |
| wizard-agent-service | 4 | 0 | 1 | 1 | No vendored kit found |
| wizard-owner-ops | 0 | 0 | 0 | 0 | No vendored kit found |
| defleur-video | 5 | 0 | 2 | 1 | No vendored kit found |
| wizard-reference | 0 | 0 | 26 | 24 | stale 4fb7e73b |
| wizard-app-store | 176 | 5 | 69 | 11 | stale 4d055229 / stale fb3a00a1 / stale fdb2b9a3 |
| wizard-social-owner-live | 0 | 0 | 0 | 0 | No vendored kit found |
| conversation-evidence-index-source | 10 | 0 | 3 | 0 | No vendored kit found |
| wizard-quest-owner-live | 96 | 7 | 11 | 2 | No vendored kit found |
| wizard-stories-owner-live | 25 | 3 | 30 | 14 | No vendored kit found |
| tailnet-app-manager | 127 | 6 | 0 | 11 | No vendored kit found |
| wizard-search | 35 | 0 | 23 | 8 | No vendored kit found |
| wizard-app-manager | 123 | 1 | 66 | 142 | current fbec58ef / stale 49631d64 / stale fdb2b9a3 |
| reader | 35 | 16 | 6 | 28 | No vendored kit found |
| meditate | 48 | 2 | 6 | 8 | No vendored kit found |
| wizard-music-hub | 0 | 0 | 0 | 0 | No vendored kit found |
| wizard-airlock | 19 | 0 | 43 | 1 | stale 4fb7e73b |
| wizard-music | 26 | 2 | 25 | 30 | No vendored kit found |
| wisdom | 271 | 7 | 254 | 47 | No vendored kit found |
| wizard-recorder | 84 | 3 | 128 | 8 | No vendored kit found |
| wizard-messenger | 123 | 0 | 83 | 21 | No vendored kit found |
| notes-local | 6 | 3 | 36 | 14 | stale 4fb7e73b |
| wizard-connectors | 0 | 0 | 7 | 4 | stale 4fb7e73b |
| chatgpt-connection | 28 | 2 | 11 | 2 | No vendored kit found |
| claude-connection | 28 | 1 | 6 | 2 | No vendored kit found |
| wizard-troubleshooter | 40 | 0 | 26 | 16 | No vendored kit found |
| wizard-google | 91 | 0 | 49 | 0 | No vendored kit found |
| wizard-app-index | 69 | 0 | 33 | 12 | No vendored kit found |
| cinequeue | 154 | 1 | 54 | 22 | No vendored kit found |
| wizard-calendar | 28 | 0 | 43 | 18 | No vendored kit found |
| wizard-shopping | 236 | 31 | 141 | 42 | No vendored kit found |
| wizard-files | 118 | 2 | 114 | 9 | No vendored kit found |
| wizard-food-app | 70 | 0 | 28 | 11 | No vendored kit found |
| wizard-notes | 0 | 3 | 33 | 13 | stale 4fb7e73b |
| android-apps | 48 | 0 | 14 | 13 | No vendored kit found |
| video-editor | 11 | 0 | 56 | 32 | stale 4fb7e73b |
| wizard-tinfoil | 11 | 0 | 2 | 9 | stale dce078a3 |
| wizard-connection-router | 28 | 1 | 0 | 0 | No vendored kit found |
| profiles | 45 | 0 | 52 | 2 | stale dce078a3 |
| wizard-home-relay | 0 | 0 | 0 | 0 | No vendored kit found |
| wizard-local-model | 0 | 0 | 0 | 0 | No vendored kit found |
| wizard-archive | 55 | 3 | 28 | 10 | No vendored kit found |
| mizel-owner-local | 89 | 3 | 115 | 8 | No vendored kit found |

## Shell screens

| Surface | C | F | P |
|---|---:|---:|---:|
| Setup | 19 | 0 | 27 |
| Settings | 1 | 1 | 41 |
| Device | 0 | 0 | 0 |
| Chats | 280 | 0 | 189 |
| Home | 0 | 0 | 0 |
| Notifications | 0 | 0 | 0 |

## Highest debt / rollout

- **wizard-ux**: 1969 colours, 6 fonts, 1039 px type, 456 button candidates.
- **wisdom**: 271 colours, 7 fonts, 254 px type, 47 button candidates.
- **wizard-shopping**: 236 colours, 31 fonts, 141 px type, 42 button candidates.
- **wizard-app-manager**: 123 colours, 1 fonts, 66 px type, 142 button candidates.
- **wizard-files**: 118 colours, 2 fonts, 114 px type, 9 button candidates.

Wisdom, Shopping and Files are the three independent end-user apps selected for the first repair batch; WAM is handled by the template/builder gate and shell Setup/Settings by the shell PR. No live deployment is part of this work. The shell dynamically replaces hosted kit CSS, so a stale vendored copy can look fine today and still break standalone/offline builds.

## Coverage boundaries

- `wizard-app-store` is archived historical mirrored application source; reported separately from current authoritative products. `reader`, owner-custody forks and live-reference repositories are listed explicitly rather than silently dropped.
- Repositories with zero findings may be headless, wrappers or contain no front-end source; zero means no lexical matches, not certified appearance. Service repositories were included to catch embedded HTML (App Manager/Notifications are shell/service-owned surfaces, not standalone repos).
- Mizel has no standalone repository in the organization inventory. Six CSS/HTML/JS files from the owner-local UI checkout (recorded commit, no remote) are source-audited separately as `mizel-owner-local`; no backend, private recordings or account data was read. Remote origin provenance still needs confirmation.
- Thin native hosts (`wizard-desktop-shell`, `wizard-shell-mac`, `wizard-status`) and stock third-party `runtipi` are outside this web-kit lint. Corporate sites, unrelated services, substrate, and custody duplicates are not Wizard UI products. No private account or content payload was inspected.
- Reproducibility: per-repository immutable SHA, path/line findings and kit SHA256 values are in the JSON. The table describes **before**, not a claim that every app has already been repaired.

## Enforcement boundaries

Existing violations warn; newly added/changed source violations and changed stale kit copies fail. New hello apps use strict mode. Hash-locked exceptions need a reason and review. The CI rule does not replace functional/skin review, and legacy non-Git imports remain warning-only until a baseline can be established.
