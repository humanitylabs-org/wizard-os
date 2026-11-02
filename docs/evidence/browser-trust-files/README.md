# Evidence: Files under the browser boundary (wizard-os #385 / #386)

Local real-Chromium runs (headless shell 1248), synthetic data only. Forum `/srv/work` was not reachable from this runner; nginx was a Node stand-in applying `packaging/browser-boundary-document.conf.template`; Tailscale Serve was a Node stand-in (Host kept, `X-Forwarded-*` + owner login added).

| Run | Script (wizard-ux) | Heads | Checks |
|---|---|---|---|
| `own-tab/` | `tools/qa-browser-files-own-tab.cjs` | WAM 6dbc2c09 · Service 88298f9 · UX d8b715ac (the wizard-files heads, which contain the own-tab commits) · files 5e2fc4d (real `filebrowser/filebrowser:v2.63.23`) | 21/21 |
| `own-tab-baseline/` | same, `QA_BASELINE=1` | WAM 750868f7 · Service d24c4e2 · UX dc594c1b · files 623c691 | 5 (records what is open today) |
| `wizard-files/` | `tools/qa-browser-wizard-files.cjs` | WAM 6dbc2c09 · Service 88298f9 · UX d8b715ac · wizard-files dbab496 | 35/35 |
| `wizard-files-baseline/` | same, `QA_BASELINE=1` | WAM 750868f7 · Service d24c4e2 · UX dc594c1b · wizard-files a635669 | 13 (records what is open today) |

`result.json` in each folder lists every check. `errors` there are Playwright's sandbox service-worker notice and the hostile probes' own blocked CORS reads (expected).
