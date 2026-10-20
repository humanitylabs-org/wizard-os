#!/usr/bin/env python3
"""Hold the shared Thales worker lease (BSD flock, same family as the Android runner) around one command."""
import fcntl, subprocess, sys, time
f = open('/Volumes/ThalesMedia/AndroidBuilds/worker.lock', 'a')
t0 = time.time()
while True:
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB); break
    except OSError:
        if time.time() - t0 > 3600: print('LEASE-TIMEOUT', flush=True); sys.exit(75)
        time.sleep(10)
print('LEASE-ACQUIRED after %ds' % (time.time() - t0), flush=True)
rc = subprocess.call(sys.argv[1:])
print('LEASE-RELEASED rc=%d' % rc, flush=True)
sys.exit(rc)
