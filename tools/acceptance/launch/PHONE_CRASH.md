# Phone disappearance: runtime evidence and GPU contrast

**EXTEND** the existing phone harness, transport, PNG masker, Serve fixture and
inherited heavy-worker lease. `phone_runtime.py` is shared runtime/evidence code;
`phone_crash_diag.py` is a separate diagnostic, not a pairing substitute.
No production APK, Wizard server, owner box, SDK or global network settings change.

## Established facts and limits

The failing Linux phone run loaded roughly 2 MB through the successful TLS relay,
then failure-time ADB probes found no owned device. The emulator log ended at
boot completion without a fatal line; host kernel inspection found no OOM or
segfault. Earlier receipts discarded the original exception and process status.
**Those artifacts cannot establish whether QEMU exited, ADB disconnected, a UI
command timed out, or Android/WebView crashed. A GPU crash is still a hypothesis.**
Guest low-memory kills also differ from a host OOM: they appear in logcat, while a
host SIGKILL only identifies the signal, not its issuer. Compare the new numeric
host/emulator memory snapshots and host kernel/cgroup records before attributing
SIGKILL to OOM. Do not infer an AVD's actual RAM from the Pixel 7's retail RAM.

## Source-backed Linux candidate (inspected 1 November 2026)

The installed emulator's **37.2.12** `-help-all` explicitly supports
`-logcat-output <file>`, and `-help-gpu` lists `auto`, `host`, `software`,
`lavapipe`, `swiftshader`, and `swangle`. These are cheap help probes, not boots.

