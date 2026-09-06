/**
 * S2 canvas perf gate. Runs e2e/canvas-perf.spec.ts (mock-IPC, Chromium)
 * and asserts AC-S2-3: 12 flooding terminal nodes, pan for 5 s; p95 frame
 * ≤ 16 ms at zoom 1 and ≤ 8 ms at zoom 0.5. A frame interval can never be
 * shorter than the display refresh period (8.33 ms on a 120 Hz panel). The
 * spec measures that period on an idle page first; a bar below it passes
 * when p95 stays under 1.5× the idle period, i.e. no frame missed a refresh
 * (rAF deltas jitter by about ±1.5 ms around the period even when idle).
 * The stressed samples never widen their own bar. Numbers are printed and
 * recorded in docs/canvas-perf.md after a run on the dev machine.
 *
 * Usage: pnpm test:canvas-perf            (starts vite via playwright.config)
 *        VOSS_APP_URL=http://localhost:5199 pnpm test:canvas-perf
 */

import { spawnSync } from 'node:child_process';

const P95_ZOOM_1_MAX_MS = 16;
const P95_ZOOM_HALF_MAX_MS = 8;

interface Sample {
  zoom: number;
  frames: number;
  chips: number;
  period: number;
  p50: number;
  p95: number;
  max: number;
}

interface Idle {
  period: number;
  frames: number;
}

const DROPPED_FRAME_TOLERANCE = 1.5;

function limitFor(barMs: number, idle: Idle): number {
  const noDropLimit = idle.period * DROPPED_FRAME_TOLERANCE;
  return idle.period > barMs ? noDropLimit : barMs;
}

function run(): { idle: Idle; samples: Sample[] } {
  const res = spawnSync('pnpm', ['playwright', 'test', 'canvas-perf', '--reporter=line'], {
    cwd: process.cwd(),
    env: process.env,
    encoding: 'utf8',
  });
  process.stdout.write(res.stdout);
  process.stderr.write(res.stderr);
  const samples: Sample[] = [];
  for (const m of res.stdout.matchAll(/\[canvas-perf\] (\{.*\})/g)) {
    samples.push(JSON.parse(m[1]) as Sample);
  }
  const idleMatch = /\[canvas-perf-idle\] (\{.*\})/.exec(res.stdout);
  if (res.status !== 0 || samples.length < 2 || !idleMatch) {
    console.error('canvas-perf: spec failed or produced no samples');
    process.exit(1);
  }
  return { idle: JSON.parse(idleMatch[1]) as Idle, samples };
}

function main(): void {
  const { idle, samples } = run();
  const one = samples.find((s) => Math.abs(s.zoom - 1) < 0.05);
  const half = samples.find((s) => Math.abs(s.zoom - 0.5) < 0.05);
  if (!one || !half) {
    console.error('canvas-perf: missing a zoom sample', samples);
    process.exit(1);
  }
  const limitOne = limitFor(P95_ZOOM_1_MAX_MS, idle);
  const limitHalf = limitFor(P95_ZOOM_HALF_MAX_MS, idle);
  const okOne = one.p95 <= limitOne;
  const okHalf = half.p95 <= limitHalf;
  console.log(
    `AC-S2-3 idle refresh period ${idle.period}ms; ` +
      `zoom 1: p95=${one.p95}ms (≤${limitOne.toFixed(1)}) ${okOne ? 'PASS' : 'FAIL'}; ` +
      `zoom 0.5: p95=${half.p95}ms (≤${limitHalf.toFixed(1)}) ${okHalf ? 'PASS' : 'FAIL'}`,
  );
  if (!okOne || !okHalf) process.exit(1);
}

main();
