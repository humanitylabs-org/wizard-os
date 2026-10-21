# Devices

Status: Approved by James (direction, 14 Oct 2026). Reference implementation: `wizard-ux` `tools/system-devices.mjs`, `tools/wizard-devices.mjs`, `web/core/resources.js`.

A Wizard can run on one box and work on others (a build Mac, a media drive, a home server). Devices gives the owner one place, on the phone, to see every machine the Wizard uses: online lights like the Tailscale admin list, plus CPU, memory and every disk for the machines the Wizard can read.

## Model

- **This device** is always present: the box the Wizard is installed on. It needs no setup. A fresh install shows exactly one device.
- **Connected devices** are machines the owner has given the Wizard access to. They live in the registry and are added by the agent, normally because the owner asked by voice ("watch Thales's disk too"). The shell never hard-codes a machine.
- **On your network** lists every other node on the owner's tailnet with its online light, when Tailscale is available. These are machines the Wizard could be given next; they show no readings.

## Registry

`~/.wizard-os/devices.json`, owned by the agent (mode 600, atomic writes, one `.bak`):

```json
{
  "version": 1,
  "this": {"name": null, "role": null, "tailnet": ["gateway-node"]},
  "devices": [
    {"id": "build-worker", "name": "Build worker", "role": "Builds and media", "connect": {"type": "ssh", "host": "build-worker.example"}, "tailnet": []}
  ],
  "hide": []
}
```

- `id`: lowercase letters, digits, dashes (≤32). `this` is reserved.
- `connect.type`: `ssh` in v1. `host` is a plain SSH host or alias from the Wizard user's SSH config (no leading dash, no spaces). Further transports (an agent on the device, Runtipi API) add new `type` values.
- `tailnet`: extra tailnet node names that are this machine, so they are not listed twice. `hide`: tailnet nodes to leave out of "On your network".
- `this.name` defaults to the tailnet name of the box, then its hostname.

The agent manages it with `wizard-devices` (`list`, `add <id> --ssh <host> [--name] [--role]`, `remove`, `this`, `hide`, `unhide`, `probe`). `add` refuses a machine it cannot read unless forced, so a device only appears once the Wizard really has access.

## Reading

`GET /api/system/devices` (owner identity required, read-only; anything else is 405):

```json
{"at": "…", "devices": [{"id": "this", "kind": "this|ssh", "name": "…", "role": "…", "status": "online|stale|offline|unreachable|connecting",
  "readAt": "…", "lastSeen": "…", "platform": "linux|macos", "cpus": 8, "cpu": 21, "memory": 44, "memoryTotalGB": 31, "memoryUsedGB": 14,
  "disks": [{"label": "System disk", "mount": "/", "usedGB": 245, "sizeGB": 386, "freeGB": 141, "pct": 63}]}],
 "network": {"available": true, "peers": [{"name": "…", "os": "…", "online": true, "lastSeen": null}]}}
```

- One fixed POSIX probe runs locally for this device and over `ssh -T <host> sh -s` for connected ones (Linux and macOS). Readings are cached ~25 s.
- Disks are real filesystems only. On macOS the APFS Data volume is reported as "Internal disk" (fill = (size − free) / size); external volumes keep their names. On Linux, fill = used / (used + free), matching `df`.
- No IP addresses, keys, usernames or command output leave the server; fields are an allowlisted numeric/label shape.
- `status`: `offline` when the tailnet says the node is down, `unreachable` when it is up but the probe failed, `stale` when a previous reading is shown.

## Shell

- Home keeps one compact Server meter for this device. Other devices appear on Home only as a one-line warning when one is offline or any disk is at 90 % or more.
- Opening the meter shows Resources → **Devices**: one card per device (this device first), each with its light, CPU, memory, main disk and every disk when there is more than one; then "On your network".
- Polling is visibility-bound: Home every 60 s, the open Devices tab every 15 s.
