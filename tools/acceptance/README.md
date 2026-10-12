# Two-box acceptance (wizard-os#29)

`two_box.sh status` lists every acceptance step, what it proves and which candidate gates it. `two_box.sh <step> <vm>`
runs a scripted step inside a Lima VM on Thales (VMs under `LIMA_HOME=/Volumes/ThalesMedia/lima-coord`; the
internal disk is near full). Heavy work takes `/Volumes/ThalesMedia/AndroidBuilds/worker.lock`.

Box A = Ubuntu 24.04 + stock Hermes from the public installer + owner sentinels (the cohort's shape).
Box B = fresh Ubuntu 24.04. Steps never touch a real user's box. Per-person cohort preflights come after a full pass
and only with James's authorization.

Scripted today: `baseline`, `install`/`pins`, `doctor`, `unlink`. The rest are named with their gate and get scripted
as each candidate lands, so the first full run is mechanical.
