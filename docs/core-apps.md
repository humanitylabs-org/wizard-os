# Core apps

Miguel's direction, 20 Nov 2026 (wizard-os#763): **WizardOS 1.0 is a private agent on Tinfoil plus 14 solid everyday
apps.** This page is the one bar every builder task and every person works to. When an issue touches a core app, judge
it against the core-ready bar below.

## The 14 core apps

Chat, Messenger, Mail, Calendar, Contacts, Notes, Files, Photos, Music, Maps, Translator, Voice, Finances (today's
Money) and Health.

**System pieces on every box** (not counted in the 14, but every core app leans on them): Connections, Backup, Updates
and Feedback, Browser plus Search.

## Three stages

Every app moves through the same three stages, in order:

1. **Works on its own.** Manual entry or file import. No account needed.
2. **A connection adds data, read-only.** An outside service fills the app through Connections. The app never writes
   back to it.
3. **The box is the source of truth.** The outside service becomes an optional sync.

An app is "at" the highest stage it fully meets, counting up from 1. An app that is only useful once an outside account
is connected is at stage 0, even if it already does stage 2 or 3 things.

## Core-ready bar

A core app is ready when it:

- installs and updates cleanly;
- works as its own phone app;
- is useful at stage 1 (no account);
- gives agents access only through Connections grants, read-only by default;
- backs up and restores.

## Where each core app stands

Filled in from each repo's `main` on 20 Nov 2026 (wizard.md, README, skill and compose files). It is a snapshot: update
the row when an app's stage or gaps change.

| App | Repo | Version | Stage | What it lacks for the bar |
|---|---|---|---|---|
| Chat | `wizard-ux` (Chats) + `wizard-agent-service` | shell | n/a: the agent itself | Not an App Store app: it ships with the shell and the Agent Service, so the app rows below do not apply as written. Not assessed here. |
| Messenger | `wizard-messenger` | 0.2.0-unified.16.88 | 1 | Encrypted Wizard-to-Wizard chat works with no account. The WhatsApp, Telegram and other network bridges send messages back out, so they are not read-only stage 2. Agent levels are Messenger's own (Draft-only recommended), not Connections grants. Only core app that sets `private_data`. |
| Mail | `wizard-mail` | 0.10.0 | 0 | Useless until a Google or Microsoft account is connected; sends through them (writes back). Agent level defaults to Draft only, not Read-only. No local mailbox or file import. |
| Calendar | `wizard-calendar` | 0.3.24 | 0 | Starts empty with Connect Google / Microsoft; no calendar of its own for events without an account, no `.ics` file import (only a private iCal link). Agent level defaults to Suggest only, not Read-only. |
| Contacts | `contacts` | 0.4.3 | 1 | Manual entry and vCard import/export work. No read-only Google/iCloud import yet (CardDAV phone sync is a two-way opt-in). Agent tools can add and update contacts with no read-only default. |
| Notes | `wizard-notes` | 0.1.0-alpha.13 | 1 (close to 3) | Plain Markdown vault on the box; an existing Obsidian folder can be used. Still alpha. Agent tools write and delete (to trash) with no read-only default. |
| Files | `wizard-files` | 0.1.6 | 1 | Reads the owner files root; uploads go through the system upload service. Agent tools are read-only (`files_list`, `files_search`). Version 0.1.x; no outside connection yet (stage 2). |
| Photos | `photos` | 0.4.0 | 1 (close to 3) | Immich on the box, Google Takeout import, phone backup through the Immich phone app. No read-only Google Photos connection (Takeout only). Agent can move photos to trash. A restore of Immich's database is not tested. |
| Music | `wizard-music` | 0.2.0-test.23 | 1 | Local files play with no account, but only the agent can add them (no upload in the app). Online songs need the YouTube Music connector. Still a test release. |
| Maps | `wizard-maps` | 0.1.2 | 1 | World overview with no account; regions build on the box; offline areas on the phone. Agent tools can save, delete places and add or remove regions with no read-only default. Version 0.1.x. |
| Translator | `wizard-translator` | 0.2.0 | 1 | Types and translates with the private model (Tinfoil) or on the phone offline. No file or document import. Agent tools save history; no read-only default. |
| Voice | `wizard-voice-service` | 0.2.2-rc1.app2 | n/a: a service | Dictation layer over Transcriber; no owner screen, so not its own phone app. Still a release candidate. Meeting recording lives in `wizard-recorder` (Recorder, 0.2.8), which is the nearer thing to an owner-facing Voice app. |
| Finances | `money` | 0.16.7 | 0 | Manual accounts (for example a cold Bitcoin wallet) and a one-time history import work, but day-to-day transactions need a bank connection (SimpleFIN, Monarch or Teller). No manual transaction entry or CSV import. Agent can update transactions with no read-only default. |
| Health | `wizard-health` | 0.16.4 | 0 | Shows nothing without a wearable connector (WHOOP, Oura, Fitbit, Polar, Withings, Apple Health). No manual entry or file import. Agent tools are read-only. |

Gaps every core app shares today:

- **Phone app.** No core app declares the `home_screen:` block ([WIZARD_MD.md](../spec/WIZARD_MD.md#home-screen-pins)),
  so a pinned app needs a connection to open. Maps and Translator keep offline data on the phone inside the app.
- **Agent access.** Agents reach apps through the Agent Service gateway and the owner's per-agent ticks
  ([PERMISSIONS.md](../spec/PERMISSIONS.md)), not through Connections grants. Only Messenger, Mail and Calendar have their
  own per-agent levels; none of them defaults to Read-only.
- **Backup and restore.** `wam backup` takes every app's data folder, but a per-app restore is not tested for any core
  app, and a restore reopens folder permissions unless the recipe sets `private_data: true`
  ([BOX_STATE.md](../spec/BOX_STATE.md), "App data folder modes"). Only Messenger sets it.

## System pieces

| Piece | Repo | Version |
|---|---|---|
| Connections | `wizard-connectors` (Connected accounts) | 0.7.1 |
| Backup | `wizard-backup` | 0.5.6 |
| Updates | `wizard-app-manager` (and the shell's update screen in `wizard-ux`) | platform |
| Feedback | `wizardos-feedback` | 0.3.2 |
| Browser | `browser` | 155.0.8059.44 |
| Search | `wizard-search` | 0.3.11 |

## Not now

- App sharing.
- A shell redesign.
- Apps beyond the 14.
