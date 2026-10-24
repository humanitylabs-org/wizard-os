"""Dry plans must really select the candidate without expanding owner-shell variables early."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys


def candidate_plan(tmp_path):
    script = Path(__file__).with_name("update_reboot.py")
    p = subprocess.run([sys.executable, str(script), "dry-run", "q2", str(tmp_path / "evidence"),
                        str(tmp_path / "lima"), "l4-retry-plan", "0.3.32", "0.3.33"],
                       env={**os.environ, "WAM_CANDIDATE_TGZ": str(tmp_path / "candidate.tgz"),
                            "WAM_CANDIDATE_APPLY": "1", "WAM_CANDIDATE_COMMIT": "a" * 40},
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    plan = json.loads(p.stdout)
    assert plan["error"] is None, plan["error"]
    return plan, {s["step"]: s for s in plan["plan"]}


def python_code(step):
    outer = shlex.split(step["argv"][-1])
    lexer = shlex.shlex(outer[-1], posix=True, punctuation_chars=';')
    lexer.whitespace_split = True
    inner = list(lexer)
    return inner[inner.index("-c") + 1]


def test_candidate_source_manifest_changes_only_wam_and_records_exception(tmp_path):
    plan, steps = candidate_plan(tmp_path)
    assert plan["release_exact"] is False
    assert plan["candidate_source_commit"] == "a" * 40
    d = tmp_path / ".cache/wam-update-candidate"
    d.mkdir(parents=True)
    original = {"version": "0.3.33", "components": {"wizard-app-manager": {"commit": "b" * 40},
                "wizard-agent-service": {"commit": "c" * 40}}, "images": {"agent": "immutable-digest"}}
    (d / "original-release.json").write_text(json.dumps(original))
    code = python_code(steps["candidate-source-stage"])
    compile(code, "candidate-source-stage", "exec")
    p = subprocess.run([sys.executable, "-c", code], env={**os.environ, "HOME": str(tmp_path)},
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    candidate = json.loads((d / "releases/0.3.33.json").read_text())
    assert candidate["components"]["wizard-app-manager"]["commit"] == "a" * 40
    candidate["components"]["wizard-app-manager"]["commit"] = "b" * 40
    assert candidate == original
    assert json.loads((d / "candidate-exception.json").read_text())["source_exception"]["ok"] is False
    assert (d / "releases/latest").read_text().strip() == "0.3.33"
    assert "WIZARD_RELEASE_BASE=file://" in steps["update-reapply"]["argv"][-1]
    for name in ("original-release-readback", "verified-final-receipt"):
        compile(python_code(steps[name]), name, "exec")
    assert 'image wizard-agent-service' in python_code(steps["verified-final-receipt"])


def test_candidate_q2_plan(tmp_path):
    script = Path(__file__).with_name("update_reboot.py")
    evidence = tmp_path / "evidence"
    p = subprocess.run([sys.executable, str(script), "dry-run", "q2", str(evidence), str(tmp_path / "lima"),
                        "l4-retry-plan", "0.3.32", "0.3.33"],
                       env={**os.environ, "WAM_CANDIDATE_TGZ": str(tmp_path / "candidate.tgz"),
                            "WAM_CANDIDATE_APPLY": "1"}, capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    plan = json.loads(p.stdout)
    assert plan["error"] is None, plan["error"]
    steps = {s["step"]: s for s in plan["plan"]}
    assert steps["candidate-activation-copy"]["argv"][1] == "copy"
    assert "wam-update-candidate/bin" in steps["update-apply"]["argv"][-1]
    assert "sudo -u wizard -H bash -c" in steps["raw-after-reboot"]["argv"][-1]
    assert "sudo -iu wizard bash" not in steps["raw-after-reboot"]["argv"][-1]
    assert '[ -f "$p" ]' in steps["raw-after-reboot"]["argv"][-1]
    assert "verified-final-receipt" in steps
    for step in plan["plan"]:
        argv = step.get("argv", [])
        if "bash" in argv and "-lc" in argv:
            syntax = subprocess.run(["bash", "-n", "-c", argv[-1]], capture_output=True, text=True)
            assert syntax.returncode == 0, (step["step"], syntax.stderr)
    # Prove that the generated wait is executable Python, not merely shell-shaped text.
    outer = shlex.split(steps["mid-update-wait"]["argv"][-1])
    inner = shlex.split(outer[-1])
    code = inner[inner.index("-c") + 1]
    compile(code, "generated-mid-update-wait", "exec")