[Google's graphics documentation](https://developer.android.com/studio/run/emulator-acceleration#command-gpu)
marks **guest, swiftshader_indirect and swangle_indirect deprecated since 36.4.9**:

| Mode | Decision for a Linux host without a GPU |
| --- | --- |
| `swiftshader_indirect` | Old baseline, still available as an explicit contrast/override. |
| `swangle_indirect` | Also deprecated; not a useful modernization. |
| `guest` | Deprecated, not the Linux default. |
| `host` | Requires a known-good host graphics stack; no physical GPU here. Forcing Mesa via environment would change another variable. |
| `lavapipe` | Supported Mesa software alternative; explicit option, not yet tested here. |
| `swiftshader` | Supported software GLES/Vulkan; explicit option. |
| `software` | Supported automatic software-backend choice, but less reproducible across SDK updates. |
| `swangle` | Supported ANGLE-over-SwiftShader GLES with SwiftShader Vulkan. Selected Linux candidate to change the GLES translation path without requiring a GPU. |

**macOS retains its prior `swiftshader_indirect` default.** No claim that ANGLE
fixes this particular failure is justified before the queued comparison.
Do not use `-gpu host` and assume that `-no-window` makes it software rendering.

[37.2.13 release notes](https://developer.android.com/studio/releases/emulator#37-2-13)
report issue **568480829**, a host OpenGL ES emulation memory leak when guest
apps/processes exit. This makes memory worth recording on 37.2.12; it is **not**
a proven explanation for a disappearance after one load. This change does not
upgrade the shared SDK or claim a known WebView-specific 37.2.12 crash fix.

The disposable API35 AVD pins `hw.ramSize=3072` and `vm.heapSize=512` MiB, rather
than depending on whichever defaults avdmanager/device profiles happen to emit.
This is a bounded, configurable working budget, not an established OOM cure.
The Wizard guest VM still consumes host memory in the full acceptance run; the
standalone diagnostic deliberately omits it, so a standalone pass cannot rule
out pressure specific to the combined run. API37's documented 4 GiB minimum is
not applicable to this API35 image.

Private phone config options:

```json
{"gpu_mode":"swangle","ram_mb":3072,"heap_mb":512}
```

Modes are allowlisted. RAM must be 2048–8192 MiB; heap 128–1024 MiB and at most
half the RAM. Only each disposable AVD's config.ini changes; duplicate emitted
keys are replaced. Both acceptance and the crash diagnostic use these options.

## Evidence that survives device death

Failure receipts retain a fixed exception class/message enum, and for subprocess
failures only sanitized **argv[1:3]**, never argv/stdout/stderr/exception text.
Unknown messages become `unclassified`. Examples: `phone_emulator_exited`,
`phone_ui_timeout`, `TimeoutExpired`, `CalledProcessError`.

Liveness is frozen **before** potentially slow diagnostics, HTTPS relay teardown
or emulator cleanup: return code and signal name, ADB owned-device state/rc,
seconds since emulator start, boot-completed observation and Connect invocation,
and Linux MemAvailable/SwapFree/SwapTotal/emulator VmRSS/VmPeak KiB. No serial,
process name, owner hostname or address appears in these projections.

The emulator receives `-logcat-output <evidence>/private-logcat.pipe -logcat *:V`.
The 0600 FIFO drains into **private-logcat.txt** and, on rotation,
**private-logcat.previous.txt** (0600, at most 8 MiB each). Thus the latest raw
logcat survives loss of ADB without permitting an unbounded log file. It is not
uploaded or suitable for sharing: it can contain private data. Rotation discards
older raw bytes, while counters cover the entire stream. The FIFO disappears on
exit. `logcat-summary.json` contains only counts/byte totals/retention and writer
status, never log lines or URLs. Categories: FATAL EXCEPTION, Fatal signal, ANR,
Chromium/WebView crashes, GPU/EGL/SwiftShader/Vulkan errors, lowmemorykiller kills.
GPU warnings are evidence, not automatically an emulator-crash verdict.

A masked checkpoint is attempted immediately before Connect and at Connect +5s.
The native address screenshot uses the existing sensitive-label masker. Dynamic
WebView/canvas screenshots fail closed to a full mask (also the hold-end image),
rather than guessing pixels safe. A dead device may prevent capture; the bounded
checkpoint status is retained and cannot replace the primary failure.

Owned emulator cleanup escalates ADB kill → wait → terminate → kill → wait, even
if ADB is dead. A cleanup failure is separately recorded, not confused with the
pre-cleanup exit status. SIGKILL or loss of the worker cannot guarantee teardown.

## Short diagnostic, ready for the heavy queue

```
phone_crash_diag.py --phone-config <private-config> --root <new-work-child> \
  --gpu-modes swiftshader_indirect swangle
```

Run only with the shared worker, `WIZARD_WORK_ROOT`, and its inherited lease.
It validates the same lock FD/device/inode as phone acceptance, holds that lease
across both modes, and writes a bounded private verdict. Execution has a 1050s
alarm plus bounded cleanup (designed for <20 min); the queue hard timeout is
1800s. No Wizard VM, model call or owner credential is needed.

Each mode creates a fresh identical Pixel 7/API35 AVD, verifies the published
APK against its feed/hash/signer, installs it and opens **ConnectActivity**, not
the APK's built-in migration origin. Connect uses the real APK probe, real HTTPS
certificate, scoped 9453 Serve handler, and the same Android global-proxy/TLS
relay as acceptance. The page explicitly identifies itself as **synthetic**:
1200 animated DOM tiles plus bounded 2D canvas/WebGL drawing. Its title/core
marker intentionally satisfies the native read-only probe to exercise the
Connect → WebView path; it is not a fake Wizard acceptance receipt.

Require its post-animation ready marker in the APK UI, hold for **120 seconds**,
sample emulator/ADB/activity liveness, and require the marker still visible at
the end plus bidirectional TLS relay bytes and persistent logcat reception.
Screenshots and raw logcat remain private. Fatal/ANR/Chromium crash counters
make that mode fail; GPU errors and lowmemorykiller kills remain visible counts.
The overall comparison fails if either mode fails: inspect each per-mode verdict
to decide which mode, if any, survived. Never promote a comparison pass to an
actual shell/second-owner pairing pass.

Only free Serve **9453** can be added; pre-existing handlers are compared before
setup and after cleanup. The existing 2283 handler is never changed. Emulator,
AVD, relay and Serve unwind before releasing the lease, including SIGTERM and
deadline exceptions. Do not start mode two if owned emulator cleanup fails.

## Cheap regressions (no boots)

```
python3 -m unittest tools.tests.test_phone_runtime \
  tools.tests.test_launch_onboarding tools.tests.test_phone_net_diag
```

Tests exercise a real FIFO writer/reader/rotation, private permissions, sanitized
exception payloads, SIGSEGV vs UI-command timeout at address-pairing, dead-device
snapshots before cleanup, GPU defaults/overrides, duplicate RAM keys, shared-lease
ordering, Serve teardown ordering, diagnostic boot death, and stopping before
a second mode on cleanup failure/deadline. They do not execute the crash
comparison: booting/queue submission must be separately authorized.
