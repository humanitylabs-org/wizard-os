# Agent templates

**Status: Idea (James, 24 Oct 2026, DECISIONS #98).** Parked for later. Nothing here is scheduled or built. It's recorded so that the Agents shelf, agent packages and the split flow aren't designed in a way that rules it out. Revisit it once real use shows which roles actually need an agent of their own.

## The idea

People pick up Wizard to do something specific: study, think, build, run their life. An agent that arrives already shaped for that job fits it better than a blank one: its personality (`SOUL.md`), a starting set of skills, a model recommendation and a tool preset all come with it. An **agent template** is that shape with nothing personal in it. Installing one creates a fresh agent. It has the template's soul and skills and memory that starts empty.

Example templates, all names provisional:

- **Philosopher / Thinking partner.** Questions positions, steelmans the other side, keeps a ledger of what the owner holds and why. James's `philosopher` agent is the working prototype.
- **Tutor / Study.** Teaches a subject over time: Socratic questioning, drawing answers out, close reading, an end-of-session review, and a learner profile of what the student knows and where they get stuck.
- **Builder.** Plans, implements and verifies software: repo and terminal tools, delivery skills, a stronger model by default.
- **Assistant.** The general personal agent most boxes start with.

Use will show whether these really are separate agents, or skills and spaces inside one agent. The live question is whether a builder needs to be separate from a personal assistant.

## How it fits what exists

- **Template vs agent package.** An agent package ([AGENT_STATE.md](AGENT_STATE.md), "Packages") is one agent's whole folder, with its memory, history and sign-ins. It's for backups and moving a box. A template is the shareable subset of that folder: soul, skills, settings recommendations and an empty memory layout. It never carries memory entries, sessions, notes, `.env`, credentials or sign-ins.
- **Template vs a `type: agent` app.** In [WIZARD_MD.md](WIZARD_MD.md), a `type: agent` app ships a runnable harness (compose files plus MCP). A template ships no runtime. It installs onto a harness the box already runs, through the Agent Service's existing create API (preset, model, permissions), so a new agent costs no extra download and follows the box's harness updates.
- **Splitting, the template-shaped way** ([AGENT_SPLIT.md](AGENT_SPLIT.md), #95). A split proposal can start from a template's soul and skills instead of writing them from scratch. Publishing a template from an agent you already have is a split diff with every personal item removed, approved by the owner.
- **Privacy.** A template from a private agent is published only as exact copies the owner approves item by item (#59). A template can recommend the Private preset, and installing it still goes through the normal private-agent setup.

## Rough shape (to settle when built)

```text
socrates/
  template.md          # front matter: id, name, summary, harness: [hermes, pi], preset,
                       # recommends: {model, step_up}, tools allowlist, publisher
  SOUL.md              # personality and stance
  skills/<name>/SKILL.md
  memory-layout.md     # empty structure, e.g. learner profile or positions ledger headings
```

It should be published and found the same way as apps and skins, under the publisher's Wizard ID, through lists people choose to follow (#38, #83).

## Choosing one without a setup question

Onboarding doesn't ask what Wizard is for. Instead, the box notices a pattern as it's used (for example, many study sessions on one subject) and the main agent offers once: "want a tutor agent for this?" That offer runs as a split proposal from a template, and the owner approves it under #95. A template can also be installed by hand from the Agents shelf.

## Open questions

- **How many agents?** #95 recommends at most three, and adding a fourth means retiring or merging one. That's advice; the Agent Service doesn't enforce any limit. It exists because each extra agent splits memory and leaves the owner deciding who to ask. James asked on 24 Oct whether this should be a hard limit. This idea assumes it stays advice and that templates install like any other agent.
- How narrow should a template's skills be before they work better as system skills every agent can read?
- Which fields go in `template.md` versus the existing create API's `preset` and `model`?
- Does a template that supports both Hermes and Pi need a separate skill set per harness? Skills are written for one harness's tools (AGENT_STATE §2).
