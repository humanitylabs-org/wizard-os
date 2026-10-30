## Fresh install of 0.3.89 on a disposable KVM guest

Companion to [promote-0.3.89.md](promote-0.3.89.md) (installed upgrade 0.3.88 → 0.3.89, PASSED). 0.3.89 changes the
fresh-install path (App Manager #357: a fresh link installs the wizard-os plugin so ChatGPT sign-in works; ChatGPT
0.2.12 / Claude 0.2.14), so a clean-box install was also run, as wizard-app-manager AGENTS.md asks for install-path
changes (raised by Codex on wizard-app-manager#361).

Run: `kvm_upgrade.py run --from 0.3.89 --to 0.3.89 --keep` (rundir `20261030T023947Z-0.3.89-to-0.3.89`). The rig's
"install" phase is a fresh install of the named release on a clean guest with stock root Hermes, via the public
command (`curl -fsSL https://aiwizards.com/os.sh | WIZARD_RELEASE=0.3.89 WIZARD_STRICT=1 bash -s start`, agent-run).

**Fresh install 0.3.89: PASSED.**

- Install done in 551 s; release.json 0.3.89 `pinned`, install_rc 0, 27 checks, 0 failed (App Manager 706012e4,
  image ae8a65da…, Agent Service e02d50a4…, Wizard UX 2463c11b…, every default app on its pinned source commit).
- install-outcome.json: `ok`, failed [], degraded [].
- Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 0.
- Engines: wizard-chatgpt-engine sha256:abe83ddb… (0.2.12), wizard-claude-engine sha256:e839af7c… (0.2.14), both healthy.
- #357 on the guest: `/root/.hermes/plugins/wizard-os` present, `plugins.enabled` lists `wizard-os`, linked.json
  records `plugin_installed: true` and the `plugins.enabled` edit (so `wizard unlink` reverses it).
- Not exercised: a real ChatGPT/Claude sign-in (needs a live account); #357 was verified live on a fresh 0.3.86
  demo box in its PR (ChatGPT `actions.add: true`, device-code sign-in shown).

**Same-version rerun (second phase): not a release result.** Re-running the same public command on the box already at
0.3.89 failed in 63 s with the known runtipi container-name `Conflict` flake; that rerun installed 0.3.88 (the public
stable mirror at that moment, before wizard-app-manager#361 merged) rather than the requested 0.3.89, so the rig
reported FAILED for the after-state. This phase is outside the promotion test; the rerun not honouring `WIZARD_RELEASE`
on a same-version rerun is noted for follow-up.
