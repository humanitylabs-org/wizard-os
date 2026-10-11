# Private access

Miguel's current default: **Tailscale**, preinstalled by the Wizard OS installer.
Cloudflare Tunnel + Access remains an alternative, not the default for this installer.

## A system parking spot, with a host provider

`private-access` is a system capability. Tailscale fills it by default; a different
provider can fill it later without replacing the agent, shell, or other apps.

Tailscale runs as a native host daemon because it manages networking. Do not
package it as an ordinary store container with host-network or runtime-socket
access: that would defeat the store's container-safety rules. Its lifecycle needs
a trusted host integration. The installer is the first implementation; store/UI
management of this parking spot is not implemented yet.

## Install and ownership

`curl -fsSL aiwizards.com/os.sh | bash` installs the native Tailscale daemon,
enables it for reboot, and prints the owner sign-in link for a new, unpaired box.
The owner signs into their own Tailscale account and installs Tailscale on the
phone/laptop that will access the Wizard. Never pre-enroll customer boxes into a
team-owned tailnet or bake a reusable auth key into a VM image.

Already-connected boxes retain their settings. Already-configured but stopped
nodes are not reset. If sign-in is deferred or the build is unattended, setup
continues with Tailscale installed but unpaired; the owner runs `sudo tailscale up`
when ready. Login waits are bounded; actual package/service failures stop setup.

The installer writes only provider/state metadata to
`~/.wizard-os/private-access.json`, not credentials. It enables no Funnel, Tailscale
SSH, subnet routes, exit node, or public app port. Native Tailscale installation
is **not** proof that app screens are reachable: the configured access path must
still reach the app's existing Runtipi endpoint; current box-local origins remain
loopback-only unless deliberately configured otherwise.

## App opening and routing

Reuse stock Runtipi for this part of the system. Its existing Open action supports
the current hostname plus the assigned app port, an app domain, or a local domain;
its existing Traefik integration handles domain routing. Wizard interfaces should
reuse those endpoints and actions, not invent a parallel app proxy or per-app
Tailscale Serve lifecycle.

New apps use Runtipi's existing installation and routing configuration. Provider
setup and owner enrollment are separate from app installation. A direct port URL
still requires that port to be privately reachable, while domain routing requires
the domain and access provider to be configured. Do not claim remote access works
merely because Tailscale was installed or an Open URL was calculated.

## Alternatives and packaging

Set `WIZARD_PRIVATE_ACCESS=cloudflare` or `none` for the installer process to skip
Tailscale setup. These options neither configure Cloudflare nor remove an
existing Tailscale installation. Switching a running box's access provider must
preserve a verified recovery path before retiring the old one.

VM and boot-image packaging can include Tailscale binaries, but must not include
an enrolled daemon state, account credential, shared auth key, or cloned node
identity. Each installed Wizard enrolls independently at first use.

Implementation: `wizard-app-manager/scripts/setup-private-access.sh` (called by
`install.sh`; the root-to-user handoff preserves `WIZARD_PRIVATE_ACCESS`). Existing
Cloudflare routes on Miguel's server are unchanged.
