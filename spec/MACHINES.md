# Machines — designated compute without inherited owner SSH

**Status: PROPOSAL, 22 October 2026. Not an approved platform requirement.**
Source-only preview: `wizard-agent-service`, branch `feature/machines-preview`.
No live deployment, account enrollment, new network permission, or replacement of current build routes is authorized by this document.

## 1. Owner job and boundaries

“Let this agent use that computer for these jobs, without giving it my login.”

Machines is a replaceable system component with a stable semantic API. It owns machine registration, scoped grants, transport credentials and receipts. Initially its implementation ships with the Agent Service; a separate daemon/package is not required. Settings stays shell-owned. [Devices](DEVICES.md) keeps monitoring and network discovery: a discovered/online device is **not** enrolled and grants no execution rights. Devices consumes explicitly granted status data; no silent import of the old SSH registry or the host's SSH configuration.

The owner may designate a dedicated build worker, or cautiously opt a personal computer into bounded status. Agents never receive owner logins, target private keys, arbitrary SSH destinations, a Docker socket, sudo, or root. Machines does not make a host-agent shell with existing owner SSH safe retroactively; migration removes each bypass only after its consumer has passed acceptance.

### Root, answered directly

- **Wizard host runtime:** unprivileged. No root installer, sudoers, host TCP relay, iptables, firewall edits or host-wide SSH config changes.
- **Target bootstrap:** the owner deliberately runs a reviewable one-time administrator script **on the target** to create a new limited account and install immutable policy/receiver. This privileged bootstrap is not agent authority.
- **Target runtime:** dedicated non-admin account, never owner/root. No sudo, admin/docker groups, owner keychain, Full Disk Access, SSH agent, owner caches, signing keys or owner credential folders.
- A limited OS account is **not a sandbox**. A working directory, named command, regex argument rule, `restrict` SSH key, or approval prompt does not confine repository-controlled code. Build presets can execute arbitrary code as that account. It can read world-readable files, observe processes, reach the LAN/tailnet, persist and exhaust resources. Local exploits and a compromised target administrator are outside this boundary.

**Recommendation awaiting James:** personal machines are default-deny and v1 status-only after explicit opt-in. Compute belongs on designated workers or disposable VMs. macOS TCC is defense in depth, not a confidentiality guarantee. Even status-only enrollment creates a credential/account and has residual risk; choosing no enrollment remains valid.

## 2. Machine and grant model

An owner-only registry lives beneath the component's configured private data root, separate from all agent homes and user Files. Keys and pinned-host material live in a different private directory from sockets. Mode 0700 directories / 0600 registry, atomic replacement and serialized owner writes. Backup must treat target keys as credentials; target OS accounts do not move with Wizard backups automatically.

Machine: stable id, owner label, platform, immutable privacy class (`worker` or `personal`), transport binding (host, port, dedicated username, private key reference, explicit known-hosts file), expected target policy agent id, enrolled date, disabled flag. Endpoint changes and class changes require re-enrollment/review, never an agent edit. Owner addresses are configuration, never source defaults or agent responses.

Grant: machine id + sealed-agent id, explicit capability set, allowed preset ids, expiry, opaque generation, revoked/disabled state. Every agent including the main/standard agent starts unticked. Unknown machines, missing grants, expired grants and unknown classes fail closed. No transitive app/agent grant. Private agents cannot gain another agent's workspace or results; sending private inputs to a machine is an explicit data egress grant, not implied by a job name.

**Target principals:** separate dedicated OS principal per sealed-agent/machine pair, or a stronger verified per-agent VM/container. Sharing a remote UID with separate directories is forbidden for repository execution. First preview supports one target principal and one agent per machine registration and rejects another agent on that registration; multiple-account enrollment and logical grouping into a single physical machine are deferred. No machine discovery or key autoscan.

## 3. Enrollment and removal

