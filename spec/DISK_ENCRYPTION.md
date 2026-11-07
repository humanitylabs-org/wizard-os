# Disk encryption

**Decision #112 (James, 7 Nov 2026).** Wizard OS encrypts the owner's disk by default. The key is sealed in the box's security chip (TPM 2.0), so the box unlocks itself on normal restarts and stays always-on. A one-time recovery key is the way back in when the chip says no. Network-check unlock is a later optional feature, not part of the standard.

## The model

- **LUKS2** holds the data. On a dedicated box that is the whole system: root, every Wizard data root under it (Wizard home, app data, owner files, Docker, agent homes, backup staging) and swap, in one LUKS2 volume with LVM inside.
- **TPM 2.0, sealed to PCR 7 and to PCR 15 = 0.**
  - PCR 7 records the Secure Boot state: whether it is on, the firmware's key databases (PK, KEK, db, dbx), the certificates that verified each boot stage (Microsoft's CA for shim, Debian's CA for GRUB and the kernel) and shim's SBAT level. It does not record the hash of the kernel, the initramfs, the kernel command line, GRUB's menu or other firmware settings, so kernel updates do not change it.
  - PCR 15 = 0 means the chip releases the key once per boot: `tpm2-measure-pcr=yes` extends PCR 15 with a value derived from the volume key right after unlock, so nothing on the running box can ask the chip again.
  - Enrolled with `systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=7+15:sha256=<64 zeros>` (systemd 257 on Debian 13). The unseal uses a salted, encrypted session to the chip.
  - `/etc/crypttab`: `wizard_crypt UUID=… none luks,discard,tpm2-device=auto,tpm2-measure-pcr=yes`. Because PCR 15 = 0 is single-use, only one chip-sealed volume unlocks per boot; any extra encrypted disk on an encrypted box uses a key file stored on the encrypted root.
- **A systemd initramfs.** Debian's default `initramfs-tools` ignores `tpm2-device=`, so a dedicated box uses `dracut` (which replaces `initramfs-tools` and `cryptsetup-initramfs`) with `systemd-cryptsetup` (which carries `systemd-cryptenroll`) and `tpm2-tools` with its `libtss2` libraries. Data volumes unlocked after boot (the `wam disk encrypt` case) do not need it.
- **One recovery key** per volume, made with `systemd-cryptenroll --recovery-key` at first-run setup and written only to the box's local consoles (its screen, and a serial console if one is configured). It is shown once with a plain "save this" step and never written to disk. No agent, log, backup, status call or support bundle reads or carries it; Wizard keeps only the fact that a recovery slot exists. Setup needs a keyboard and screen at the box anyway (the Tailscale QR code) and runs before the box joins Tailscale.
- **No passphrase on a normal restart.** The installer's temporary unlock is wiped during first-run setup (below).

## What it protects

The standard protects against an **offline read of the disk**.

| Situation | Result |
|---|---|
| The disk is pulled and read elsewhere (stolen, discarded, sent for repair) and never put back | Unreadable. The sealed key in the LUKS2 header opens only with this chip in this boot state; the other way in is the recovery key. |
| An OS not signed by Debian is booted from USB, with Secure Boot on | The chip withholds the key (PCR 7 differs). |
| Secure Boot is turned off, or its key databases change | The chip withholds the key. The boot asks for the recovery key. |
| A kernel update, or most OS package updates, then a reboot | Unlocks by itself as before. |

## What it does not protect

Anyone who has **the whole box** for a while and knows what they are doing can reach the data. Firmware passwords and USB boot off only slow this down: clearing the firmware settings often resets them without changing PCR 7.

- **A Debian-signed USB stick.** A stock Debian live or installer stick, booted with Secure Boot on, produces the same PCR 7, and PCR 15 is still 0, so root on the stick can ask the chip for the key. This is the easiest attack on a whole box.
- **The GRUB menu and the unencrypted `/boot`.** GRUB's boot-line editor and console, and the initramfs on `/boot`, are not measured into PCR 7. Adding `init=` or `rd.break`, loading another initramfs, or replacing the one on `/boot` (disk pulled and put back) gets the key on the next boot.
- **A whole stolen box that boots normally** unlocks itself, as it does at home. The login, SSH keys and Tailscale are then the barrier.
- **A running box, and root on it.** The volume key is in memory while the disk is unlocked, and root can read it. PCR 15 stops a second unseal from the chip, not this.
- **Secure Boot off.** The box is still encrypted and still unlocks itself, and a pulled disk is still unreadable, but any USB boot with Secure Boot off produces the same PCR 7. Status says so. Turning Secure Boot on asks for the recovery key once, then the owner re-seals.
- **Boot security updates that change PCR 7:** a firmware or BIOS update, a dbx revocation update, the Microsoft 2023 certificate rollout, a shim update that raises its SBAT level, or a kernel signed with an owner-enrolled key (MOK). The next boot asks for the recovery key once, at the box's keyboard and screen; a headless box waits there and is unreachable until someone types it. To stop this happening unattended, a chip-sealed box holds `shim-signed` from automatic upgrades (`apt-mark hold`), does not install `fwupd`, and Wizard never reboots by itself. The owner applies these at the box, enters the recovery key once and re-seals. Status warns when a boot security package changed since the last seal: "The next restart may ask for the recovery key."
- **Only Wizard data encrypted (alongside).** Root stays unencrypted, so anyone who can write to root (pull the disk, add a user, key or service, put it back) or edit GRUB gets the data volume unlocked by the chip on the next boot. Data that sat on the old unencrypted disk before the move may still be readable from its free blocks until that disk is wiped or retired.

