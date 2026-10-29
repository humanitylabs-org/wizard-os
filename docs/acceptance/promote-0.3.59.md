# Promote 0.3.59: any number of Claude subscriptions (Stable)

## Decision and scope

Miguel (owner thread, 26 Oct 2026): "Ship it (not limited to just 2 though)". Release the multi-account Claude connection app, with any number of Claude subscriptions, together with the shell's Claude-pool routing (wizard-ux #537, #558), to Stable. This adds a capability, so it is classified honestly as a **feature** and fast-tracked under DECISIONS #93 with the owner's authorization.

0.3.59 is Stable 0.3.57 plus only the pieces this needs. The runtime pins that change versus `releases/0.3.57.json` are:

| Pin | 0.3.57 | 0.3.59 | Source |
|---|---|---|---|
| `default_apps.claude-subscription` | claude-connection `3b2d618` (0.1.2, engine `wizard-claude:0.1.2`) | `eb434ae` (0.2.5, engine `wizard-claude:0.2.5@sha256:4a8f91cf…2436f`) | claude-connection #2; engine from wizard-app-store #31 (`801afc58`, run 40319542857) |
| `components/images.wizard-ux`, `default_apps.shell` | `ffa4c636` (`sha256:a667cd87…`) | `325be039` (`sha256:cd80f6f8…db06d`) | wizard-ux #564: exact cherry-picks of #537 + #558 onto `release/stable-onboarding`; dispatch run 40320876700 (validate, publish, attest, finalize, anonymous-pull all green) |
| `components.wizard-app-manager` | `d926eec` (main) | `e3f76a68ea496f9540cf573ea5e934d66acefb65` (`maintenance/stable-0.3.57`) | WAM #250 = d926eec + exact cherry-picks of #249 and #252 |

The Agent Service, Troubleshooter, Hermes, every other default app and the App Manager image stay byte-for-byte 0.3.57. There are no migrations and no owner-data rewrites.

What each change does:

- **Claude app 0.2.5.**
  - The owner adds, reconnects and removes any number of Claude subscriptions. Each one has its own row and usage meters.
  - Added subscriptions sign in inside the agent with stock `hermes auth add anthropic --type oauth`, a pure OAuth flow that never writes `~/.claude`. The sign-in goes through the wizard-os plugin's account broker on the agent's dashboard.
  - The existing Claude Code sign-in keeps its volume or bind and stays the first row. Its original Connect/Test page moves to `/claude-code/`.
  - "Sign in again" appears on that row when it stops working. "Sign in" falls back to that page when the agent has no broker.
  - Account changes work without a page password, from same-origin requests only.
  - Hermes' copy of the Claude Code login folds into the original row, including on plugins that predate the mirror flag.
