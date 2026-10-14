# Phone setup: use Wizard on your phone

**Status: build approved by James (14 Oct 2026); contract below is the MVP. Decisions #55–#57.**

A new owner uses Wizard on the computer it runs on. When they want it on their phone, they open **Setup** and tap
**Use Wizard on your phone**. Nothing about private networking happens before that tap.

## Setup app

A built-in system app beside Chats (`id: setup`). It opens by itself the first time Wizard opens and is reachable
from the launcher afterwards. Its home is a short checklist. MVP item: **Use Wizard on your phone**. Later items
(AI accounts, first app, voice, backups) join the same list. Onboarding lives here rather than in a chat, so a new
owner learns that Wizard is an operating system with apps, not a chat window.

## Use Wizard on your phone (three steps)

1. **Sign in to Tailscale on this Wizard.** Wizard starts Tailscale and opens Tailscale's own sign-in page. The owner
   uses their own (free) Tailscale account. If their tailnet still needs HTTPS certificates switched on, Wizard shows
   Tailscale's one-click link for that. The step completes when the box is online with its name, e.g.
   `wizard.tail1234.ts.net`.
2. **Get Tailscale on your phone.** QR code to `https://tailscale.com/download`; sign in with the same account.
3. **Open Wizard on your phone.** QR code to the box's own `https://<machine>.<tailnet>.ts.net/`. The step completes
   when Wizard sees the phone. The phone is signed in as the owner automatically; anyone else on that tailnet is
   refused.

## Rules

- Every address is discovered at run time from the box's own Tailscale status and stored in settings
  (`network.base_url`, `network.aliases`, `access.tailscale`). No address, tailnet name or owner name is written
  into source, images or defaults.
- Each Wizard joins its owner's own tailnet through Tailscale's normal sign-in. No shared tailnet, auth key or
  node state in images. No Funnel, Tailscale SSH, subnet routes or exit node.
- Tailscale stays installed but unpaired until the owner asks for phone access.
- On a Mac (Try Wizard), the local path through the Mac app keeps working exactly as before; the tailnet path is a
  separate entry that never assumes the owner.
- Back never exits: phone screen → checklist → previous screen.

## Pieces

| Piece | Repo | What it does |
|---|---|---|
| `wizard-private-access` helper | wizard-agent-service `ops/private-access/` | Root host helper on a local socket: status, start sign-in, serve HTTPS 443 to the Wizard's tailnet entry, reset. Nothing else. |
| Setup API | wizard-agent-service | `GET /wizard/v1/setup`, `POST /wizard/v1/setup/seen`, `GET /wizard/v1/setup/phone`, `POST /wizard/v1/setup/phone/start`, `POST /wizard/v1/setup/phone/reset` (owner-only). Writes the discovered address and owner login into settings; the Tailscale access check reads them at request time. |
| Setup app | wizard-ux | Checklist, three-step screen, QR codes generated on the device, live status. |
| Guest integration | try-wizard | Guest ships Tailscale unpaired, installs the helper, and gives Serve its own entry without the local owner shortcut. |
| Box installer | wizard-app-manager | Installs the helper next to Tailscale on Linux boxes. |

Done when a fresh Try Wizard install and a fresh Linux box each reach a real iPhone and Android phone with no terminal
step, a second Tailscale account is refused, and reset returns the box to computer-only use.