Closing the whole-box gaps needs the later work: a signed boot image (UKI) with a signed PCR 11 policy, an owner PIN, or the network check.

## Recovery

When the chip withholds the key, the boot screen asks for a passphrase. Typing the recovery key unlocks it. After a deliberate change, the owner runs `wam disk reseal` at the box. It:

- runs only from a local console session (logind `Remote=no` on seat0), never over SSH or from an agent's pty;
- asks for the recovery key itself (never from an agent, argument or file);
- enrolls a fresh chip slot for the current boot state and removes the old one.

A restart confirms the new seal. Losing both the chip state (new motherboard, cleared TPM) and the recovery key means the data is gone; the encrypted box backup is the remaining copy.

## Status

`wam disk status` is a read-only check. It reports:

- whether the volume holding Wizard data is encrypted;
- whether it is chip-sealed, and to which PCRs;
- whether a recovery key is enrolled;
- whether Secure Boot is on;
- whether a boot security package changed since the last seal.

It never reads key material. Settings, Security shows one plain line from it:

| State | Line |
|---|---|
| Encrypted, chip-sealed, recovery key saved | Disk encrypted, unlocks with this box's security chip |
| Same, Secure Boot off | Disk encrypted, unlocks with this box's security chip. Secure Boot is off: turn it on for stronger protection |
| Chip-sealed, recovery key not made yet | Disk encrypted. Recovery key not saved yet: finish setup on this box's screen |
| Encrypted, chip seal not finished | Disk encrypted, not yet sealed to this box's security chip |
| Encrypted, needs a passphrase | Disk encrypted, asks for a passphrase at every start |
| Only Wizard data encrypted (alongside, after `wam disk encrypt`) | Wizard data encrypted, unlocks with this box's security chip |
| No chip found, not encrypted | Not encrypted: no security chip found (it may be turned off in the firmware settings) |
| Not encrypted | Not encrypted |
| VPS | Not encrypted by Wizard: relies on your provider's disk encryption |
| Mac, FileVault on | Protected by FileVault on this Mac |
| Mac, FileVault off | Not encrypted: FileVault is off on this Mac |

When a boot security package changed since the last seal, the line adds: "The next restart may ask for the recovery key."

## Per platform

### Dedicated Linux box (wizard-os-iso)

With a TPM 2.0 chip, the installer always encrypts: one LUKS2 volume with LVM for root and swap, `/boot` and the EFI partition outside, and dracut as the initramfs.

1. **Install.** The installer formats with a random temporary passphrase. It exists only in the installer's memory and as a one-time key file inside the first initramfs on `/boot`. No owner data exists yet.
2. **First boot.** The initramfs unlocks with that key file. The system then seals the chip slot for this real installed boot (not the installer's) and tests it without unlocking (`cryptsetup open --test-passphrase --token-only`). It rebuilds the initramfs to unlock with the chip only, with no key file, and restarts.
3. **Second boot.** The chip unlocks the disk with no prompt. First-run setup on the box's screen makes the recovery key, shows it once, and wipes the temporary passphrase slot. Only then does the Tailscale step start. Copies of the temporary passphrase left on `/boot` are useless once its slot is wiped.

If a step fails, the box keeps the temporary unlock and status says the chip seal is not finished. It is never left without a working unlock.

**No TPM 2.0 found:** install unencrypted and record `not encrypted: no security chip`. Never require a password at every boot as the fallback.

### Linux alongside an existing OS, and boxes installed before this decision

Root is never re-encrypted in place and existing disks are never repartitioned silently. `wam disk encrypt` is an opt-in step at the box. It:

1. needs a new drive or an empty partition;
2. takes a verified backup first;
3. creates a TPM-sealed LUKS2 volume with a recovery key;
4. stops Wizard, moves the Wizard home and app data (which hold the agent homes, vault and tokens) onto it, and bind-mounts them back at their old paths, ordered with `RequiresMountsFor=` so Docker and the Wizard services cannot write underneath before the volume is mounted;
5. checks every file and keeps the old copy until the owner confirms.

On confirmation it deletes the old copy and trims free space. `wam disk encrypt --rollback` restores the old layout. Both need the same local-console confirmation as `wam disk reseal`. James's Minisforum gets it when its new SSDs arrive, as a separate attended step.

### VPS

No chip to seal to, and the provider controls the disk (a provider's virtual TPM adds nothing). Wizard reports "Not encrypted by Wizard: relies on your provider's disk encryption" and changes nothing.

### Mac (Wizard for Mac)

FileVault is the boundary. Wizard checks FileVault on the volume that actually holds the VM image, its rollback copies and the shared folder (it may be an external drive), and says plainly when it is off. No separate guest encryption in this round.

## Later, optional

- **Network-check unlock** (the box also needs the owner's network or phone to unlock): off by default, owner opt-in, after the chip-only standard is shipped.
- A signed boot image with a signed PCR 11 policy (or `systemd-pcrlock`) to close the `/boot`, GRUB and Debian-signed boot medium gaps, and to predict PCR 7 before boot security updates.
