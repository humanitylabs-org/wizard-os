# Wizard repair kit

How to get a broken Wizard box working again without James. Part 1 is for the owner. Part 2 is for whoever helps
them, human or agent. Part 3 is the technical detail behind each recipe.

Issue: [#93](https://github.com/humanitylabs-org/wizard-os/issues/93). The drill that tests this kit on a
deliberately broken box is `tools/acceptance/repair/` (it lands with its first run, in
[#97](https://github.com/humanitylabs-org/wizard-os/pull/97)).

Rules for everyone who uses this kit:

- **Never print, paste, copy or move a secret.** Not in chat, not in an issue, not in a screenshot. This page says
  where each sign-in lives so you can leave it alone, not so you can read it.
- **Never delete owner data.** That means chats, files, `media/`, app data folders and backups. A repair restarts
  or reinstalls things. It does not wipe them.
- **Do the smallest fix first.** Then check that it worked before you try the next one.

---

## Part 1 — For the owner

### First, open the Troubleshooter

Every box installed from stable 0.3.22 onwards has a **Troubleshooter**. It is a small page that runs on its own,
outside the Wizard shell, so it still works when Wizard does not.

- Open `https://<your-box>/troubleshoot/` on a device signed in to your Tailscale. It is the same address as your
  Wizard, with `/troubleshoot/` on the end.
- It shows each link in the chain (gateway, sign-in, shell, Agent Service, your agent) and which one is broken.
- Its guardian only **reports** problems. It does not change anything until you turn automatic repairs on.

If the Troubleshooter page does not open either, the box itself, its internet, or Tailscale is down. Check that the
server is switched on and that your phone or laptop is connected to Tailscale. Then go to "Repair with any working
subscription" below.

### What you see, and what to do

| What you see | What it usually means | Recipe |
|---|---|---|
| The Update button says "installing" for ever | An update was cut off (the box restarted, or the installer stopped) | [A](#a-update-stuck-on-installing) |
| Chats say your AI is signed out, or every reply fails | Your Claude, ChatGPT or Tinfoil sign-in ran out | [B](#b-ai-provider-signed-out) |
| The phone shows "Wizard needs attention", or the page won't load | The Wizard shell or the Agent Service stopped | [C](#c-shell-wont-load--wizard-needs-attention) |
| Installing an app fails with "the App Manager removed it" | The app could not be downloaded or started | [D](#d-an-app-install-fails-the-app-manager-removed-it) |
| One app's screen stays blank inside Wizard | That app stopped, or its link is missing | [E](#e-an-app-screen-wont-open-inside-wizard) |
| Messages send but your agent never answers | Your agent (Hermes) stopped or is stuck | [F](#f-hermes-not-answering) |

Most of these need someone to type a few commands on the server. If you can't, or don't want to, ask a friend, or
use any AI coding tool you already pay for. That is the next section.

### Repair with any working subscription

You need three things:

1. **A way into the server.** That is SSH to the box as the Wizard owner (on a fresh install the user is called
   `wizard`). If the box is on your Tailscale, the helper can join your tailnet, or you can share just this machine
   with them from the Tailscale admin page. Tailscale SSH (`sudo tailscale set --ssh` on the box) avoids passwords.
2. **An AI coding tool you already pay for.** Claude Code (any Claude subscription) or Codex (any ChatGPT
   subscription). It runs on the helper's own laptop, not on the box. The box never sees the helper's login.
3. **The repair prompt.** It is in [`tools/repair/REPAIR_PROMPT.md`](../tools/repair/REPAIR_PROMPT.md). It tells
   the tool what Wizard is, what it may and may not touch, and the recipes on this page.

On the helper's laptop, check that SSH works, then start the tool with the prompt:

```sh
ssh wizard@<box> true                          # must succeed without errors first
export WIZARD_BOX=wizard@<box>
claude "$(cat tools/repair/REPAIR_PROMPT.md)

The box is $WIZARD_BOX. The owner says: <what is wrong, in their words>"
# or, with a ChatGPT subscription:
codex "$(cat tools/repair/REPAIR_PROMPT.md)

The box is $WIZARD_BOX. The owner says: <what is wrong, in their words>"
```

The tool runs commands on the box over SSH, asks before anything risky, and reports back in plain sentences. When it
is done, remove the helper from your tailnet (or stop sharing the machine).

---

## Part 2 — Where every sign-in lives

Read this to know what **not** to touch. Every file below is private to the owner (mode `0600`) and holds secrets.
Do not `cat`, copy or move any of them. Claude and ChatGPT refresh tokens are single-use: a copy signs out the
original.

`~` is the Wizard owner's home folder (`/home/wizard` on a fresh install). Runtipi lives in `~/runtipi`.

### Fresh box (Wizard installed its own Hermes)

| Sign-in | Where it lives | How to reconnect it |
|---|---|---|
| Claude (subscription) | Docker volume `wizard-ai-accounts-claude`, shared by the **Claude** app (`wizard-claude`) and the **Hermes Agent** app, mounted at `/claude` in both | Open the Claude app in Wizard, press Test (it renews), or sign in again |
| ChatGPT / Codex | Hermes' own sign-in file, `~/runtipi/app-data/wizardapps/hermes-agent/data/auth.json`. The **ChatGPT** app (`wizard-chatgpt`) holds no token: it drives Hermes' dashboard sign-in (`http://hermes-agent:9119`) | Open the ChatGPT app in Wizard and sign in again |
| Other model keys for Hermes | `~/runtipi/app-data/wizardapps/hermes-agent/data/.env` | Set the key through the connection app that owns it; don't hand-edit |
| Tinfoil API key | The Tinfoil app's private volume (`/data/private` inside `wizard-tinfoil`); the key never leaves the app | Open Tinfoil, paste a new key, press Connect |
| Cloudflare | The Cloudflare app's private volume (`/data/private` inside `wizard-cloudflare`) | Open Cloudflare and sign in again |
| Connected accounts (Google etc.) | The Connected accounts app's data (`/data` inside `wizard-connectors`) | Open Connected accounts and reconnect the account |
| App Manager API token | `~/.wizard-os/api-token`, read by the user unit `wizard-app-manager-api.service` (`127.0.0.1:7790` only) | Created by the App Manager; `wam doctor` checks it exists and is `0600` |
| App Manager's Runtipi operator login | `~/.wizard-os/runtipi-operator.json` (`owner@wizard.local`) | Created once by the App Manager; never edit the database |
| Agent gateway token (`wizard` MCP) | `~/.wizard-os/mcp-token` | Created once by the App Manager; the shell and the agent share it |
| Generated app secrets | `~/.wizard-os/secrets/<app-id>.json` | Created at install; reinstalling the app keeps them |
| Runtipi's own database and queue passwords | `~/runtipi/.env` | Never change by hand |
| Troubleshooter settings and history | `~/.local/share/wizard-troubleshooter/host.env`, `~/.local/state/wizard-troubleshooter/` | `wam troubleshooter` rewrites the settings; keep the history |
| Tailscale (the box's network identity) | Managed by the system `tailscaled` service | `sudo tailscale up`, open the link with **your** Tailscale account, then `wam links` |
| GitHub (only boxes installed with `WIZARD_GITHUB=1`) | The owner's `gh` login | `gh auth login` as the owner |

### Alongside box (Wizard added to a Hermes that was already there)

Everything above still applies to the apps, with these differences:

| Sign-in | Where it lives | How to reconnect it |
|---|---|---|
| Hermes' model sign-ins | The existing Hermes home, usually `~/.hermes` (`auth.json`, `.env`), owned by whoever ran Hermes before | Sign in the way you always did with Hermes (`hermes` CLI), or through the ChatGPT app |
| Claude (subscription) | The owner's own Claude Code folder (`~/.claude`, or `CLAUDE_CONFIG_DIR`). `wam alongside` points the Claude app at this same folder, so both use one sign-in | Sign in with the Claude app (or `claude` on the box), then run `wam alongside` |
| Hermes dashboard password used by the ChatGPT app | `~/.wizard-os/secrets/host-dashboard.env`, served by `wizard-host-dashboard.service` | `wam alongside` recreates the link |
| Wizard's record of the host Hermes | `~/.wizard-os/alongside.json` (no secrets) | `wam alongside` |

---

## Part 3 — Recipes

Run every command as the Wizard owner, with the App Manager on your path:

```sh
sudo -iu wizard            # skip if you are already the owner
export PATH="$HOME/.local/bin:$PATH"
wam doctor                 # read-only health check; every line is PASS or FAIL
```

`wam doctor --fix` repairs what it safely can (the Wizard builder bundle and the Store data). It is always safe to
run. Each recipe ends with a check. If the check fails, go to "When nothing works" at the bottom.

### A. Update stuck on "installing"

**Why:** the installer writes `~/.wizard-os/install-status.json` and holds `~/.wizard-os/install.lock` while it
runs. If the box restarts or the installer is killed, the file can still say `running` with a lock nobody holds. The
Update button then waits for ever ([#90](https://github.com/humanitylabs-org/wizard-os/issues/90)).

**Fix:**

```sh
wam updates                                                # heals a dead run: state becomes "interrupted"
curl -fsSL https://aiwizards.com/os.sh | bash -s status    # should now say the install stopped
curl -fsSL https://aiwizards.com/os.sh | bash -s start     # run the update again, detached
```

`wam updates` checks the recorded runner: if the box rebooted since (`boot_id` changed) or the runner's process is
gone, and neither `install.start.lock` nor `install.lock` is held, it marks the run `interrupted` and removes the
stale `install.lock`. A runner that still holds the lock is never touched, so this is safe to run during a real
update. Do **not** delete `install.lock` or `install-status.json` by hand.

The start command updates to the current stable release. To stay on a chosen version, put it in front of `bash`:
`curl -fsSL https://aiwizards.com/os.sh | WIZARD_RELEASE=<version> bash -s start`.

**Check:** `bash -s status` shows `running` with a moving step, and later `done`. `cat ~/.wizard-os/release.json`
shows the new version.

### B. AI provider signed out

**Why:** a Claude, ChatGPT or Tinfoil sign-in expired or was revoked. Wizard can't renew it for you.

**Fix:** sign in again in the app that owns it (table in Part 2): the **Claude** app, the **ChatGPT** app, or
**Tinfoil**. Each has Connect (or Sign in) and Test. On an alongside box, run `wam alongside` after a Claude sign-in
so the app and the host Hermes share it again.

Never copy a sign-in file from another machine. Never paste a token into chat.

**Check:** the app's Test button passes, and a new chat message gets a reply.

### C. Shell won't load / "Wizard needs attention"

**Why:** the Wizard shell (`wizard-ux`) or the Agent Service (`wizard-agent-service`) container stopped or vanished.
The phone shows "Wizard needs attention" when the shell fails to start, or names the link that is down.

**Fix:**

```sh
wam recover
```

It starts the shell and the Agent Service when their containers are missing or not running. Apps the owner stopped
stay stopped. If the shell still fails, restart it outright:

```sh
wam app restart wizard-ux
wam app restart wizard-agent-service
```

**Check:** `wam recover` prints the apps it `started` and no `failed` entries. The shell answers on its health URL
(`wam apps --json`, the `wizard-ux` entry's `health`). Reload the page on the phone.

### D. An app install fails ("the App Manager removed it")

**Why:** when an app's image can't be downloaded or its container can't start, the App Manager deletes the half-made
install and says `install failed: … (the App Manager removed it; see docker logs runtipi)`. Nothing else on the box
changes.

**Fix:**

```sh
docker logs --since 30m runtipi 2>&1 | grep -i <app-id> | tail -20   # the real reason
wam doctor                                                           # is the App Store index reachable?
wam install <app-id>                                                 # try again once the cause is fixed
```

Common causes: the box has no internet or the registry is down (retry later), the disk is full (`df -h`), or the app
needs a setting (`wam install` then names it: `wam install <app-id> --set KEY=VALUE`).

**Check:** `wam install` ends with the app `running`, and the app is listed by `wam apps`.

### E. An app screen won't open inside Wizard

**Why:** the app's container stopped, or the list of apps and their links the shell reads is out of date.

**Fix** (for example, for Files: `wam app start files`):

```sh
wam app start <app-id>      # or: wam app restart <app-id>
wam apps                    # rewrites ~/.wizard-os/apps.json, which the shell reads
wam store-data              # rebuilds the Store data and its routes
wam links                   # only on a Tailscale box: re-publishes each app's private link
```

**Check:** `wam app start` reports `"status": "running"`. The app's `health` URL from `wam apps --json` answers.
Close and reopen the app in Wizard.

### F. Hermes not answering

**Why:** the agent itself stopped or got stuck. Messages arrive but nothing replies. The Troubleshooter shows
"Your agent (Hermes) isn't responding".

**Fix on a fresh box** (Hermes runs as the `hermes-agent` app):

```sh
wam app restart hermes-agent
```

**Fix on an alongside box** (Hermes runs on the host):

```sh
systemctl --user restart hermes-gateway.service
wizard doctor               # checks the link, the shell and the gateway with one live request
```

Restarting Hermes interrupts any reply in progress. Do it only when Hermes is really stuck.

**Check:** `docker ps` shows `hermes-agent_wizardapps-hermes-agent-engine-1` up (fresh), or
`systemctl --user is-active hermes-gateway.service` says `active` (alongside). A new message gets a reply.

### When nothing works

1. Rerun the installer. It repairs in place, keeps every app the owner had running, and never wipes data:
   `curl -fsSL https://aiwizards.com/os.sh | bash -s start`, then `bash -s status` until `done`.
2. Run `wam doctor` and save its output. Doctor prints names and paths only, never secret values.
3. Open an issue in `humanitylabs-org/wizard-os` with the doctor output, the Troubleshooter status and what you
   tried. Remove anything that looks like a token before you post.

---

## Technical notes

- **Owner and paths.** Fresh installs create the `wizard` user (docker group, passwordless sudo) that owns
  everything. State lives in `~/.wizard-os` (`WIZARD_OS_HOME` overrides), Runtipi in `~/runtipi` (`RUNTIPI_ROOT`
  or `runtipi_root` in `~/.wizard-os/app-manager.json`). The App Manager API binds `127.0.0.1:7790`.
- **Container names** follow Runtipi's compose naming: `<app>_wizardapps-<app>-1`, plus `-engine-1` for an app's
  engine (`hermes-agent_wizardapps-hermes-agent-engine-1`).
- **App lifecycle.** `wam app start|stop|restart <id>` waits for the app to reach the wanted state and reports
  `start_error`/`missing` instead of hanging. `wam app update <id>` updates one app (backup first by default). Any
  other `wam app …`, `wam start|stop|restart` etc. goes straight to the Runtipi CLI.
- **`wam recover [--running <urn>]`** only starts the shell, the Agent Service and the apps named with `--running`.
  The installer passes the apps that were running before a rerun; by hand, name the app you want back.
- **Install state** (`wam/updates.py: install_state`) heals `running`/`needs_owner` to `interrupted` only when the
  runner is provably gone (boot id changed, or its pid is dead) and it can take both `install.start.lock` and
  `install.lock` itself. `os.sh … status` also reports a dead runner as `stopped`.
- **Troubleshooter** is installed by `wam troubleshooter` as user units `wizard-troubleshooter.service`,
  `wizard-guardian.service` and `wizard-guardian.timer`, listening on `127.0.0.1:9691` under `/troubleshoot`. It
  needs a systemd user session and Tailscale; without Tailscale it waits (`wam troubleshooter` says why, and
  `~/.wizard-os/troubleshooter.json` records it). Its own built-in repair prompt is
  `wizard-troubleshooter/REPAIR_PROMPT.md`; [`tools/repair/REPAIR_PROMPT.md`](../tools/repair/REPAIR_PROMPT.md) is
  the off-box version for a helper's own Claude Code or Codex.
- **Earlier draft.** [#95](https://github.com/humanitylabs-org/wizard-os/pull/95) (`CREDENTIALS.md`, `docs/REPAIR.md`)
  is superseded by this page. Its review note still holds: `wam app list-backups` / `wam app restore` go straight to
  `runtipi-cli`, which cannot reach Runtipi's queue on stock installs, so this kit gives no restore recipe. Restore
  an app backup from the Runtipi dashboard (the app's Backups page) until `wam backup` lands.
- **Not built yet:** `wizard report`, the single redacted diagnostics document in
  [`spec/LAUNCH_AUDITS_8_9.md`](../spec/LAUNCH_AUDITS_8_9.md). Until it lands, `wam doctor` plus the Troubleshooter
  status are the shareable diagnostics.
- **Grounding.** Every command above exists in the App Manager pinned by release 0.3.32
  (`wizard-app-manager@66d06b4`): `wam doctor [--fix]`, `recover`, `updates`, `apps`, `store-data`, `links`,
  `troubleshooter`, `alongside`, `install`, `app start|stop|restart|update`, and the `wizard doctor` CLI. Recipes
  A, C, E and F (fresh) are exercised on a broken test box by the drill in `tools/acceptance/repair/`; B, D and
  every alongside-only step need a real account, a failing registry or an existing Hermes, and are checked against
  the source only.
