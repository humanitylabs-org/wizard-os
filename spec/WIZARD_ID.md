# Wizard ID v0.1

**Status:** approved by James, 10 Oct 2026 ([DECISIONS](../docs/DECISIONS.md) #39); key model revised 24 Oct 2026 (#94). Jan to review the key handling and bridge. Build step 1 in progress (Archimedes).

Your Wizard ID is a Nostr key pair. The public half (`npub`) is your name everywhere in Wizard: the apps you publish, who follows you, and what your Wizard does for you. The private half signs. It is created on your phone, inside the Wizard app, and no one else holds a copy. That includes Humanity Labs, your Wizard box and the agent.

People never have to install a separate signer app (Amber or anything else). The ordinary screens say **Wizard ID**, **Approve & sign** and **Signed**. `nsec`, relays and event kinds appear only under Advanced.

## Where the key lives

- **The Android app `ai.wizards.os`.** The app generates the secret and encrypts it under an Android Keystore AES-GCM key (StrongBox when the phone has it). That key needs a fresh biometric or device PIN for every single use: `setUserAuthenticationParameters(0, BIOMETRIC_STRONG | DEVICE_CREDENTIAL)`, and it is invalidated if new fingerprints are enrolled. The secret is decrypted for one signature, the signature is checked, and the secret is wiped. Keystore can't sign secp256k1 itself, so it wraps the key instead of holding it.
- **Signing library:** `fr.acinq.secp256k1:secp256k1-kmp` (BIP-340 Schnorr). Every signature is verified against the public key before it leaves the signer.
- **Out of reach:** the WebView, the Wizard box, Hermes, connectors and model context. The page can *ask* for a signature through the bridge. Only the native approval sheet can grant it, and only after the system biometric/PIN prompt.
- **Starting code:** the September `android-authority` prototype (`KeyVault.kt`: enrol, wrap, biometric-gated Schnorr signing) moves into `ai.wizards.os`, which then ships as one app.
- **Later hardening:** on the GrapheneOS reference build the signer can move into a separate package with no launcher icon. The bridge and the screens stay the same.

## Onboarding

1. **Create your Wizard ID.** Enter a name and pick a photo. The key is generated on the phone.
2. **Save your key.** One button opens Android's own "save password" sheet (Credential Manager `CreatePasswordRequest`). The username is the Wizard ID name and the password is the `nsec`. It lands in whatever password manager the phone already uses, such as Google Password Manager, Bitwarden or 1Password. The copy on screen:
   > This key *is* your Wizard ID. Save it like a password. If you lose this phone and this key, your Wizard ID is gone for good, and nobody, including us, can reset it. Your Wizard and your files are not affected.
3. **Check the backup.** The app asks for the saved key back once (Credential Manager `GetPasswordOption`, one tap) and compares public keys. Only a match marks the ID as backed up. On phones with no password manager, the key is shown with Copy, and the person pastes it back to confirm. Settings shows "Not backed up" in amber until one of these checks passes.
4. **First signature.** Publishing the name and photo (Nostr kind 0) is the first approval. That's how people learn the sheet with something harmless.
5. **Already have Nostr?** Choose "Use my existing key", then pick it from the password manager or paste it. Both `nsec` and NIP-49 `ncryptsec` are accepted.

**Restore on a new phone:** choose "I have a Wizard ID", pick the key from the password manager, approve with biometric, done. Restoring keeps the same `npub`, profile, apps and follows.

## Signing

- **Who can ask:**
  - the Wizard UX on the phone, through the native bridge (`identity.sign`);
  - the box, through Wizard Link (a push notification that opens the sheet);
  - desktop browsers and Wizard for Mac, which route to the paired phone;
  - later, other Nostr apps through NIP-46 or NIP-55.
- **The sheet is drawn from the event itself, never from a description the requester supplies.** Known kinds get a plain sentence:
  - kind 0: "Update your profile";
  - kind 1: "Post publicly";
  - kind 3: "Change who you follow";
  - kind 30617: "Publish *DeFleur Video* as your app";
  - Wizard attestations: "Let *Archimedes* act as your Wizard";
  - action envelopes: "Restart the Wizard service".

  Anything else shows the raw event under "Unfamiliar request".
- **Every owner signature needs biometric/PIN.** Each approval covers one event, or one batch whose events are all listed. There are no remembered "always allow" grants for the owner key. This matches the 1 Sep authority rule.
- In chat, the amber **Needs your approval** card (locked 6 Sep) is the way in. **Approve & sign** opens the sheet. The thread then shows **Signed**, then **Sent** or **Executing**, and ends at **Verified** or a precise failure.

## Other devices

- Desktop UX, Wizard for Mac and browsers hold no key. Their requests appear as a notification on the paired phone.
- iPhone and Mac-only owners get the same design later, on Keychain plus Face ID or Touch ID. Until then they can still publish, and their apps show as unclaimed.

## Your Wizard's own key ([DECISIONS](../docs/DECISIONS.md) #94)

Each person has two keys and two names. Nothing else is ever shown.

- **Wizard ID (the phone key)** is the only key anyone sees as the person. Their name, friends, follows, apps and skins all hang off this `npub`.
- **Wizard (the box key)** is a device key. Its kind 0 says "*<name>*'s Wizard" and carries a `p` tag to the owner. It is never presented as the person. The box needs it for one reason: something must decrypt and answer while the phone is asleep. The box key is also the inbox key; there is no third key.
- Protocol-internal keys (Marmot/MLS leaf keys, NIP-59 throwaway keys) stay inside their protocol and are never named.

### The device list

The phone signs one addressable event, kind `30078` with `d=wizard-devices` (NIP-78 application data; a registered kind replaces it once a NIP exists). It has one `p` tag per device: `["p", <box hex>, <relay hint>, <roles…>]`, with roles `inbox`, `profile`, `messenger` and `agent`, plus an `expiration` tag about 90 days out that the phone renews. The sheet reads **Let this Wizard receive for you**.

**Every Wizard client reads identity with one rule, from one shared module:**
1. An `npub` with a current device list is a person, and their inbox is the listed device.
2. An `npub` whose kind 0 `p`-tags an owner whose current list names it is that owner's Wizard. Show the owner.
3. Otherwise the `npub` is a provisional identity and its own inbox. Show "*name*'s Wizard (unclaimed)". An unclaimed Wizard can't publish apps or skins under a person's name.

**Claim:** when a box-only user gets a phone ID, the phone lists the old box key. Friends re-key the pair to the owner automatically. Nobody has to re-add anyone.

**Revoke:** the phone republishes the list without the box, adding `["revoked", <box hex>, <unix time>]`. Readers drop that box's events after that time and stop encrypting to it. Name, friends, follows and apps are untouched. Whatever the box already decrypted stays exposed, and that is accepted.

### Who signs what

**The phone, with a fresh biometric each time:**
- kind 0 (name and photo) and kind 3 (follows);
- the device list, and attesting or revoking a Wizard;
- sending and accepting friend requests (the NIP-59 seal is signed and NIP-44-encrypted by the owner key);
- app and skin announcements;
- the owner action envelopes.

**The phone, under a short-timeout second Keystore key, limited to Messenger chores so that a batch takes one tap:**
- Marmot account-identity proofs and KeyPackage events;
- unwrapping Welcomes and any gift wrap addressed to the owner `npub`.

**The box, automatically:**
- receiving and unwrapping anything wrapped to its inbox key;
- re-sharing friends' encrypted profile parts on every change;
- relay authentication and routine Blossom uploads;
- Archimedes's own labelled posts.

**Messenger leaf keys on the box** sign every message in groups the box has joined. Sending invites (MLS Commits) and receiving need no phone.

### Messenger

The Marmot account is the owner `npub`, through MDK's external-signer account. The box runs MDK; its signer callback forwards to the phone over Wizard Link. The phone is needed:
- to join or create a group;
- for KeyPackage batches;
- for the per-group leaf rotation every 24–36 days, which the box queues into one sheet.

If the phone is offline, existing chats keep working, and new invites wait for a tap. Redirecting Welcomes to the box inbox key is a later Marmot proposal, not v1.

### Agent line

Anything that needs the owner key is the owner's act. The agent prepares it, and the phone shows "*Archimedes* asks: …", quoting the chat line behind it. The agent can't approve. Inside an existing conversation the box can already send, so the gate there is a per-contact switch, **Archimedes may reply for me** (default off), plus an audit log. Agent-sent messages carry a visible marker.

## App publishing ([DECISIONS](../docs/DECISIONS.md) #38)

- Publishing an app means the owner signs a NIP-34 announcement. It carries:
  - kind `30617` and `t=wizard-app`;
  - `clone` = the GitHub URL;
  - `r <earliest commit> euc`;
  - `maintainers` = co-authors' npubs and the Wizard's npub.
- **Credit needs both sides.** The repo's `wizard.md` names `publisher: npub1…`, which proves control of the repo. That npub signs the announcement, which proves control of the key. The announcement's `clone` must match the repo and its `euc` must match the repo's first commit. With only one side the app stays unclaimed. So nobody can claim your repo, and nobody can pin their repo on you.
- The store shows the publisher's name and photo (from kind 0). Tapping the name lists every app that npub has published. Unclaimed apps show "GitHub: *owner*".
- Downloads still come from GitHub, at the commit the checker passed.

## Native bridge additions

These go in [NATIVE_BRIDGE.md](NATIVE_BRIDGE.md) once confirmed.

| Method | Returns |
|---|---|
| `identity.info` | `{npub, name, picture, backed_up}` or `{none: true}` |
| `identity.setup` | Opens onboarding natively; returns `{npub}` when done or `{cancelled: true}` |
| `identity.sign` `{event}` | The signed event, or `{denied: true}`. Always goes through the native sheet and biometric/PIN. |
| `identity.nip44_encrypt` `{pubkey, plaintext}` | `{ciphertext}`. Used to seal friend requests. The sheet shows the inner event being sealed and to whom. |
| `identity.nip44_decrypt` `{pubkey, ciphertext}` | `{plaintext}`. Used for gift wraps addressed to the owner `npub`. The sheet says "Open a sealed message from *name*". |

No method returns or accepts the private key. Only the native onboarding and import screens ever handle it.

## Build order

1. **Wizard ID in `ai.wizards.os`** (Archimedes builds, Jan reviews):
   - create or import a key;
   - back it up to the password manager and read it back;
   - publish the profile;
   - Settings → Wizard ID;
   - the three bridge methods.

   Builds and emulator QA run on Thales.
2. **Signed app publishing:**
   - `wizard publish` (Agent Service) posts the announcement after approval on the phone (Archimedes);
   - the index and `wam` apply the two-sided publisher rule and fill `publisher_npub` (Miguel);
   - the store shows publisher profiles and the tap-through list (James + Archimedes).
3. **Wizard key and attestation**, desktop requests routed to the phone, NIP-46 for outside apps, and the signed service-restart canary.

## Tests before release

- A wrong or missing biometric produces no signature. Every returned signature verifies.
- After backup and a fresh install, restore gives the same `npub`.
- A bridge call can't get the key, and can't get a signature without the native sheet.
- The sheet's sentence comes from the event's kind and content, never from requester text.
- A two-sided claim lists the app under the publisher. A one-sided claim stays unclaimed, whichever side is missing.