1. Owner picks name, platform and class in Settings (CLI in the preview). Wizard creates a dedicated key in its private component directory, never `~/.ssh`; only the public key enters a downloadable bootstrap bundle. Bundle contents, user, workspace, presets and residual access disclosure are shown before execution. Never curl-pipe an agent-generated script as root.
2. Owner enables OpenSSH themselves through native OS controls if needed. Bootstrap does **not** change `AllowUsers`, the owner's login, Remote Login state, system firewall, tailnet policy, home permissions or existing accounts. Tailscale, when used, is installed/enrolled by the owner and limits reachability with tailnet ACLs; it is transport, not grant authority.
3. Linux bootstrap creates a fresh dedicated `wizard-agent` (or per-agent suffixed name), no usable password, no supplementary groups, no sudo. Root-owned home and `.ssh` prevent editing the forced-command key; a child `work/` is owned by the limited user, mode 0700. Root-owned receiver and policy live outside that writable workspace. Refuse an existing username or partial enrollment rather than adopt an account. Print manual cleanup/recovery instructions on partial failure; never delete retained work automatically.
4. macOS equivalent: owner creates a fresh hidden non-admin account with a unique UID, disabled password, no SecureToken/FileVault unlock or keychain provisioning; root-owned home/authorized key and receiver/policy, writable private workspace on the owner's selected volume. Do not add admin, grant FDA, change owner folders, or copy Homebrew/Gradle/Xcode/signing credentials. Existing Remote Login policy may exclude the new account: show the native setting and stop until the owner allows it. Detailed macOS executable bootstrap remains a follow-on, not tested/claimed by the Linux preview.
5. Key entry uses OpenSSH `restrict,command="<immutable receiver> --policy <immutable policy> --agent <bound id>"`. No port/X11/agent forwarding, PTY, user rc or arbitrary shell. Receiver checks its policy-bound identity; it ignores/rejects attempted replacement commands. The private key never enters an agent container. A receiver identity mismatch fails even if the relay is misconfigured.
6. Owner confirms the target's host-key fingerprint out of band. Store the explicit public host key; never auto-trust `ssh-keyscan` alone, TOFU or a changed host key. Probe only through the restricted credential and read back the enrolled identity.
7. Revoke stops new admissions immediately, advances generation, terminates local SSH and discards late output; **remote process state after disconnect may be unknown**. UI and receipts say so. Owner disables/removes the key on the target to invalidate a copied credential; local revocation alone cannot revoke stolen keys. Disconnect does not delete accounts, files or audit evidence. Deleting the account/workspace is a separate owner-run, destructive action.

## 4. Capabilities: semantic jobs before shells

Capabilities are independent, not cumulative. The owner grants exact operations and presets, never a numeric tier that quietly includes another operation.

| Capability | Request and boundary | First preview |
| --- | --- | --- |
| `status` | Fixed receiver, platform + workspace-volume disk/free values only; no process/user/network enumeration or owner paths | yes; personal explicit opt-in only |
| `run` | Named root-owned preset, explicit argv/environment/cwd and timeout/output limits; request cannot supply argv, shell, cwd or environment | yes, worker only |
| `fetch-file` | Relative regular file beneath that principal's generated workspace; bounded bytes, no symlinks/hardlinks/special files/traversal; untrusted bytes | yes, worker only |
| `stage-files` | Agent-owned source → fresh job subtree, bounded files/bytes, no outside symlinks/device files/absolute paths, atomic admission; no rsync delete or owner-folder mount | deferred |
| `fetch-log/artifact` | Job-owned output handles + receipt; no arbitrary target pathname, return only to requesting agent | follows structured staging/jobs |
| `confined-shell` | Not ordinary SSH or a restricted shell. Only inside an independently verified disposable VM/container with explicit owner opt-in and transcript/resource policy | absent; not reserved as a promise |

Run presets may execute untrusted repository scripts and are safe only within the selected OS/VM trust boundary. Stage filenames/archives, build logs and outputs are hostile input, not instructions. File size and concurrency limits are not hard global CPU/RAM/disk isolation: preview process ceilings/timeouts are best-effort; a dedicated worker remains necessary. Presets must not embed credentials or fetch owner/private source without its separate data grant.

