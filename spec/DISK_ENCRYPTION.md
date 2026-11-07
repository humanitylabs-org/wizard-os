# Disk encryption

**Decision #112 (James, 7 Nov 2026).** Wizard OS encrypts the owner's disk by default. The key is sealed in the box's security chip (TPM 2.0), so the box unlocks itself on normal restarts and stays always-on. A one-time recovery key is the way back in when the chip says no. Network-check unlock is a later optional feature, not part of the standard.

## The model

- **LUKS2** holds the data. On a dedicated box that is the whole system: root, every Wizard data root under it (Wizard home, app data, owner files, Docker volumes, agent homes, backup staging) and swap.
- **TPM 2.0, sealed to PCR 7 and PCR 15 = 0.** PCR 7 records the Secure Boot state: whether it is on, the firmware's key databases (PK, KEK, db, dbx) and which signing authorities started the boot chain (firmware, shim, and shim's SBAT level). It does not record the kernel, the initramfs, the kernel command line or other firmware settings, so kernel updates do not change it. PCR 15 = 0 means the chip releases the key only once per boot: `tpm2-measure-pcr=yes` extends PCR 15 with the volume key right after unlock, so a process on the running box cannot ask the chip again. Enrolled with `systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=7+15:sha256=0…0` (systemd 257; the unseal uses a salted, encrypted session to the chip, so the secret does not cross the bus in the clear).
- **A systemd initramfs.** Debian's default `initramfs-tools` ignores `tpm2-device=` in `/etc/crypttab`, so a dedicated box uses dracut with its `systemd-cryptsetup` and `tpm2-tss` modules. Data volumes unlocked after boot (the `wam disk encrypt` case) do not need it.
- **One recovery key** per volume, made with `systemd-cryptenroll --recovery-key` on the box's own screen during first-run setup, shown once with a plain "save this" step, and never written to disk. No agent, log, backup, status call or support bundle reads or carries it; Wizard keeps only the fact that a recovery slot exists. Setup needs a keyboard and screen at the box anyway (the Tailscale QR code), and it runs before the box joins Tailscale, so before any agent can reach it.
- **No other unlock.** See the dedicated box steps below for how the first boot unlocks before the chip slot exists. No passphrase is asked on a normal restart.

## What it protects

| Situation | Result |
|---|---|
| The disk is pulled and read elsewhere (stolen, discarded, sent for repair) and not put back | Unreadable. The key exists only in the chip's sealed form and, while the box runs, in its memory. |
| Someone boots a USB stick with an OS not signed by Debian, while Secure Boot is on | The chip withholds the key (PCR 7 differs). The system asks for the recovery key. |
| Someone turns Secure Boot off or changes its key databases | The chip withholds the key. The recovery key still unlocks; after a deliberate change the owner re-seals. |
| Someone adds a shell or single-user option to the boot line at the GRUB menu (`init=`, `single`, `rd.break`, `systemd.unit=`, debug shell) | The initramfs sees it and extends PCR 15 before unlocking, so the chip withholds the key and the recovery key is needed. |
| A kernel update or most OS package updates, then a reboot | Unlocks by itself as before. |

## What it does not protect

The standard protects an **offline read of the disk**. Anyone who has the whole box for a while and knows what they are doing can still reach the data:

- **A whole stolen box that boots normally** unlocks itself, as it does at home. The login, SSH keys and Tailscale still stand between a thief and the data, but they are software barriers on a running system.
- **Tampering with the unencrypted `/boot`.** The initramfs and GRUB's console are not measured into PCR 7. Someone who replaces the initramfs (or loads their own from GRUB's console or another Debian-signed boot medium) and lets the box boot can capture the key. Firmware passwords and USB boot off raise the bar (the install guide says how) but are not a boundary: clearing the firmware settings often resets them without changing PCR 7.
- **A running box, and root on it.** The volume key is in memory while the disk is unlocked, and root can read it. PCR 15 stops a second unseal from the chip, not this.
- **Secure Boot off.** The box is still encrypted and still unlocks itself, and a pulled disk is still unreadable, but any USB boot with Secure Boot off measures the same PCR 7. Status says so and asks the owner to turn Secure Boot on (which asks for the recovery key once, then `wam disk reseal`).
- **Boot security updates that change PCR 7:** a new revocation list (dbx), the Microsoft 2023 certificate rollout, a shim update that raises its SBAT level, or a kernel signed with an owner-enrolled key (MOK). The next boot asks for the recovery key once, at the box's keyboard and screen; a headless box waits there. Status warns when a boot security package changed since the last seal. Predicting PCR 7 ahead of these updates is later work.
- **Only Wizard data encrypted (alongside).** Root stays unencrypted, so anyone who can write to root (pull the disk, add a user, key or service, put it back) or edit GRUB gets the data volume unlocked by the chip on the next boot. This layout protects a disk read, nothing more.

