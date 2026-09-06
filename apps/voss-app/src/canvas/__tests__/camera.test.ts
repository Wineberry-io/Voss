import { afterEach, describe, expect, it } from 'vitest';
import { animateView, lerpView, prefersReducedMotion } from '../camera';

afterEach(() => document.documentElement.classList.remove('reduced-motion'));

describe('camera', () => {
  it('lerps every field', () => {
    expect(lerpView({ x: 0, y: 0, zoom: 1 }, { x: 100, y: -50, zoom: 2 }, 0.5)).toEqual({ x: 50, y: -25, zoom: 1.5 });
  });

  it('tweens with the injected clock and lands exactly on the target', () => {
    let t = 0;
    const frames: (() => void)[] = [];
    const applied: number[] = [];
    let done = 0;
    animateView(
      { x: 0, y: 0, zoom: 1 },
      { x: 100, y: 0, zoom: 1 },
      (v) => applied.push(v.x),
      () => (done += 1),
      100,
      (cb) => {
        frames.push(() => cb(t));
        return frames.length;
      },
      () => t,
    );
    const tick = (ms: number) => {
      t = ms;
      frames.shift()!();
    };
    tick(0);
    tick(50);
    expect(applied.at(-1)).toBeGreaterThan(0);
    expect(applied.at(-1)).toBeLessThan(100);
    tick(120);
    expect(applied.at(-1)).toBe(100);
    expect(done).toBe(1);
    expect(frames).toHaveLength(0);
  });

  it('cancel stops further frames', () => {
    const frames: (() => void)[] = [];
    const applied: number[] = [];
    const cancel = animateView(
      { x: 0, y: 0, zoom: 1 },
      { x: 100, y: 0, zoom: 1 },
      (v) => applied.push(v.x),
      () => {},
      100,
      (cb) => {
        frames.push(() => cb(0));
        return 1;
      },
      () => 10,
    );
    cancel();
    frames.shift()!();
    expect(applied).toHaveLength(0);
  });

  it('AC-S2-7: zero duration applies synchronously; the html class opts into reduced motion', () => {
    let x = 0;
    animateView({ x: 0, y: 0, zoom: 1 }, { x: 9, y: 0, zoom: 1 }, (v) => (x = v.x), () => {}, 0);
    expect(x).toBe(9);
    expect(prefersReducedMotion()).toBe(false);
    document.documentElement.classList.add('reduced-motion');
    expect(prefersReducedMotion()).toBe(true);
  });
});