## 5. No-root transport and identity

Sealed agent → its existing identity-bound gateway → Machines semantic operation → dedicated per-agent Unix socket relay → fixed OpenSSH destination over tailnet/private network → forced-command receiver as limited target user.

The relay is **not a generic TCP/SSH byte tunnel**. No client-selected host, port, key, username, command or agent id. Each socket resides in its own 0700 directory, socket 0600, mounted only into that agent's trusted edge. Socket directory is separate from keys/registry. Bind the agent identity from the receiving listener, then verify Linux `SO_PEERCRED` against the expected edge UID. Same-UID credentials alone cannot distinguish containers; the private mount plus fixed listener binding is essential. No agent receives a sibling socket or service data root. Stock Hermes remains unchanged. Preview's caller CLI exercises this semantic boundary; automatic gateway/MCP installation is deferred and explicitly opt-in.

Use the existing restricted-runtime Linux-kernel placement rule: a macOS host socket shared into a Linux VM is not a functioning Unix transport. Run relay/Service and sockets in the daemon-local Linux environment. No TCP fallback.

OpenSSH runs with `-F /dev/null`, batch mode, strict pinned host checks, explicit identities/known-hosts, no ssh-agent environment, no forwarding, no control-master, no owner config, no PTY and bounded connect/session timeout. Disable password, keyboard-interactive, proxy command and local command. Target receiver executable and policy must be administrator-owned and not writable by the limited account.

Bounds: request frame, socket idle time, clients, active operations per agent, run duration, captured output, fetched bytes and audit growth. Fail closed on malformed frames, unknown fields, unavailable peer credentials, stale generation, audit admission failure or unsafe socket directory. Re-read grants through execution and before releasing output. Audit denial without exposing secrets. Grant mutation by another process uses atomic locked writes; simultaneous edits cannot lose revocation.

## 6. Receipts, revocation and owner visibility

Owner-visible activity contains request id, agent, machine, capability/preset, admitted/denied/running/completed/failed/revoked, UTC times, exit status, byte counts and reason codes. Log start before SSH and terminal result before releasing bytes. Audit is owner-only, append-oriented, metadata-only; never raw command output, personal file names, contents, keys or addresses in global logs. This is not cryptographic tamper-proof evidence against the host administrator. Long-term retention/rotation is owner policy; preview stops admitting when its fixed audit ceiling is reached rather than silently deleting evidence.

Sensitive per-agent receipts/logs stay inside that agent boundary; owner Settings may view activity, but the main agent does not gain private-agent content. Responses carry `untrusted: true` on logs/files and do not automatically enter chat/model context. Revoked/expired/generation-changed work returns no output; completion never re-grants access. Failed/offline operations never fall back to host SSH or another machine. Key rotation is an explicit owner enrollment change.

## 7. Agent tools and existing heavy jobs

Proposed deferred tools: `machines_list`, `machines_status(machine_id)`, `machines_run(machine_id,preset)`, `machines_fetch_file(machine_id,path)`, then `machines_stage_files` and receipt/artifact handles. Caller identity derives from authenticated gateway, not a tool argument. List returns only granted machine ids/labels, class and capabilities/presets, never endpoints or other agents. Denials are stable machine-readable codes. Owner registry/grant mutations are not agent tools.

**Preview:** owner CLI (`register`, `grant`, `revoke`); per-agent daemon (`serve`); agent-side CLI (`call`), bounded JSON and audit. It is usable without integrating a new shell page, HTTP owner API, MCP fleet or scheduler. No deployment autostart, existing grant change, source ingestion, remote signing or production build migration.

Heavy relay becomes **one consumer**: it resolves an owner-designated Machines worker grant and named build capability; Machines owns SSH/staging/fetch policy, heavy owns queue/lanes, originating-agent watermark, cancellation and durable receipt/continuation. A Machines receipt does not replace original human approval or make a child agent eligible for heavy admission. Preserve current light/heavy placement, caps and receipt semantics. Migrate one consumer at a time with parity tests; current raw SSH remains explicitly legacy, not silently claimed converted.

