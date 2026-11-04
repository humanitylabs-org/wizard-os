# Sign-in safety audit — leading gaps

**1 Nov 2026 · read-only baseline, corrected for account ownership.** This shareable summary follows the [sign-in safety decision](DECISIONS.md#1-nov-2026--james-sign-in-safety-for-every-app-and-connector). Installation evidence stays private; no credentials, account identities, personal paths or browser histories belong here.

## Gap 1 — retained profiles need ownership evidence

Retained site state proves neither active login nor account ownership. A provider domain or profile name cannot establish a personal-policy violation.

**Fix · medium:** classify from explicit account/session ownership records first. Verified agent-operated accounts may retain isolated persistent sessions. Personal setup requires owner-only entry with inspection paused, then provider logout, session stop and verified local deletion; record these as separate outcomes. With separate approval, retire only verified obsolete personal sessions after checking active task/handoff ownership. Preserve unknown/mixed profiles pending classification and explicit personal exceptions.

## Gap 2 — instructions must distinguish account classes

Autonomous login is not inherently a violation. Verified agent-operated accounts may use approved model-blind vault login and agent-controlled verification routes. Working agent-owned helpers must not be disabled merely for being automated.

**Fix · medium:** remove guidance that would automate personal-account passwords or codes. Personal accounts require paused owner takeover; an approved one-time intake link is only for owner-supplied secrets a non-browser consumer needs, never a personal provider password or code. Both classes keep secret values out of model context, browser dumps, screenshots, logs and exceptions, and report allowlisted status only. Unknown ownership follows personal rules until verified.

## Gap 3 — credential custody and authority

Reviewed source includes plaintext credential-bearing JSON and native CLI credential files. Host auth/environment stores remain tool-accessible. Source behavior is not proof of actual deployed storage; deployment provenance and service-UID access must be checked separately. File mode 0600 is not encryption or isolation from same-user model tools or the host administrator.

**Fix · large overall, medium per store:** migrate canonical custody to an approved encrypted vault/broker with separately controlled keys, deliver narrow runtime grants to the consumer, prove a real canary and rollback, then, with separate approval, remove plaintext duplicates. Native CLI-required files may need controlled read-only per-process delivery rather than incompatible encryption. Never put a key beside an encrypted file and call the host/model boundary solved. Read-only defaults do not cancel existing authorised write permissions, including Calendar writes; scope reduction or revocation requires specific approval. Master-password/canonical-custody changes require a preannounced migration plan.

## What this does not claim

The baseline audit changed no sign-ins, grants or profiles. Its earlier blanket condemnation of autonomous login and write scopes is superseded by this ownership distinction. Private-agent, message and recording data remain excluded. Local permission tightening, where separately authorised and verified, does not establish encrypted custody or completed migration. This docs PR is not implementation or release acceptance; owner-classification, real consumer canaries and teardown receipts remain required.
