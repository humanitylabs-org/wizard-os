# Agent identity, split and merge

**Status: Approved by James 24 Oct 2026 (DECISIONS #95).** Agent-facing procedure and future Agents app flow; no split/merge API or UI implementation in this change.

## One agent per identity, skills per task

Start a box with one agent. Split later from use. A role earns an agent only when it needs all three: a different default model/fallback, a narrower tool surface, and its own always-loaded memory whose register conflicts with the main agent's. Otherwise make a skill. Recommend at most three agents; adding a fourth retires or merges one.

Tag memory/facts by area, for example `[area: building]`. A later split becomes a filter rather than a reconstruction.

## Split: propose, approve, apply

1. The owner says “split X out” in chat or the Agents app. Do not create or move state yet.
2. The splitting agent proposes a diff: the new SOUL, always-loaded memory (entries moved, kept, or needed by both), skills to move/copy, a summary of relevant history, model/fallback, tools and permissions. Label copies and source attribution. Explain any private/silo boundary; a private source may publish only exact owner-approved copies under #59.
3. Ask the owner to approve that exact diff. Changed proposals need fresh approval. Full old transcripts stay with the original, readable through Agent History under `other_agents` and its seals.
4. On approval, Agent Service creates the new agent through the existing create API and its container/permissions path. Apply only the approved state. Verify new state before removing moved entries from the original. Each agent writes its own memory/skills/notes; lifecycle coordination does not grant cross-agent write tools.
5. Remove approved moved entries from the original. Put a one-line pointer to the other in both agents. Keep the approved diff and completion checkpoint so a partial failure resumes without duplicate moves. Verify both sides; never silently delete transcripts.

## Merge back

Propose the reverse diff. With owner approval, fold memory/skills into the surviving agent, preserving source attribution and resolving conflicts explicitly. Verify the folded state, add pointers, stop the merged agent's container and archive its home, never delete it. Its threads stay readable through Agent History under the same permissions and seals. Private data never becomes standard through a merge; only exact owner-approved published copies may cross that boundary.
