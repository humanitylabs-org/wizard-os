# Disk encryption

**Decision #112 (James, 7 Nov 2026).** Wizard OS encrypts the owner's disk by default. The key is sealed in the box's security chip (TPM 2.0), so the box unlocks itself on normal restarts and stays always-on. A one-time recovery key is the way back in when the chip says no. Network-check unlock is a later optional feature, not part of the standard.

## The model

- **LUKS2** holds the data. On a dedicated box that is the whole system: root, every Wizard data root under it (Wizard home, app data, owner files, Docker, agent homes, backup staging) and swap, in one LUKS2 volume with LVM inside.
- **TPM 2.0, sealed to PCR 7.**
  - PCR 7 records the Secure Boot state: whether it is on, the firmware's key databases (PK, KEK, db, dbx), the certificates that verified each boot stage (Microsoft's CA for shim, Debian's CA for GRUB and the kernel) and shim's SBAT level. It does not record the hash of the kernel, the initramfs, the kernel command line, GRUB's menu or other firmware settings, so kernel updates do not change it.
  - Enrolled with `systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=7` (systemd 257 on Debian 13). The unseal uses a salted, encrypted session to the chip.
  - `/etc/crypttab`: `<name> UUID=… none luks,discard,x-initrd.attach,tpm2-device=auto` (the installer's own name, `<disk>_crypt`).
  - No PCR 15 lock: `tpm2-measure-pcr=yes` does nothing unless the kernel booted as a measured UKI, which is later work.
- **A systemd initramfs.** Debian's default `initramfs-tools` ignores `tpm2-device=`, so a dedicated box uses `dracut` (which replaces `initramfs-tools` and `cryptsetup-initramfs`) with `systemd-cryptsetup` (which carries `systemd-cryptenroll`) and `tpm2-tools` with its `libtss2` libraries. Data volumes unlocked after boot (the `wam disk encrypt` case) do not need it.
- **One recovery key** per volume, made with `systemd-cryptenroll --recovery-key` at first-run setup and shown only on the box's screen (and on a serial console only when the installer was told to with `wizard.recovery_console=`; serial output can be logged off the box). It is shown once with a plain "save this" step and never written to disk. No agent, log, backup, status call or support bundle reads or carries it; Wizard keeps only the fact that a recovery slot exists. Setup needs a keyboard and screen at the box anyway (the Tailscale QR code); it runs on its own screen (tty8) without holding up SSH or other services, and the Tailscale step waits for it. On a fresh dedicated box no agent exists yet at that point (Wizard and its agents are installed after the box joins Tailscale, and the installer puts no agent's SSH key or account on the box: the owner adds the agent's key only after that), so none can see the key. On a seal retry after Tailscale, and in `wam disk encrypt` on an existing box, the key is shown on a box where the agent's account and its admin rights already exist: keeping it out of agents there is a design rule, not a boundary against root (see Recovery).
- **No passphrase on a normal restart.** The installer's temporary unlock is wiped during first-run setup (below).

## What it protects

The standard protects against an **offline read of the disk**.

| Situation | Result |
|---|---|
| The disk is pulled and read elsewhere (stolen, discarded, sent for repair) and never put back | Unreadable. The sealed key in the LUKS2 header opens only with this chip in this boot state; the other way in is the recovery key. |
| An OS not signed by Debian is booted from USB, with Secure Boot on | The chip withholds the key (PCR 7 differs). |
| The disk is attached to another computer or VM, with its own chip | That chip has never seen the key. The boot asks for the recovery key. |
| Secure Boot is turned off, or its key databases change | The chip withholds the key. The boot asks for the recovery key. |
| A kernel update, or most OS package updates, then a reboot | Unlocks by itself as before. |

## What it does not protect

Anyone who has **the whole box** for a while and knows what they are doing can reach the data. Firmware passwords and USB boot off only slow this down: clearing the firmware settings often resets them without changing PCR 7.

- **A Debian-signed USB stick.** A stock Debian live or installer stick, booted with Secure Boot on, produces the same PCR 7, so root on the stick can ask the chip for the key. This is the easiest attack on a whole box.
- **The GRUB menu and the unencrypted `/boot`.** GRUB's boot-line editor and console, and the initramfs on `/boot`, are not measured into PCR 7. Adding `init=` or `rd.break`, loading another initramfs, or replacing the one on `/boot` (disk pulled and put back) gets the key on the next boot.
- **A whole stolen box that boots normally** unlocks itself, as it does at home. The login, SSH keys and Tailscale are then the barrier.
- **A running box, and root on it.** The volume key is in memory while the disk is unlocked, and root can read it or ask the chip again. On today's boxes the agent's user has passwordless sudo, so this includes the agent.
- **Secure Boot off.** The box is still encrypted and still unlocks itself, and a pulled disk is still unreadable, but any USB boot with Secure Boot off can reproduce the same PCR 7. Status says so. Turning Secure Boot on asks for the recovery key once, then the owner re-seals.
- **Boot security updates that change PCR 7:** a firmware or BIOS update (sometimes), a dbx revocation update, the Microsoft 2023 certificate rollout, a shim update that raises its SBAT level (including booting someone's newer shim, such as a newer Debian rescue stick, which can raise the firmware's SBAT level for every later boot), or a kernel signed with an owner-enrolled key (MOK). The next boot asks for the recovery key once, at the box's keyboard and screen; a headless box waits there and is unreachable until someone types it. To stop this happening unattended, a chip-sealed box holds `shim-signed` from automatic upgrades (`apt-mark hold`), does not install `fwupd`, and Wizard never reboots by itself. The owner applies these at the box, enters the recovery key once and re-seals. Status warns when a boot security package changed since the last seal ("The next restart may ask for the recovery key") and when a held one has an update waiting ("A boot security update is waiting: install it at this box").
- **Dual boot.** Another OS on the same box (Windows Update in particular) applies dbx and Secure Boot certificate updates by itself, which changes PCR 7 for the Linux boot too. A dedicated box has no other OS. On an alongside box the Wizard data volume is `nofail,headless=true`: the box still starts without waiting at a prompt, the Wizard services stay stopped, and a small unit on the unencrypted root shows "Wizard data is locked: enter the recovery key at this box" on the console and login message (Settings cannot show it, because the shell's data is on the locked volume). `wam disk unlock` at the box opens it and starts the held services.
- **Only Wizard data encrypted (alongside).** Root stays unencrypted, so anyone who can write to root (pull the disk, add a user, key or service, put it back) or edit GRUB gets the data volume unlocked by the chip on the next boot. What stays on the unencrypted root: Docker's images and the owner's other Docker volumes, swap, the system journal and logs, `/tmp`, and anything Wizard data left in free blocks before the move (until that disk is wiped or retired). App data, agent homes, the vault, tokens and backup staging move.

Closing the whole-box gaps needs the later work: a signed boot image (UKI) with a signed PCR 11 policy, an owner PIN, or the network check.

## Recovery

When the chip withholds the key on a dedicated box, the boot screen asks for a passphrase and typing the recovery key unlocks it. On an alongside box the box starts with Wizard stopped and `wam disk unlock` at the box takes the recovery key. After a deliberate change, the owner runs `wam disk reseal` at the box. It:

- runs only from a local console session (a logind session with `Remote=no` on a local tty or serial line), never over SSH or from an agent's pty. This guards against mistakes; it is not a boundary against something that already has root;
- asks for the recovery key itself (never from an agent, argument or file). On a box where the agent has root, the agent could still capture it while it is typed; keeping it out of agents is a design rule, not a boundary against root;
- enrolls a fresh chip slot for the current boot state and removes the old one.

A restart confirms the new seal. Losing both the chip state (new motherboard, cleared TPM) and the recovery key means the data is gone; the encrypted box backup is the remaining copy.

## Status

`wam disk status` is a read-only check. It reports:

- whether the volume holding Wizard data is encrypted;
- whether it is chip-sealed, and to which PCRs;
- whether a recovery key is enrolled;
- whether Secure Boot is on;
- whether a boot security package changed since the last seal, or a held one has an update waiting;
- whether the seal still matches: the current PCR 7 against the value recorded when it was sealed (both public), and whether this start unlocked without the chip;
- whether the owner confirmed saving the recovery key (a marker written when the owner types back the key's first 8 letters; the LUKS header only shows that a recovery slot exists);
- whether the temporary install key (its key slot or key file) is still present.

Boot security packages are `shim-signed` and the firmware version (DMI BIOS version); a kernel signed by anything other than Debian's key also counts.

It never reads key material. Settings, Security shows one plain line from it:

| State | Line |
|---|---|
| Encrypted, chip-sealed, recovery key confirmed saved | Disk encrypted, unlocks with this box's security chip |
| Same, Secure Boot off | Disk encrypted, unlocks with this box's security chip. Secure Boot is off: turn it on for stronger protection |
| Encrypted, the temporary install key is still on this box (seal failed, or recovery key not confirmed yet). Takes priority over every other row | Not protected yet: the disk key is still stored on this box. Finish setup on this box's screen (if it keeps failing, check the security chip is turned on in the firmware settings) |
| Chip-sealed, but this start unlocked with the recovery key or the chip no longer matches | This box's security chip no longer matches: run `wam disk reseal` at this box |
| Encrypted, needs a passphrase | Disk encrypted, asks for a passphrase at every start |
| Only Wizard data encrypted (alongside, after `wam disk encrypt`) | Wizard data encrypted, unlocks with this box's security chip (the same Secure Boot and update notes apply) |
| Alongside, chip refused at this start (console and login message only) | Wizard data is locked: enter the recovery key at this box |
| No chip found, not encrypted | Not encrypted: no security chip found (it may be turned off in the firmware settings) |
| Not encrypted | Not encrypted |
| VPS | Not encrypted by Wizard: relies on your provider's disk encryption |
| Mac, FileVault on | Protected by FileVault on this Mac |
| Mac, FileVault off | Not encrypted: FileVault is off on this Mac |

When a boot security package or a Secure Boot variable (db, dbx, KEK, SbatLevelRT, compared by hash with the values at seal time) changed since the last seal, the line adds: "The next restart may ask for the recovery key." When a held boot security package has an update waiting, it adds: "A boot security update is waiting: install it at this box."

## Per platform

### Dedicated Linux box (wizard-os-iso)

With a TPM 2.0 chip, the installer always encrypts: one LUKS2 volume with LVM for root and swap, `/boot` and the EFI partition outside, and dracut as the initramfs.

1. **Install.** The installer formats with a random temporary passphrase. It exists only in the installer's memory, as a root-only key file on the encrypted root, and inside every initramfs on `/boot` built while it exists (a dracut `install_items` drop-in, so a kernel update before the seal still boots). Until the seal is confirmed, `/etc/crypttab` unlocks with that key file only (`<name> UUID=… /etc/wizard/disk/install.key luks,discard,x-initrd.attach`, no `tpm2-device=`: systemd-cryptsetup treats a key file next to `tpm2-device=` as a sealed blob, not a passphrase). No owner data exists yet.
2. **First boot.** The initramfs finds no chip slot and unlocks with the key file. First-run setup, on the box's screen (its own tty8; SSH and other services start as usual, and only the Tailscale step waits for it):
   1. seals a chip slot for this real installed boot (not the installer's) and tests it without unlocking (`cryptsetup open --test-passphrase --token-only`);
   2. makes the recovery key, checks it opens the disk, and shows it once with "Write it down or take a photo"; the owner types back its first 8 letters (a wrong answer is asked again);
   3. only after that, rewrites `/etc/crypttab` to the final chip line (`none luks,discard,x-initrd.attach,tpm2-device=auto`), removes the dracut drop-in, builds every initramfs beside the live one, checks each holds the chip support and no key file, and only then swaps them in (on a failed check the live images stay, and the crypttab rewrite and drop-in removal are undone); then wipes the temporary passphrase slot, checks only the chip and recovery slots remain, deletes the key file and restarts.
3. **Second boot.** The chip unlocks the disk with no prompt, and the Tailscale step starts. If the chip ever refuses, the owner has the recovery key they just saved.

If sealing or its test fails, the box keeps the temporary unlock and shows no recovery key. The screen says "Disk setup could not finish, so the disk is not protected yet", setup carries on to Tailscale, status shows the "Not protected yet" line, and every start retries the seal. A later successful retry shows the recovery key on the box's screen without holding up any service, and wipes the temporary key and restarts only after the owner types back its start there. If the box loses power before that, the next start replaces the unconfirmed recovery key with a new one. It is never left without a working unlock.

Wiping the temporary slot does not change the volume key. Anyone who copied the LUKS header and the first initramfs before step 2 finished can open the volume at any later time, including data written afterwards. This matters if someone else had the box between install and the first successful seal (a box installed for someone and shipped to them, or a box whose seal kept failing): run first-run setup before it leaves the installer's hands, or re-encrypt to a new volume key (`cryptsetup reencrypt`), which is the only complete fix. After the rebuild, `/boot` is trimmed so old initramfs images do not linger in free blocks.

**No TPM 2.0 found:** install unencrypted and record `not encrypted: no security chip`. Never require a password at every boot as the fallback.

### Linux alongside an existing OS, and boxes installed before this decision

Root is never re-encrypted in place and existing disks are never repartitioned silently. `wam disk encrypt` is an opt-in step at the box. It:

1. needs a new drive or an empty partition;
2. takes a verified backup first;
3. creates a TPM-sealed LUKS2 volume with a recovery key;
4. stops Wizard, moves the Wizard home and app data (which hold the agent homes, vault and tokens) onto it, and bind-mounts them back at their old paths, ordered with `RequiresMountsFor=` on Wizard's own units (not the owner's other containers). The emptied folders left on root become immutable mount points (`chattr +i`), so nothing can write underneath while the volume is locked, including containers Docker restarts by itself: their bind mounts fail instead of writing plaintext. Wizard app data lives in bind mounts under the moved folders; a Wizard app that keeps data in a Docker named volume is listed and moved too. The volume is `nofail,headless=true`, unlocked by the chip after boot, and its filesystem mount and every bind mount are `nofail` too, so a locked volume never sends the boot to emergency mode. The old copy is renamed aside on root, not deleted;
5. shows the recovery key once on the box's screen with the same type-back confirmation and saved marker as a dedicated box, holds `shim-signed`, and turns off automatic `fwupd` updates if it is installed;
6. checks every file and keeps the old copy until the owner confirms.

On confirmation it deletes the old copy and trims free space. `wam disk encrypt --rollback` stops Wizard, unmounts the bind mounts, clears the immutable flag, copies the current data from the volume back to the old folders, verifies it, then removes the mount units and the `RequiresMountsFor=` lines (before confirmation it never falls back to the stale old copy). Both need the same local-console confirmation as `wam disk reseal`. James's Minisforum gets it when its new SSDs arrive, as a separate attended step.

### VPS

No chip to seal to, and the provider controls the disk (a provider's virtual TPM adds no protection from the provider). Many providers do not encrypt at all, and Wizard cannot check. Wizard reports "Not encrypted by Wizard: relies on your provider's disk encryption" and changes nothing.

### Mac (Wizard for Mac)

FileVault is the boundary. Wizard checks encryption (FileVault, or APFS volume encryption on an external drive) on the volume that actually holds the VM image, its rollback copies and the shared folder, and says plainly when it is off. No separate guest encryption in this round.

## Later, optional

- **Network-check unlock** (the box also needs the owner's network or phone to unlock): off by default, owner opt-in, after the chip-only standard is shipped.
- A signed boot image with a signed PCR 11 policy (or `systemd-pcrlock`) to close the `/boot`, GRUB and Debian-signed boot medium gaps, and to predict PCR 7 before boot security updates.