Closing the whole-box gaps needs the later work: a signed boot image (UKI) with a signed PCR 11 policy, an owner PIN, or the network check.

## Recovery

When the chip withholds the key, the boot screen asks for a passphrase. Typing the recovery key unlocks it. After a deliberate change (firmware update, Secure Boot turned on), the owner runs `wam disk reseal` at the box: it asks for the recovery key itself (never from an agent or a file), enrolls a fresh chip slot for the current state and removes the old one. It refuses to run without an attended terminal. Losing both the chip state (new motherboard, cleared TPM) and the recovery key means the data is gone; the encrypted box backup is the remaining copy.

## Status

`wam disk status` is a read-only check: is Wizard data on an encrypted volume, is it TPM-sealed (and to which PCRs), is a recovery key enrolled, is Secure Boot on, and did a boot security package change since the last seal. It never reads key material. Settings, Security shows one plain line from it:

| State | Line |
|---|---|
| Encrypted, chip-sealed | Disk encrypted, unlocks with this box's security chip |
| Same, Secure Boot off | Disk encrypted, unlocks with this box's security chip. Secure Boot is off: turn it on for stronger protection |
| Encrypted, chip seal not finished | Disk encrypted, not yet sealed to this box's security chip |
| Encrypted, needs a passphrase | Disk encrypted, asks for a passphrase at every start |
| Only Wizard data encrypted (alongside, after `wam disk encrypt`) | Wizard data encrypted, unlocks with this box's security chip |
| No chip found, not encrypted | Not encrypted: no security chip found (it may be turned off in the firmware settings) |
| Not encrypted | Not encrypted |
| VPS | Relies on your provider's disk encryption |
| Mac, FileVault on | Protected by FileVault on this Mac |
| Mac, FileVault off | Not encrypted: FileVault is off on this Mac |

When a boot security package changed since the last seal, the line adds: "The next restart may ask for the recovery key."

## Per platform

- **Dedicated Linux box (wizard-os-iso).** With a TPM 2.0 chip the installer always encrypts: LUKS2 with LVM inside for root and swap, `/boot` and the EFI partition outside, dracut as the initramfs.
  1. The installer formats with a random temporary passphrase that never leaves the installer's memory except as a one-time key file, and puts that key into the first initramfs. No owner data exists yet.
  2. First boot unlocks with that key file, then seals the chip slot for this real installed boot (not the installer's) and proves it unlocks. It rebuilds the initramfs to unlock with the chip only, with no key file.
  3. First-run setup on the box's screen makes the recovery key, shows it once, then wipes the temporary key slot and key file. This is before the Tailscale step.

  **No TPM 2.0 found:** install unencrypted and record `not encrypted: no security chip`. Never require a password at every boot as the fallback.
- **Linux alongside an existing OS, and boxes installed before this decision.** Root is never re-encrypted in place and existing disks are never repartitioned silently. `wam disk encrypt` is an opt-in, attended step: it needs a new drive or an empty partition, takes a verified backup first, creates a TPM-sealed LUKS2 volume with a recovery key, moves the Wizard data roots onto it (bind-mounted back at their old paths), checks every file, and keeps the old copy until the owner confirms. `wam disk encrypt --rollback` restores the old layout and needs the same attended confirmation. James's Minisforum gets it when its new SSDs arrive, as a separate attended step.
- **VPS.** No chip to seal to and the provider controls the disk. Wizard reports `Relies on your provider's disk encryption` and changes nothing.
- **Mac (Wizard for Mac).** FileVault is the boundary: the VM disk image, its rollback copies and the shared folder all live on the Mac's own volume. Wizard reports FileVault's state and says plainly when it is off. No separate guest encryption in this round.

## Later, optional

- **Network-check unlock** (the box also needs the owner's network or phone to unlock): off by default, owner opt-in, after the chip-only standard is shipped.
- A signed boot image with a signed PCR 11 policy (or `systemd-pcrlock`) to close the `/boot` tampering and same-vendor boot-medium gaps, and to predict PCR 7 before boot security updates.
