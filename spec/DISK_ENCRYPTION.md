# Disk encryption

**Decision #112 (James, 7 Nov 2026).** Wizard OS encrypts the owner's disk by default. The key is sealed in the box's security chip (TPM 2.0), so the box unlocks itself on every normal restart and stays always-on. A one-time recovery key is the way back in when the chip says no. Network-check unlock is a later optional feature, not part of the standard.

## The model

- **LUKS2** holds the data. On a dedicated box that is the whole system: root, every Wizard data root under it (Wizard home, app data, owner files, Docker volumes, agent homes, backup staging) and swap.
- **TPM2 sealed to PCR 7** releases the key. PCR 7 records the Secure Boot state: whether it is on, the firmware's key databases, and which signing authorities were used to start the boot chain. It does not record the kernel or initramfs bytes, so kernel and ordinary OS updates do not change it. Enrolled with `systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=7`; unlocked in the initramfs by `systemd-cryptsetup` (`tpm2-device=auto` in `/etc/crypttab`).
- **One recovery key** per volume, made with `systemd-cryptenroll --recovery-key`. It is shown to the owner once, on the box's own screen during first-run setup, with a plain "save this" step, and then deleted from the box. No agent, log, backup, status call or support bundle ever reads or carries it. Wizard keeps only the fact that a recovery slot exists.
- **No other unlock.** The installer's temporary passphrase is random, never written outside the installer's memory and the encrypted volume, and its key slot is wiped once the chip slot is proven. No passphrase is asked on any normal restart.

## What it protects

| Situation | Result |
|---|---|
| The disk is pulled and read in another computer | Unreadable. The key never leaves this box's chip. |
| Someone boots the box from a USB stick with another OS, or with Secure Boot off | The chip withholds the key (PCR 7 differs). The system asks for the recovery key. |
| Someone changes firmware security settings (Secure Boot off, new keys added) | The chip withholds the key. The recovery key still unlocks; after a deliberate change the owner re-seals. |
| A kernel or OS package update, then a reboot | Unlocks by itself as before. |

## What it does not protect

- **A whole stolen box that boots normally.** It unlocks itself, like it does at home. The attacker then still faces the login, SSH keys, Tailscale and app sign-in, but disk encryption has done its part. Stronger protection against whole-box theft needs an extra factor at boot (owner PIN or network check), which is the later optional feature.
- **A running or already-unlocked box.** Encryption only matters while the key is not in memory. Root on a running box can read everything mounted.
- **Another boot medium signed by the same vendor (Debian).** It can reproduce the same PCR 7 value. Closing this needs a firmware administrator password with USB boot turned off (the install guide says how), or a later, stricter boot policy.
- **Secure Boot off.** The box is still encrypted and still unlocks by itself, and a pulled disk is still unreadable, but any USB boot with Secure Boot off measures the same PCR 7. Status says so plainly and asks the owner to turn Secure Boot on.
- **Firmware or bootloader security updates that change PCR 7** (a new Secure Boot revocation list, a shim SBAT bump). The next boot asks for the recovery key once; after it boots, re-seal. Predicting PCR 7 ahead of such updates is later work.

## Recovery

When the chip withholds the key, the boot screen asks for a passphrase. Typing the recovery key unlocks it. After a deliberate change (firmware update, Secure Boot turned on), the owner re-seals with `wam disk reseal`, which enrolls a fresh chip slot for the current state and removes the old one. Losing both the chip state (new motherboard, cleared TPM) and the recovery key means the data is gone; the encrypted box backup is the remaining copy.

## Status

`wam disk status` is a read-only check: is Wizard data on an encrypted volume, is it TPM-sealed (and to which PCRs), is a recovery key enrolled, and is Secure Boot on. It never reads key material. Settings, Security shows one plain line from it:

| State | Line |
|---|---|
| Encrypted, chip-sealed | Disk encrypted, unlocks with this box's security chip |
| Same, Secure Boot off | Disk encrypted, unlocks with this box's security chip. Secure Boot is off: turn it on for full protection |
| Encrypted, needs a passphrase | Disk encrypted, asks for a passphrase at every start |
| Only Wizard data encrypted (alongside, after `wam disk encrypt`) | Wizard data encrypted, unlocks with this box's security chip |
| No chip, not encrypted | Not encrypted: this box has no security chip |
| Not encrypted | Not encrypted |
| VPS | Relies on your provider's disk encryption |
| Mac, FileVault on | Protected by FileVault on this Mac |
| Mac, FileVault off | Not encrypted: FileVault is off on this Mac |

## Per platform

- **Dedicated Linux box (wizard-os-iso).** The installer always encrypts when the box has a TPM 2.0 chip: LUKS2 with LVM inside for root and swap, `/boot` and the EFI partition outside. The chip slot is sealed on the first boot of the installed system (so PCR 7 is the real installed boot, not the installer's). The recovery key is enrolled during install and shown at first boot before the Tailscale step, which is before any agent can reach the box. **No TPM 2.0:** install unencrypted and record `not encrypted: no security chip`. Never require a password at every boot as the fallback.
- **Linux alongside an existing OS, and boxes installed before this decision.** Root is never re-encrypted in place and existing disks are never repartitioned silently. `wam disk encrypt` is an opt-in, attended step: it needs a new drive or an empty partition, takes a verified backup first, creates a TPM-sealed LUKS2 volume with a recovery key, moves the Wizard data roots onto it (bind-mounted back at their old paths), checks every file, and keeps the old copy until the owner confirms. `wam disk encrypt --rollback` restores the old layout. James's Minisforum gets it when its new SSDs arrive, as a separate attended step.
- **VPS.** No chip to seal to and the provider controls the disk. Wizard reports `Relies on your provider's disk encryption` and changes nothing.
- **Mac (Wizard for Mac).** FileVault is the boundary: the VM disk image, its rollback copies and the shared folder all live on the Mac's own volume. Wizard reports FileVault's state and says plainly when it is off. No separate guest encryption in this round.

## Later, optional

- **Network-check unlock** (the box also needs the owner's network or phone to unlock): off by default, owner opt-in, after the chip-only standard is shipped.
- A stricter boot policy (signed PCR 11 / `systemd-pcrlock`) to close the same-vendor boot-medium gap and to predict PCR 7 before firmware updates.
