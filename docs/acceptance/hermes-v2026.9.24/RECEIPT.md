# Hermes stable-candidate test — PASS

- Candidate: `nousresearch/hermes-agent@sha256:fca358f12efd65bfaaca05884166f15c0e2788375ca30d77061ac1ebc96452b7` (Hermes Agent v0.21.5 (2026.9.24) · upstream f97608f1)
- Updated from and rolled back to: `nousresearch/hermes-agent@sha256:fca358f12efd65bfaaca05884166f15c0e2788375ca30d77061ac1ebc96452b7` (Hermes Agent v0.21.5 (2026.9.24) · upstream f97608f1)
- Agent Service: `ghcr.io/humanitylabs-org/wizard-agent-service:pinned-cb92d01c5656`
- Shell (Markdown renderer): `ghcr.io/humanitylabs-org/wizard-ux:pinned-c60920e7da9f`
- Fresh VM `hs-1022t010058z` on `thales.local`, 2026-10-22T01:02:13Z → 2026-10-22T01:05:40Z
- Model: deterministic fake (fake_model.py), no accounts or paid inference

- PASS — A thread sends and receives: run completed, output 'ECHO t1'; thread has 2 messages read back through the Agent Service
- PASS — A helper's result comes back to the thread that started it: background helper; the Agent Service's follow-through started the next turn; helper's model call seen: True; helper result stored in the parent thread: True; parent's reply using it: 'PARENT-SAW CHILD-RESULT h1'; helper sessions recorded with this thread as parent: 1
- PASS — Markdown replies render: reply stored verbatim: True; rendered by the shell's chat-kit.js: heading yes, bold yes, list yes, code block yes, table yes, link yes
- PASS — A long conversation keeps its reasoning after compaction: Hermes compacted 1 time(s); on the recall turn the early facts reached the model only through the summary: ['alpha', 'bravo', 'charlie'] (still verbatim: none); the model recalled ['alpha', 'bravo', 'charlie']
- PASS — The database is intact before and after a restart: integrity before ok, after ok; sessions 6→6, messages 61→61; the first thread reads back identically and takes a new turn ('ECHO r1')
- PASS — A scheduled job fires: job a886a6a258b1 scheduled 'every 1m'; its model call arrived 119s after creation
- PASS — An update followed by a rollback both work, with history intact: update Hermes Agent v0.21.5 (2026.9.24) · upstream f97608f1 → Hermes Agent v0.21.5 (2026.9.24) · upstream f97608f1: ok (seed thread from before the update read back identically: True); rollback → Hermes Agent v0.21.5 (2026.9.24) · upstream f97608f1: ok (integrity ok; seed thread and post-update thread read back identically; new turn 'ECHO rb1') — from and to are the same image, so this exercises the recreate/backup path only
- Observation — Thread history after compaction: the compaction test thread has 46 rows in state.db (3 of the 3 early fact turns); the Agent Service returns 8 messages to the shell (include_compacted=true, view=wizard), WITHOUT the compacted early turns
