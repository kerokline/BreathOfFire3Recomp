# Starvation watchdog: false trips and the "atexit" mislabel

**Status:** IN PROGRESS (proposal drafted 2026-09-02; **filed 2026-09-05 as [mstan/psxrecomp#321](https://github.com/mstan/psxrecomp/pull/321)** from fork branch `fix/starvation-watchdog-wrap` `430c93b8` off the `17f49ad3` pin, with the ctest `starvation_watchdog_test` and both verification steps below done — 10 min poller soak with the watchdog enabled, no trip; forced trip labels `exit_origin: starvation_watchdog`. Bump the gitlink and drop the `setx` workaround when it merges)

Two defects in `psxrecomp/runtime/src/starvation_ring.c` and its callers, both
observed on 2026-09-02 and both owned by upstream `mstan/psxrecomp`. The
submodule is read-only here, so this doc holds the patch until it is filed.
Local workaround in force: `PSX_STARVATION_TIMEOUT_US=0` persisted with `setx`
(see `STATUS.md`, *Known issues*).

## Evidence

Run: `build-dbg`, pin `7ab698ca`, launched from the launcher 2026-09-02 15:00:02
with the area poller attached over TCP. Process vanished at 15:01:41.

| Artifact | What it says |
|---|---|
| `build-dbg/psx_last_run_report.json` | `reason: "atexit"`, `exit_origin: "unknown"`, frame 5524. Native stack (addr2line on the -O0 exe): `starvation_watchdog_check` (starvation_ring.c:246) → `psx_atexit_handler` → `psx_crash_trace_dump`. |
| `build-dbg/starvation_dump.jsonl` meta | `last_heartbeat_us: 322798613022`, `now_us: 322798613424` — the heartbeat was **402 µs** old when the dump ran, against a 4 s threshold. |
| `build-dbg/psx_freeze_heartbeat.json` ring | 6 frames per 100 ms sample right up to the final sample (60 fps). `tcp_send_stall_ms` 1929 and rising: the IO thread was serving the poller continuously. |
| Windows Application log | No event 1000/1001 for the exe. The runtime exited voluntarily. |

`docs/STATUS.md` had already recorded the symptom (watchdog `exit(2)` reported
as `atexit`/`unknown`) but attributed it to a genuine 4 s stall. This run shows
it fires with a fresh heartbeat.

## Defect 1 — cross-thread read race wraps the staleness subtraction

`starvation_watchdog_check` runs on the emu thread every 65536 guest cycles
(`psx_cycles.c`, `psx_cycles_watchdog_fire`). It samples the clock **first**,
then reads the shared timestamp:

```c
/* starvation_ring.c:245 (pin 7ab698ca) */
void starvation_watchdog_check(void) {
    if (s_dump_done) return;
    if (s_last_heartbeat_us == 0) return;  /* not initialized yet */
    uint64_t timeout = starvation_timeout_us();
    if (timeout == 0) return;              /* watchdog disabled (renderer bring-up) */
    uint64_t now = host_us_now();
    if (now - s_last_heartbeat_us > timeout) {
        starvation_ring_dump(NULL);
        fprintf(stderr, "starvation_watchdog: %llu us without heartbeat — "
                "ring dumped to starvation_dump.jsonl, aborting\n",
                (unsigned long long)(now - s_last_heartbeat_us));
        fflush(stderr);
        exit(2);
    }
}
```

`s_last_heartbeat_us` is written by `starvation_watchdog_heartbeat()` from
**two threads**:

- emu thread: `debug_server_poll` (per vblank) and the host pause loops in `main.cpp`;
- debug-server IO thread (`io_thread_main`, SDL thread `psx-dbg-io`):
  `send_all_blocking` at `debug_server.c:4816`, once per `send()` chunk
  ("Legitimate debug traffic in flight — not starvation").

If the IO thread stores a heartbeat between the emu thread's `host_us_now()`
and its load of `s_last_heartbeat_us`, then `last > now`, the `uint64_t`
subtraction wraps to ~1.8e19, the comparison passes, and the runtime exits.
The dump then re-reads the clock and prints the true staleness — the 402 µs
above. The variable is also a plain `uint64_t` with no atomic qualifier, so
the load is not even guaranteed to be single-copy atomic on every target.

### Fix

Read the timestamp first, then the clock, and refuse a negative gap. Make the
shared variable atomic so the cross-thread store/load is well defined.

```diff
--- a/runtime/src/starvation_ring.c
+++ b/runtime/src/starvation_ring.c
@@
-static uint64_t        s_last_heartbeat_us = 0;
+#include <stdatomic.h>
+static _Atomic uint64_t s_last_heartbeat_us = 0;
@@
 void starvation_watchdog_heartbeat(void) {
-    s_last_heartbeat_us = host_us_now();
+    atomic_store_explicit(&s_last_heartbeat_us, host_us_now(),
+                          memory_order_relaxed);
 }
@@
 void starvation_ring_reset(void) {
     memset(s_ring, 0, sizeof(s_ring));
     s_seq = 0;
-    s_last_heartbeat_us = 0;
+    atomic_store_explicit(&s_last_heartbeat_us, 0, memory_order_relaxed);
     s_dump_done = 0;
 }
@@
 void starvation_watchdog_check(void) {
     if (s_dump_done) return;
-    if (s_last_heartbeat_us == 0) return;  /* not initialized yet */
+    uint64_t last = atomic_load_explicit(&s_last_heartbeat_us,
+                                         memory_order_relaxed);
+    if (last == 0) return;                 /* not initialized yet */
     uint64_t timeout = starvation_timeout_us();
     if (timeout == 0) return;              /* watchdog disabled (renderer bring-up) */
-    uint64_t now = host_us_now();
-    if (now - s_last_heartbeat_us > timeout) {
+    /* Sample `last` BEFORE `now`: the debug-server IO thread also stamps the
+     * heartbeat (send_all_blocking), and a stamp landing between the two reads
+     * in the old order made `now < last`, wrapped the subtraction, and exited
+     * a healthy runtime (BoF3 2026-09-02: 402 us "staleness" tripped 4 s). */
+    uint64_t now = host_us_now();
+    if (now <= last) return;
+    if (now - last > timeout) {
         starvation_ring_dump(NULL);
         fprintf(stderr, "starvation_watchdog: %llu us without heartbeat — "
                 "ring dumped to starvation_dump.jsonl, aborting\n",
-                (unsigned long long)(now - s_last_heartbeat_us));
+                (unsigned long long)(now - last));
         fflush(stderr);
+        psx_crash_trace_set_exit_origin("starvation_watchdog");
         exit(2);
     }
 }
```

`starvation_ring_dump` prints `s_last_heartbeat_us` in its meta line; switch
that to the same relaxed load. Add `#include "crash_trace.h"` for the
exit-origin setter. The `#else` stubs (`STARVATION_RING_ENABLED=0`) are
unaffected.

## Defect 2 — a watchdog exit is reported as a clean shutdown

`psx_last_run_report.json` carries `reason` and `exit_origin`. Only three
sites ever set the origin: `debug_server.c:11333` (`tcp_quit`) and the
`sdl_window_close` paths in `main.cpp`. Every other `exit()` — the watchdog
included — reaches `psx_atexit_handler` with no origin, so the report reads
`reason: "atexit"`, `exit_origin: "unknown"`, indistinguishable from a user
closing the window. That is why this class of exit kept being described as a
"crash" with no lead in the report.

The one-line `psx_crash_trace_set_exit_origin("starvation_watchdog")` in the
diff above fixes this site. The same day showed a third one:
`psx_console_ctrl_handler` (`crash_trace.c:894`) calls `exit(0)` on
`CTRL_C_EVENT` / `CTRL_BREAK_EVENT` / `CTRL_CLOSE_EVENT`, so a console being
torn down under the game (2026-09-02 16:31: Windows Terminal crashed with the
game attached, frame 264564) is likewise reported as `atexit` / `unknown`.
Label it `console_close` (or per event) before the `exit(0)`.

Worth a sweep while there: `grep -n 'exit(' runtime/src/*.c`
shows 27 exit sites; any that represent an abnormal stop should name
themselves the same way (the native-stack-guard and xprobe fatals already go
through `psx_fatal_halt`, which is labelled).

## Optional — a config-file switch

There is no `game.toml` / `settings.toml` key for the timeout; the runtime reads
only `PSX_STARVATION_TIMEOUT_US`. If upstream wants one, `[runtime]` in
`config_schema.md` is the natural home (`starvation_timeout_us = 0`), read in
`starvation_timeout_us()` after the env var so the env var still wins. Not
required for the fix; the `setx` workaround covers this machine.

## Verification plan

1. Build `build-dbg` against the patched submodule with the env var **unset**
   (`setx PSX_STARVATION_TIMEOUT_US ""`, then a new shell).
2. Run the area poller (`tools/area_poller.py watch`) against a windowed session
   for at least 10 minutes; before the fix the poller's constant TCP traffic
   made the race hit within about 2 minutes on 2026-09-02.
3. Confirm `starvation_dump.jsonl` is not written and the session survives.
4. Force a real trip (`PSX_STARVATION_TIMEOUT_US=1000`) and confirm
   `psx_last_run_report.json` now says `exit_origin: "starvation_watchdog"`.
5. Re-persist `PSX_STARVATION_TIMEOUT_US=0` only if the watchdog still
   misbehaves; otherwise leave it enabled so real stalls are caught.

## Filing

Target: `mstan/psxrecomp`, one PR, title along the lines of
*runtime: fix starvation watchdog cross-thread wrap; label watchdog exits*.
Cite this doc's evidence table. Bump the `psxrecomp` gitlink deliberately when
merged (see `HANDOFF.md`, pin recipe) and drop the `setx` workaround.
