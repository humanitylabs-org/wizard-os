# Evidence: shell intents for the ChatGPT/Claude pages (card 2, #385)

These are real-Chromium runs of `wizard-ux tools/qa-browser-ai-accounts.cjs` (wizard-ux draft PR). They used:
- the real Agent Service;
- real WAM state from each app's own `wizard.md`;
- the apps' real MCP fronts, with the listener gate on;
- the real store engines, over a stub Hermes dashboard and a fake `claude` CLI.

All accounts are synthetic, and provider hosts resolve to a dead local port. The shell document is served by a Node stand-in for nginx.

| | Run | Result |
|---|---|---|
| Candidate | migrated pages + intents (draft branches) | 59/59 checks |
| Baseline | `QA_BASELINE=1`: wizard-app-store `main`, chatgpt-connection `37c3bc89`, claude-connection `2e58656b` (release 0.3.102 pins) | ChatGPT "Offline", Claude Code "Loading…", `confirm()` false, `window.open` null |

`result.json` holds the check list and the run records. UUIDs and ports are replaced.

Screenshots:
- Nebula: `chatgpt-nebula-*`
- Grove: `claude-*grove*`
- Landscapes Light: `chatgpt-landscapes-light-accounts`
- Dark standalone tab: `chatgpt-standalone-dark`
- Baseline: `baseline-*`
