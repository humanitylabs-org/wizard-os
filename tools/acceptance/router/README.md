# Connection Router acceptance (four box states)

Proves what a Wizard owner sees and what an app gets from the Connection Router when the box has Claude only,
ChatGPT only, both, or neither connected. It answers the "Connection Router" acceptance item in
`docs/WORK_OUTSTANDING.md`.

What is real: the published Router image (pinned by digest), Wisdom built from its pinned commit with its own
`wizard.md` and its own adopter code (`model_router.py`), the Store page and Store feed bridge from wizard-ux, and a
fresh Ubuntu VM per run. What is fake: the two AI connection apps. They are the Router's own contract fixture
(`tests/fake_provider.py`) serving the real model lists the shipped Claude and ChatGPT apps publish, so no account,
token or paid inference is involved. `fixture/router-fixture` is a no-backend test app whose three `swap: ask`
features exercise a match, an owner choice and provider-order pre-selection.

Per state the run records: owner needs and app-scoped needs (each app with its own grant), owner routes, one
`/v1/models/<feature>/run` per feature, the requests each fake provider received, phone-size screenshots of the
Store install sheet, and Router/Wisdom logs. `check.py` judges the evidence against the expectations in
`spec/CONNECTION_ROUTER.md` and writes `checks.json`.

Run (Telos stages, Thales executes through the wizard-heavy queue):

    tools/acceptance/router/stage.sh <wizard-os> <wizard-app-store> <wizard-ux> <wisdom> <wizard-agent-service>
    # then on Thales: /Volumes/ThalesMedia/wizard-os/router-acceptance/harness/<sha>/run.sh

Evidence lands in `/Volumes/ThalesMedia/wizard-os/router-acceptance/runs/<run id>/` with a `RECEIPT.md`.
