# Sign-in safety audit — leading gaps

**1 Nov 2026 · read-only review.** This is the shareable summary of the three leading gaps against the [sign-in safety decision](DECISIONS.md#1-nov-2026--james-sign-in-safety-for-every-app-and-connector). The detailed per-item evidence stays on the audited installation; no credentials, account identities, private content, personal paths or browser histories belong in this repository.

## Gap 1 — retained shared browsers

Setup/browser profiles retain state across providers rather than proving a clean throwaway lifecycle. Retained site state does not prove an active sign-in or identify the account owner.

**Fix · medium:** make setup use a fresh profile; the owner completes sign-in privately with inspection paused. Afterwards sign out, stop the browser, remove the profile and verify each step. Do not delete existing live profiles without the owner's approval.

## Gap 2 — automated sign-in and conflicting instructions

Some existing helpers and agent instructions still automate passwords or two-step codes, preserve provider profiles, or collect signed-in page text/screenshots. Keeping a password out of a transcript does not make agent entry compliant.

**Fix · medium:** replace those paths with paused owner takeover or one-time secret intake, reconcile conflicting setup guidance, and return allowlisted status codes only.

## Gap 3 — credential custody and scopes

Reviewed connection implementations include credential-bearing JSON files without app-layer encryption. Host-level credential/environment stores also remain outside the owning app boundary, and legacy Google grants include write permissions beyond the read-only default. File permissions are not encryption.

**Fix · large overall, medium per store:** keep credentials encrypted in the owning app with separated keys; give agents narrow local grants, not provider credentials. Have the owner approve reduced scopes and any migration/revocation. Recheck the pinned release without reading private data.

## What this does not claim

The audit did not alter sign-ins, accounts, grants or retained profiles. Private-agent and recording/message data were excluded; unknowns remain unknown. This documentation change records the rule and priorities, not implementation or release acceptance. Release checks still need to assert each of the four rules.