- **Shell (#537 + #558).** Once the Claude app reports a ready non-legacy subscription and Hermes' `anthropic` pool offers the same model, Opus and new chats default to that pool. Everything else keeps the legacy Claude Code route. Explicit picks are never rewritten. The image diff against 0.3.57 shows only `core/chat-models.js` changed in content (the rest is build stamps).
- **App Manager (#249 + #252).**
  - Alongside boxes get `WIZARD_ACCOUNT_CHANGES=1` in `host-dashboard.env`. The broker ships off by default. An owner's explicit value is kept, and the existing dashboard login is never rewritten.
  - The dashboard restarts whenever its environment file differs from the one it last started with.
  - `install.sh` reloads an installed or running host dashboard after `wizard link` refreshes the wizard-os plugin. If the dashboard does not come back, the install is reported as degraded.

## Published pins

- `releases/0.3.59.json` SHA256 `27db303e23ac810692c4106152ba230bb33c7f97e8eaef4f73bd12c558993c96`, `releases/0.3.60.json` SHA256 `ab3258adb9fe60252550af96a9f62445a4768c0be5a3addca3c43c1e9c93f5d9` (wizard-os #255, merge `109c46b3`).
- Claude engine `ghcr.io/humanitylabs-org/wizard-claude:0.2.5`, index `sha256:4a8f91cfa6abc829d17af533f18d23932a131ca48e2e821e870db0f474a2436f` (amd64 `sha256:4c884b13…`, arm64 `sha256:e89a38a7…`).
- Stable shell `wizard-ux:sha-325be039…`, index `sha256:cd80f6f823cfc2fd74532fbad5d002eebf2b584cdf080ad30a944b97566db06d` (amd64 + arm64). Latest shell `wizard-ux:sha-a0399680…`, index `sha256:a4b018a26f62ee42b9a5399a52ba6e5371a5ce3f714a16e576ff183b25611223` (amd64 + arm64).
- 0.3.60 (Latest) = 0.3.58 + the same Claude app, App Manager `4879531820cec4680ab19ed0a47ee8f094421c8a` (`maintenance/latest-0.3.58`, #251) and UX main `a0399680` (16 other main PRs ride along; listed in its `about`).

## Verification

- **Claude app** (wizard-app-store #31):
  - `tests/claude-pool-accounts.py`: 8/8. It covers 3, 5 and 12 listed subscriptions, a 4th and 5th add plus a remove, same-origin-only changes without a page password, the page password still enforced when set, the mirror fold on old and new plugins, the `/claude-code/` page, and an unreachable inventory. 4 of these fail on main's `pool_server.py`; the listing tests also pass there, because nothing capped the count.
  - Browser fixture `tests/claude-pool-ui.cjs` (Chromium, 390 px and 1440 px):
    - original sign-in plus 3 added subscriptions gives 4 rows and 4 meters;
    - two adds give 6 rows;
    - an expired original sign-in shows "Sign in again" (`claude-code/`);
    - with no broker, "Sign in" opens the original sign-in.
    It fails on main's `app.js`.
  - The existing pool, renewal, inference and `npm test` suites are green, and `test-container.sh` passes. CI built, tested and published `0.2.5` (amd64 + arm64), and the publish job now refuses to overwrite an existing tag.
- **Wizard UX:** `npm test` passes 769/769 on the Stable pin `325be039`. The two carried test files (9 cases) pass; 4 of those cases fail on `ffa4c636`. `npm test` passes 1083/1083 on the Latest pin `a0399680`.
- **App Manager:** `tests/test_host_dashboard.py` passes 10/10 on main, on d926eec+picks and on 44fded3+picks (the full suites: 772 passed on d926eec+picks, 1121 on 44fded3+picks). The 6 new or changed tests fail without the change. One of them runs the real `install.sh` block under bash with a stub `systemctl`. Codex completed with no unresolved findings on #249, #251 and #252, and all its findings on #250/#251 were fixed with tests.
- **Released images against fixtures** (released Claude engine `sha256:4a8f91cf…` plus the released shell's `core/chat-models.js` from each image digest, with a fake Hermes dashboard and fake model options where Hermes' default is legacy Claude Code and its `anthropic` pool is signed in):

  | Shell image | Hermes pool | Claude app accounts | `hasNativeClaude` | new chat / Opus |
  |---|---|---|---|---|
  | Stable `325be039` (`cd80f6f8…`) | mirror only | `legacy-claude-code` | false | `claude-subscription-directsdk-experimental` `claude-opus-5-5[1m]` |
  | Stable `325be039` | mirror + 3 ready | legacy + 3 | true | `anthropic` `claude-opus-5-5` |
  | Stable `325be039` | mirror + 5 ready | legacy + 5 | true | `anthropic` `claude-opus-5-5` |
  | Latest `a0399680` (`a4b018a2…`) | one / three / five | same as above | same | same |

- **Upgrade test, 0.3.57 → 0.3.59, component level.** This used disposable directories and a separate compose project; the owner's box was not touched.
  1. Start with 0.3.57's App Manager `d926eec`, whose `claude_login.ensure` binds the agent's Claude Code login folder, and 0.3.57's Claude recipe `3b2d618`, up with `docker compose` (`wizard-claude:0.1.2`). `/api/connection` reports `connected`.
  2. Upgrade to this release's App Manager (d926eec + #249/#252) with `claude_login.ensure` and `host_dashboard.ensure`, and to recipe `eb434ae`, up with `docker compose` (`wizard-claude:0.2.5@sha256:4a8f91cf…`).

  Results after the upgrade:
  - The engine's `/claude` is still the agent's login folder.
  - `/api/accounts` lists only `legacy-claude-code` as `connected` (the mirror folded). With 3 pool accounts it lists legacy plus 3 `ready`.
  - `/api/connection` reports `connected` (`wizard.ai-connection/2`).
  - **The original sign-in's credentials file is byte-identical (sha256).**
  - `WIZARD_ACCOUNT_CHANGES=1` was added, and one dashboard restart was requested.
  - A same-origin add without a page password reaches the broker, and a cross-site add gets 403.
  - Rolling back to the 0.3.57 recipe stays `connected` with the file unchanged.

## Limits (disclosed)

- **No full installer run.** No real `os.sh` upgrade ran on a clean box: demo, demo-1 and demo-2 are offline, and demo-3's key has expired. The upgrade is a component-level rig of the exact pinned pieces. Fresh mode is untouched by construction.
- **Fresh mode has no wizard-os plugin.** A fresh-mode agent (the Hermes Agent app) has no wizard-os plugin, so the Claude app shows the original sign-in and falls back to the 0.1.x sign-in page there; adding subscriptions needs an alongside agent.
- **Old plugins.** A box whose wizard-os plugin is owner-managed (not refreshed by `wizard link`), or older than agent-service #42, keeps read-only listing until its plugin is updated.
- **Fixtures only.** No real provider sign-in, MFA, quota or rotation was exercised. Through the fixture, the original sign-in page's own status reads `not_connected` because the CLI rejects the fake token; this is the unchanged 0.1.x code path.
- **Automatic updates.** App Managers on 0.3.26–0.3.31 set to Automatic skip a fast-tracked Stable (Update now still works).
