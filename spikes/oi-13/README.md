# OI-13 spike: SwiftUI on the main thread beside the Silica runtime

Question (requirements OI-13): can a SwiftUI host own the main thread and run loop while a Silica runtime runs beside
it, with events reaching Silica actors and commands coming back?

Answer: yes. Run 2026-11-24 on macOS 26, Swift 6.3.3, Silica release compiler `silica-999897-macos-applesilicon`
(release "Compiler e53689e").

## Layout

- `silica/` (hello.silica) and `exp1/`: the smallest test. A Swift program links the Silica objects and calls the Silica
  `main` on a secondary thread.
- `exp2/`: the full test. `./build.sh` (set `SILICA_COMPILER`) builds one executable from a Silica program
  (`silica/dangerous_viewer_spike.silica`), a C host (`host/viewer_host.c`) and a SwiftUI app (`app/App.swift`).
  Run `./spike` for the window, `./spike --auto 200` for timed round trips, `--burst` to send them at once, `--crash` to
  fault the main thread after 2 seconds.

## What was shown

1. The Silica entry symbol is `main` (no underscore), so it does not clash with Swift's `_main`. A 4-line C shim calls it.
   It runs on a thread the host creates. It does not take over the process. The Swift main thread stays free.
2. Events go from Swift to Silica with no call into the Silica runtime. Swift pushes onto a C queue. A Silica FFI worker
   (`spawn_dangerous`) blocks in a C function that pops the queue, casts the event to a plain actor, and casts itself again.
3. Commands go from Silica to Swift by an FFI worker calling a C function that calls a Swift handler on the worker's
   thread. The handler hops to the main thread to change SwiftUI state.
4. The path is Swift main, C queue, poller (FFI), listener actor, window actor, poster (FFI), Swift handler, Swift main.
   Over 200 round trips spaced 10 ms apart: min 0.043 ms, median 0.155 ms, mean 0.466 ms, max 1.481 ms.
   A burst of 5000 events at once: 5000 returned, 0 out of order, 0 lost (queueing latency up to 38 ms).
5. A real SwiftUI window opens (checked with the window list) and the app keeps running with the Silica thread blocked.

## Not shown, or found to be a problem

- A real mouse click was not exercised. The button calls the same function the automatic mode uses.
- Silica's fault handler takes every fatal signal. A SIGSEGV on the Swift main thread printed one line
  (`[silica] fault at ...`) and exited with 70. macOS wrote no crash report and Swift printed no backtrace.
- The failure reporter must be registered before any actor starts (E2236). This spike borrowed the trial support units
  (`Supervisor` and `trial_wait_int64`) copied from the Silica checkout. A real app needs its own root supervisor.
- The wrapper's C archive must exist before the Silica compile (E4034).
- Buffers returned by the C wrapper are leaked (the spike does not free them).
- No actor was made to fail, so supervision and restart inside the embedded process are untested.
- No orderly shutdown: quitting the app does not stop the Silica threads.
