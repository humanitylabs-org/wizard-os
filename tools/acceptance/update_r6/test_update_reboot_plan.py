"""Dry plans must really select the candidate without expanding owner-shell variables early."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys


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
