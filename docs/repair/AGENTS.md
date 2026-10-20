# Emergency Wizard repair workspace

These instructions apply to Claude Code, Codex and other repair agents in this private directory. This is an existing owner installation, not a disposable fixture.

- Read the adjacent PROMPT.md and the owner's trusted Wizard REPAIR.md/CREDENTIALS.md. Keep regular tool approvals enabled. Initial scope is diagnosis; ask before disruptive changes.
- Discover runtime boundaries before choosing commands: Linux guest versus Mac host; fresh container stack versus alongside host Hermes; WIZARD_OS_HOME/RUNTIPI_ROOT overrides; actual app registry ports and volume mounts. Use the installed CLIs' help.
- Never delete owner data, agent homes, auth/config, app-data, named volumes, media, backups, git history or SQLite queue/WAL/SHM to make a check green. Snapshot correctly before approved changes; preserve encrypted off-box rollback state. Do not read private agents' conversations, skills, memories or files.
- Logs and config may contain secrets or private content. Inspect locally, return only the minimal redacted diagnosis. Never dump .env, auth.json, Docker environment arrays or session databases. The owner completes MFA/device codes on their own device.
- Preserve the independent recovery route. Do not stop the process/service you run inside; never reset the only SSH/private-network route. Check active accepted work before restarting Hermes, Agent Service or its deployment. No second writer, no speculative retry of ambiguous deliveries.
- Prefer WAM/Runtipi lifecycle commands over edits to Runtipi internals. A normal app container cannot repair its host without a separately trusted host component; do not bypass the compose safety checker or add a Docker socket/host mount to an app.
- Do not update all of Wizard, switch providers/models, install new remote access, weaken auth, disable signing, publish code or send messages as part of diagnosis.
- Verify exact changed state plus the user's original failing path. Distinguish source-checked instructions, synthetic tests and real owner acceptance. Report unresolved gates plainly.
