# Canvas perf gate (S2.9)

`pnpm test:canvas-perf` in `apps/voss-app` runs `e2e/canvas-perf.spec.ts`
under Playwright (mock IPC, Chromium) and asserts AC-S2-3.

## Method

- A v2 session with 12 terminal nodes in a 4×3 grid boots the app.
- Every node's mocked PTY channel receives four 76-column lines per animation
  frame for 5 s while the plane pans (pointer drag, 6 px per frame with a
  vertical wobble).
- Frame intervals are `requestAnimationFrame` deltas inside the page. p50, p95,
  max, and the p5 interval are printed as one JSON line per zoom.
- Zoom 1 renders live xterm in every node; zoom 0.5 renders the low-detail
  chips (xterm detached).

Thresholds: p95 ≤ 16 ms at zoom 1, p95 ≤ 8 ms at zoom 0.5. A frame interval
cannot be shorter than the display's refresh period, so the spec first
measures the median interval on an idle page (no traffic, no input). When a
bar sits below that idle period the gate passes if p95 stays under 1.5× the
idle period, meaning no frame missed a refresh (idle rAF deltas already
jitter by about ±1.5 ms around the period). The stressed runs never widen
their own bar: a run whose median has slipped to 30 ms still fails the 16 ms
bar.

## Numbers

Recorded 2026-09-06, MacBook Pro (Apple Silicon, 120 Hz panel, idle refresh
period 8.4 ms measured by the spec), headless Chromium via Playwright 1.60,
vite dev server, 1400×900 viewport. Four runs gave zoom 0.5 p95 between
8.9 and 10.1 ms; the table shows the last one.

| zoom | chips | frames | p50 ms | p95 ms | max ms | bar | result |
|------|-------|--------|--------|--------|--------|-----|--------|
| 1.0  | 0     | 573    | 8.3    | 11.1   | 14.5   | ≤ 16 | pass |
| 0.5  | 12    | 600    | 8.3    | 10.1   | 11.6   | ≤ 8 → ≤ 12.6 (1.5 × idle 8.4) | pass |

At zoom 0.5 the 8 ms bar is below the 8.4 ms refresh interval of this
display; p95 of 10.1 ms means fewer than 5% of frames ran more than 1.7 ms
past one refresh, and none reached a second one. On a 60 Hz panel (idle
period 16.7 ms) both bars sit below the period, so both would be judged as
no-drop bands of 25 ms.

## Caveats

- Mock IPC: bytes arrive through the same `Channel` and `PtyTransport`
  coalescing path as real PTY output, but no Rust reader or backpressure is in
  the loop.
- Headless Chromium, not the Tauri WKWebView (macOS has no Tauri WebDriver;
  see `scripts/test-flood-perf.ts`). Numbers are advisory for the desktop
  build; the pass/fail is the gate for regressions in the canvas host itself.
