# Phone transport evidence and short queued proof

## What failed, and what we can establish without another boot

The previous capture command used one `ValueError('diagnostic_unavailable')`
for **nonzero ADB exit, unexpected stdout type, and excessive output**. It then
persisted only the exception class. A missing/offline owned serial therefore
produced the same three `ValueError` fields as unrelated probe failures. Also,
a sensitive UI label without bounds raised ValueError rather than retaining
redacted labels and masking the entire screenshot. These paths are reproduced
by regression tests, including real subprocess execution with a fixture ADB.
The old evidence discarded return codes, so it cannot establish which branch
occurred on the worker. Do not claim that a native API35 dump failure, proxy
bypass, or device loss has already been proven.

Capture now passes the owned ADB executable, explicit serial and emulator env
unchanged, records fixed error classes, rc and stdout byte counts, probes
`get-state`, retries API35's compressed UI dump separately, and reads that new
XML using `exec-out cat`. Screenshot, activity, logcat and Serve probes remain
independent. Missing sensitive bounds retain redacted labels and force a fully
black screenshot. An absent app pid does not prevent Chromium error capture.
No stderr, raw logcat, URL, query string, payload, IP or tailnet name is retained.
Activity evidence projects component/lifecycle lines only. Network errors are
projected onto error enums and the host class `box`/`other`, capped at 80 rows.
The relay's locked counters retain accepted/allowed/denied, upstream ok/failed,
and payload byte totals in each direction, never destinations or payloads.

DNS formerly accepted *anything except* the words `unknown host`, including
ADB's `device not found`. It now requires ping's resolved-address header.
Successful DNS is not a proxy or TCP reachability proof.

## Why Android's global HTTP proxy

The installed emulator's `-help-http-proxy` promises redirection of all TCP;
`-help-feature` documents `-feature -NAME`. A cheap version/help/acceleration
inspection is permitted, but not a boot outside the heavy queue.

It is **not correct to infer that VirtioWifi automatically disables proxying**:
public source carries a proxy option into netsim, and netsim supports it:

- [QEMU netsim registration](https://android.googlesource.com/platform/external/qemu/+/cf0f40a0aad1aa3fca68f2f89372525c8d28ca68/android-qemu2-glue/netsim/qemu-packet-stream-agent-impl.cpp#254)
  puts `http_proxy` in `NetsimdOptions`.
- [netsim arguments](https://android.googlesource.com/platform/tools/netsim/+/aaebb6787db0840a22d417fae5c97655946edbf4/rust/daemon/src/args.rs#79)
  expose `--http-proxy`, marked work in progress.
- [netsim WiFi libslirp](https://android.googlesource.com/platform/tools/netsim/+/aaebb6787db0840a22d417fae5c97655946edbf4/rust/daemon/src/wifi/libslirp.rs#27)
  builds the HTTP proxy manager only when its configuration contains a proxy.
- [Android proxy documentation](https://developer.android.com/studio/run/emulator-networking-proxy)
  distinguishes emulator-level TCP proxying from Android's HTTP-stack proxy.

These public revisions explain supported plumbing, not an exact binary/source
identity for the installed 37.2.12 build, nor the configuration of an already
running netsim daemon. They do not prove this worker's previous packets used the
requested relay. No speculative `-no-netsim` or legacy WiFi flag is needed.

Instead the disposable Linux AVD sets and reads back
`settings put global http_proxy 10.0.2.2:<relay-port>` **after boot**. Android's
HTTP/WebView stack explicitly connects to the allowlisted relay through the
emulator's host-loopback alias. The APK still uses the real tailnet HTTPS name
and validates its real certificate; the relay only carries opaque TLS. We omit
emulator `-http-proxy` and remove its implicit lower-case environment setting to
avoid double proxying. macOS keeps its previous direct transport and env.
This is the selected candidate, **not a claim of an executed emulator pass**.

## Queue the standalone network diagnostic before the long phone run

`phone_net_diag.py --phone-config <worker-config> --root <new-private-work-child>`
(default and only permitted Serve port: **9453**). The wrapper must set
`WIZARD_WORK_ROOT`; the root must be a new directory below it. The script:

1. Takes `phone.worker_lock`, including exact inherited
   `WIZARD_HEAVY_LOCK_FD` device/inode validation, and refuses an existing serial.
2. Starts a loopback tiny HTTP **network fixture**, not a Wizard or pairing mock.
   Discovers its own tailnet name at runtime and adds only the free Serve 9453
   handler. It refuses an occupied port and compares all prior TCP/Web handlers
   after setup and after cleanup. It never resets Serve or touches port 2283.
3. Creates the same disposable `launch_phone`/Pixel 7/API35 native-architecture
   AVD and uses the same `emulator_argv` and `emulator_network` as phone acceptance.
4. Records a direct toybox nc contrast probe (rc only; not an HTTPS verdict), then
   opens the real tailnet HTTPS origin through Android's default VIEW browser.
   Dismisses only known first-run Chrome account-free controls. Requires the
   unique fixture page text in Android UI **and** an actual HTTP fixture request
   **and** CONNECT/upstream/bidirectional relay byte counters. No TLS bypass.
5. Exercises real diagnostics even on success. All six retained artifacts must
   save for its diagnostics check. Writes private `verdict.json`; stdout contains
   only the same bounded verdict. This is explicitly not a pairing test.
6. Stops its own emulator, deletes its disposable AVD, removes only 9453, verifies
   other handlers unchanged, and releases the inherited lease last. SIGTERM
   unwinds cleanup. SIGKILL/host loss cannot guarantee cleanup; inspect before
   retrying. Normal budgets are well under 20 minutes; queue timeout is 1800s.

A default HTTPS VIEW browser is required by this Google APIs fixture. A missing
browser or changed first-run UI fails closed at `https-page`, with diagnostics;
it never substitutes a host fetch or reports a synthetic success. The worker
config should use a free even emulator console port in the documented range
(5554–5584); out-of-range ports cause an ADB warning. Do not kill other emulators.
Keep the full pairing acceptance queued separately and require its actual pass.

## Cheap tests (no Android boot)

```sh
python3 -m unittest tools/tests/test_launch_onboarding.py tools/tests/test_phone_net_diag.py
```

These cover the proxy setting/readback, unchanged Darwin branch, real localhost
CONNECT forwarding/denial and counters, diagnostic subprocess/serial/env,
nonzero/oversize/timeout failures, missing UI bounds, logcat privacy, Serve
preservation on exception, verdict persistence, and forced emulator cleanup.
They do not replace the queued network diagnostic or the native APK pairing run.
