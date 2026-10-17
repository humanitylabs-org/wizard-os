# Release 0.2.2 candidate: alongside runner (prepared, not executed)

`tools/qa/e2e_022_alongside.py` is a bounded experiment runner for the acceptance owner's **Thales heavy queue**. It does not certify a release, run chat, install DeFleur, publish artifacts, or modify a live installation. Local validation is syntax/static inspection only; actual guest acceptance remains pending.

## Source identities and stock installation

- Base OS runner branch: `origin/integration/e2e-022-acceptance` at `bbadfe0b2480a3bfedf24ee642723bb467ae648f`.
- WAM candidate: `2fb67c714c0c85be49d12e37e8a556d25cd23bba`, with its unchanged `scripts/qa-release-candidate.py`.
- Stock Hermes: official `NousResearch/hermes-agent` commit `bebe448a2bdb57043ca8ebd820807bf7eed6320d`, resolved from official `main`. No core changes, substituted executable, or synthetic API service.
- Wizard plugin: release-pinned Agent Service source `eac2ea0fe8f81b2b1f8a1eb0217b7d3cfcd77764`, installed by the actual stock Hermes plugin command through `wizard link`.

The [official installation documentation](https://hermes-agent.nousresearch.com/docs/getting-started/installation) and [pinned installer source](https://github.com/NousResearch/hermes-agent/blob/bebe448a2bdb57043ca8ebd820807bf7eed6320d/scripts/install.sh) establish the noninteractive route:

```sh
bash stock-hermes-install.sh \
  --branch main --commit bebe448a2bdb57043ca8ebd820807bf7eed6320d \
  --non-interactive --skip-browser --skip-computer-use
```

The pinned script is downloaded by immutable URL inside the guest, hashed and retained privately. Its ordinary installation builds the real launcher/products and dependencies; the optional browser/computer-use payloads alone are omitted. The runner records the official source remote, exact HEAD, tracked cleanliness, launcher hash and actual `--print-runtime-command` before/after. Dependency retrieval and the Ubuntu template still rely on their upstream availability; this is not a hermetic offline build.

## Parent queue handoff

Stage this **pushed, clean Git revision** (including `.git`) at:

```text
/Volumes/ThalesMedia/wizard-os/e2e-022/alongside-runner
```

Submit the following argv/cwd through the parent's native heavy queue, not a foreground SSH call. The runner neither submits jobs nor acquires a second worker lock.

```text
cwd: /Volumes/ThalesMedia/wizard-os/e2e-022/alongside-runner
argv: ["python3", "tools/qa/e2e_022_alongside.py", "--root", "/Volumes/ThalesMedia/wizard-os/e2e-022"]
```

Equivalent command:

```sh
python3 tools/qa/e2e_022_alongside.py --root /Volumes/ThalesMedia/wizard-os/e2e-022
```

The default creates **only** `alongside-022` (Ubuntu 24.04, aarch64/VZ/Rosetta, 4 CPUs, 6 GiB RAM, 60 GiB disk). It refuses any existing guest with that name. It uses dedicated `root/lima` and `root/lima-cache`, checks external-volume placement/free space and internal-disk safety headroom, disables host mounts, and ignores all automatic loopback/wildcard forwarding (explicit `127.0.0.1` rule first). Existing guests, global Lima configuration and host services are untouched. The host must already have Lima and its prerequisites.

Optional **separate** x86_64 guest for later parent-directed work:

```sh
python3 tools/qa/e2e_022_alongside.py --root /Volumes/ThalesMedia/wizard-os/e2e-022 --arch x86_64
```

This selects `alongside-022-amd64`, QEMU, 8 GiB, and **no Rosetta flag**. QEMU must already exist; the runner will not install host tools. This route is unexecuted and emulation can hit the bounded install timeouts. It is not proof that any DeFleur architecture/image/UX requirement passes. ARM preservation proof is independent of DeFleur.

## Actual sequence and proof boundary

1. Refuse prior guest installation state. Run the official pinned Hermes installer in the new disposable guest. Preserve its actual installer-generated owner files in `installer-originals/`.
2. Modify only guest owner configuration using the real Hermes runtime and its round-trip YAML library; retain stock config, append a SOUL sentinel, add a sentinel skill/auth document, and create a real random local API key. No provider/model credential is supplied. The API key never appears in source or console output.
3. Install/start the normal stock gateway service, wait for its real API health, then save `before/`: actual file bytes and type/mode/uid/gid/symlink-target metadata. This is the **pre-Wizard owner baseline**, distinct from installer originals.
4. Execute the unchanged candidate helper with `WIZARD_MODE=alongside`, `WIZARD_STRICT=1`, private access disabled and the plugin ref pinned. Its separate manifest changes **only** the WAM source selector. Normal `install.sh` invokes the actual `wizard link --restart`; no substitute link implementation is used.
5. Wait for the actual Runtipi marketplace API through `Config().runtipi()` and persisted installation state. Assert clean alongside install outcome, all candidate checks, actual core container RepoDigests, split mounts, no containerized Hermes, normal `wizard doctor` checks and a live bridge request. No `doctor --gate` or chat probe.
6. Invoke actual `wizard unlink --restart`. Require its reported restoration/restart success, then **independently compare saved file bytes and metadata**; do not trust the CLI's self-report alone. Require the newly installed Wizard plugin to be removed, distinguish additions from preexisting owner entries, and check stock source identity again.
7. Relink using actual `wizard link --restart --plugin-ref ...`, rerun readiness/doctor/source/release checks, and leave the guest linked for later real UX/chat/DeFleur work. The preexisting local API key survives unlink and relink; this case does not exercise the separate no-key-generated-by-link variant.
8. Collect private evidence even on failure and stop only the owned guest in `finally` (bounded force-stop fallback if needed). Never delete its disk or auto-repair/retry a failed installation.

Immutable owner scope is explicit: existing `config.yaml`, `.env`, `SOUL.md`, `AGENTS.md`, `USER.md`, `auth.json`, `auth-sentinel.json`, `memories/`, `skills/`, and `plugins/`. Runtime SQLite databases, caches and logs are **not** asserted byte-identical. Newly added entries are enumerated separately. Tracked Hermes source is checked independently against official HEAD. No claim is made that every mutable byte in an active Hermes home remains unchanged.

The original release receipt must still show `status: mismatch`, its original WAM expected source, source `ok: false`, and `release_exact: false`. A successful experiment is **not exact release acceptance**. Every runner receipt retains `acceptance: pending`; final acceptance belongs only to the parent.

## Restart readiness and evidence

A later authorized worker that restarts this retained guest must wait **after** Lima start and **before** WAM lifecycle calls:

```sh
export LIMA_HOME=/Volumes/ThalesMedia/wizard-os/e2e-022/lima
export LIMA_CACHE_HOME=/Volumes/ThalesMedia/wizard-os/e2e-022/lima-cache
limactl shell --workdir=/ alongside-022 -- bash -c \
  'exec python3 "$HOME/.alongside-022-qa/runner.py" --guest-phase ready'
```

Use `alongside-022-amd64` for the x86_64 fixture. The waiter has a 300-second deadline and bounded subprocess attempts; it records only attempt timestamps/exit codes, not authentication material. Initial bootstrap still owns its internal Runtipi startup: the runner does not monkeypatch the installer or hide a strict failure by rerunning it.

The runner prints step exit codes and `PRIVATE_RECEIPT=<path>`. Its private receipt contains actual remote hostname, exact invocation, source revision, runner hash, immutable companion refs, each command and exit status. The original failing phase status wins over successful collection/cleanup; collection/readback/stop failure also makes an otherwise successful run nonzero. Logs, generated Lima YAML, guest evidence tar and receipts are mode-restricted beneath `root/evidence/alongside-*`.

**Do not publish the raw evidence archive or receipt.** It deliberately contains baseline `.env` bytes, random local API credentials, runtime paths/hostname, and potentially diagnostic data. Publish only a separately reviewed/redacted result summary. This source document contains no owner hostnames, home paths or credentials.

## Validation before execution

Only AST syntax and `git diff --check` were run during preparation. The parent may queue the existing focused WAM source checks from `docs/release-pin-bootstrap.md` on Thales if further source assurance is needed. No VM, install, build, SSH runner, queue submission, chat or DeFleur acceptance was executed by the preparer.
