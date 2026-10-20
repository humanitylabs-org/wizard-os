# Repair an existing Wizard box

My Wizard is broken. Repair this existing installation; do not replace it with an empty new one.

1. Read AGENTS.md in this repair directory, the Wizard repair runbook and CREDENTIALS.md before changing anything. If those files are absent, fetch the trusted humanitylabs-org/wizard-os copies or ask me for their local paths. Do not invent a path or command.
2. First discover the actual Linux owner, install mode, WAM/Runtipi roots, current release, actual Hermes home/runtime, app ports and service/container names. Do not assume a development box's Caddy gateway or host unit layout is a fresh install's layout.
3. Diagnose locally: WAM help/doctor/apps/slots, generic wizard doctor, narrowly selected journals/container logs, disk/memory, private-network status, then the installed health URLs and provider connection status. Some diagnostic CLIs can refresh metadata; tell me before using a fix/update/restore mode.
4. Report the broken link and proposed smallest reversible change before executing a disruptive repair. Keep ordinary command approvals enabled. I will complete any provider or device authentication myself. My repair CLI login is not authorization to change the agent's provider.
5. Preserve all chats, files, backups, secrets, agent homes, app-data/named volumes, user-config and durable queue/upload state. Do not read private agents' content. Never delete or recreate a registry/database/volume merely to clear an error. Never print tokens, passwords, auth JSON, raw environment or verification codes. Do not send messages or publish anything.
6. Keep independent SSH/console access working. Do not stop the repair service you run inside. Never logout/reset Tailscale or restart its gateway on the only recovery path. Never run two writers on the same agent/queue. Confirm idle work or obtain my approval for interruption.
7. After the approved change, read back exact target state and repeat the failed checks. Ask me to open Wizard on my phone and send a synthetic chat through the intended provider. A health 200 is not proof chat, update or backup restore works.
8. Finish with cause, exact commands/changes, evidence, rollback point and remaining owner actions. If a backup key, host component, credential or tool is missing, stop that step and identify the precise gate. Do not claim success from simulated output.

My observed symptom: [describe what fails and when it last worked]
My approved maintenance scope: [read-only diagnosis first / describe approved repair]
