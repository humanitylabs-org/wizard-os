---
wizard: 0.2
id: router-fixture
name: Router Fixture
type: view
category: tools
version: 0.1.0
summary: Acceptance fixture for the Connection Router. Three swap-ask features, no backend.
license: MIT
requires:
  models:
    summarize:
      label: Summarize a note
      tier: standard
      tested_on: claude-sonnet-5
      swap: ask
      abilities: [text, streaming]
    draft:
      label: Draft a reply
      tier: standard
      tested_on: gpt-6.1-sol
      swap: ask
      abilities: [text, streaming]
    classify:
      label: Tag a note
      tier: fast
      tested_on: fixture-unlisted-fast-1
      swap: ask
      abilities: [text]
---

# Router Fixture

Not a real app. It declares one feature tested on a Claude model, one tested on a ChatGPT model, and one tested on a
model no installed provider offers, all `swap: ask`, so each acceptance state shows a match, an owner choice, and the
provider-order pre-selection.
