# Browser trust: apps must not act as the owner

Proposal for review by Jan (native Android/Mac) and Miguel (WAM, Store, grants). Execution by Oscar after review. Not permission to enable or release anything; the flag stays default-off.

- [REVIEW-BRIEF.md](REVIEW-BRIEF.md): the problem, what happens if we leave it, what exists, the proposed solution, work breakdown, questions, how Oscar executes.
- [ADAPTER-SKETCH.md](ADAPTER-SKETCH.md): proposed message and operation contracts for the missing adapters.
- [APP-CENSUS.md](APP-CENSUS.md): static inventory of every app against the sealed-frame model, with effort bounds. Source reading only, not runtime proof.

Tracking issue: #133. Draft implementation PRs: wizard-ux #327, wizard-agent-service #100, wizard-app-manager #168, wizard-os #163.
- [SPEC-CARD1.md](SPEC-CARD1.md): card 1 (#384) decision register for the review questions, architecture disposition, WAM-backed admission contract, Notifications operation schemas, storage scope and legacy ownership. Draft for Miguel's review.
