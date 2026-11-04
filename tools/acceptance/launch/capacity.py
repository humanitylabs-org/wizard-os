"""Host free-space policy for the disposable launch acceptance harness.

Linux's 60 GiB reserve is a conservative coexistence envelope, NOT a measured
peak: 32 GiB for retained Android build/SDK usage (~24.47 GiB observed), 16 GiB
for two ordinary fix increments (largest observed ~7.61 GiB), and a 12 GiB
emergency free floor. Heavy Android/Gradle/emulator/VM jobs are serialized;
retained and out-of-lock runtimes still need room. macOS keeps its old reserve.
Admission assumes one new guest at a time (daily deletes its disposable before
retained work) and a 9 GiB phone scratch allowance. run.py checks only between
commands, not during a long install/phone step; release_gate.py additionally
monitors free space. These budgets are not quotas on other processes, so the
reserve is not guaranteed against concurrent unbounded allocations.
This is harness capacity, not the product's minimum disk requirement.
"""
import platform

GIB = 1 << 30
LINUX_ANDROID_COEXISTENCE_GIB = 32
LINUX_DAILY_FIX_SCRATCH_GIB = 16
LINUX_EMERGENCY_FREE_FLOOR_GIB = 12
MACOS_RESERVE_GIB = 250
METADATA_GIB = 1
PHONE_GIB = 9


def reserve_gib():
    """Keep the legacy reserve outside Linux; native host admission is separate."""
    if platform.system() == 'Linux':
        return (LINUX_ANDROID_COEXISTENCE_GIB + LINUX_DAILY_FIX_SCRATCH_GIB
                + LINUX_EMERGENCY_FREE_FLOOR_GIB)
    return MACOS_RESERVE_GIB


def required_free_gib(disk_gib, phone=False):
    """Admission includes the guest disk, metadata and optional disposable AVD."""
    return reserve_gib() + disk_gib + METADATA_GIB + (PHONE_GIB if phone else 0)
