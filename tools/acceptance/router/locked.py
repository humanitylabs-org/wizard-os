#!/usr/bin/env python3
"""Run run.sh under Thales' shared heavy-work lock (the same flock the wizard-heavy queue and Android QA take).

Use this when the queue cannot admit the caller (for example a Kanban worker with no Wizard chat run to resume).
Waits for the lock, records when it was granted, then runs the acceptance and releases the lock on exit.
"""
import fcntl
import os
import subprocess
import sys
import time

LOCK = "/Volumes/ThalesMedia/AndroidBuilds/worker.lock"
here = os.path.dirname(os.path.abspath(__file__))
run_id = os.environ.setdefault("RUN_ID", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
print(f"waiting for {LOCK} (run {run_id})", flush=True)
t0 = time.time()
with open(LOCK, "a") as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    print(f"lock granted after {time.time() - t0:.0f}s", flush=True)
    sys.exit(subprocess.call(["/bin/bash", os.path.join(here, "run.sh")]))