## 8. Settings → System → Machines (design, not shipped UI)

Shell-owned page, separate from Store/Apps. One list with owner name, class badge, OS, fingerprint/enrolled state, granted agents and current activity; link to Devices for monitoring rather than duplicate metrics. Empty state: “Choose a computer for your agents to use” with Add machine. No tailnet node starts enrolled.

Add: name/class → review/download target bootstrap → confirm host fingerprint → explicitly grant agent/capabilities/expiry → verify restricted status. Personal disclosure: “Status only. This does not make your laptop a safe build sandbox.” Status still needs an explicit grant; hide run/stage/fetch controls for personal. Worker grants show named presets, expiry and Revoke, with no ticked defaults. Detail shows metadata audit and explains remote-unknown on cancellation. Do not advertise a green ‘safe’ seal.

Appearance v1 per [APPEARANCE.md](APPEARANCE.md): transparent hosted canvas, `--wz-*` semantic tokens, live skin changes without reload, dark standalone fallback. Shared controls and Back: sheet → detail → list; root stays inside Wizard. Future UI acceptance needs real in-shell phone/desktop screenshots on two supported skins and owner mutations read back through supported APIs. Source-only CLI preview makes **no UI-complete claim**.

## 9. Threat model and acceptance

Trusted: owner/bootstrap, host service/relay, target administrator, immutable target receiver/policy, SSH, socket mount isolation and host OS kernels. Untrusted: agent/tool payloads, source repositories, logs/artifacts, network, co-resident unprivileged users. A compromised relay with all machine keys can exercise every registered grant; separate per-agent keys and target users reduce but do not remove host TCB. A compromised target can lie in outputs. Machines does not isolate an agent already granted an owner shell.

Required preview proof in normal suites with isolated HOME/HERMES_HOME/WIZARD_OS_HOME/TMPDIR:
- Actual Linux peer credentials, foreign UID refusal, identity-bound socket and target-policy mismatch; no client identity override.
- Worker status → named run produces file → fetch exact bytes through Unix relay and real SSH; no fake response as E2E proof.
- Unknown preset/fields, traversal, all symlink path components, hardlinks/FIFO, oversized file/frame/output, timeout, caps and denied grant.
- Pinned host-key mismatch aborts; explicit SSH flags and no inherited owner configuration/agent.
- Personal run/fetch refused before transport; missing, expired and revoked grants; mid-job generation invalidation kills local transport and suppresses outputs.
- Root-owned target policy/receiver, limited account no sudo/supplementary groups/password; enrollment tested **only inside a disposable Linux container**, never the host, a live worker or the owner account. Mac bootstrap/runtime proof remains open.
- Metadata audit and list show no secrets; normal `npm test` green; pushed immutable candidate, draft PR; no live activation.

Deferred release gates: multi-principal physical-machine grouping, macOS real enrollment, private-agent gateway/MCP integration, owner API/Settings UI, staging and job artifacts, disconnect/restart recovery, audit retention policy, and heavy consumer migration. These are not implied by a green CLI preview.

## 10. Review provenance and open decision

Two rounds of Claude Fable review, resolved alias `claude-fable-5-1`, with independent position written before reading round 1. Round 1 reinforced socket-mount identity (peer UID is not enough), target account limitations and key-local revocation limits. Round 2 withdrew shared target UIDs, personal per-run approval as a privacy boundary, global SSH/home-permission edits and automatic account deletion; agreed to status-only personal, semantic CLI-first preview and honest remote-unknown cancellation. Private raw transcripts are retained in the owner's source context, not this repository.

**One decision for James:** adopt the status-only personal-machine v1 boundary, with compute only on designated workers/disposable VMs? Recommended **yes**. No existing platform decision is superseded until he decides.
