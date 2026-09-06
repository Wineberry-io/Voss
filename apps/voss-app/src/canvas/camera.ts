import type { CanvasView } from './model';

export const CAMERA_MS = 200;

/** Appearance setting (html.reduced-motion) or the OS preference. */
export function prefersReducedMotion(): boolean {
  if (typeof document !== 'undefined' && document.documentElement.classList.contains('reduced-motion')) return true;
  return typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function easeOut(t: number): number {
  return 1 - (1 - t) * (1 - t);
}

export function lerpView(from: CanvasView, to: CanvasView, t: number): CanvasView {
  return {
    x: from.x + (to.x - from.x) * t,
    y: from.y + (to.y - from.y) * t,
    zoom: from.zoom + (to.zoom - from.zoom) * t,
  };
}

/**
 * Tween `from` → `to` over `durationMs`, calling `apply` each frame and
 * `done` with the exact target. Returns a cancel function. A zero duration
 * applies the target synchronously.
 */
export function animateView(
  from: CanvasView,
  to: CanvasView,
  apply: (view: CanvasView) => void,
  done: () => void,
  durationMs = CAMERA_MS,
  raf: (cb: (t: number) => void) => number = (cb) => requestAnimationFrame(cb),
  now: () => number = () => performance.now(),
): () => void {
  if (durationMs <= 0) {
    apply(to);
    done();
    return () => {};
  }
  let cancelled = false;
  const start = now();
  const step = () => {
    if (cancelled) return;
    const t = Math.min(1, (now() - start) / durationMs);
    if (t >= 1) {
      apply(to);
      done();
      return;
    }
    apply(lerpView(from, to, easeOut(t)));
    raf(step);
  };
  raf(step);
  return () => {
    cancelled = true;
  };
}
