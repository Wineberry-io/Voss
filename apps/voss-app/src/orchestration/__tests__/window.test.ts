import { beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({ invoke: vi.fn() }));
vi.mock('@tauri-apps/api/core', () => ({ invoke: h.invoke }));

import {
  getOrchestrationContext,
  openOrchestrationConsole,
} from '../window';

describe('orchestration window IPC', () => {
  beforeEach(() => h.invoke.mockReset());

  it('opens the console with an explicit project, surface, and card', async () => {
    h.invoke.mockResolvedValueOnce(undefined);
    await openOrchestrationConsole('/repo/voss', 'review', 'card-7');
    expect(h.invoke).toHaveBeenCalledWith('open_orchestration_console', {
      cwd: '/repo/voss',
      initialView: 'review',
      cardId: 'card-7',
    });
  });

  it('loads context from Rust without renderer-supplied paths', async () => {
    const context = { cwd: '/repo/voss', initialView: 'memory' as const };
    h.invoke.mockResolvedValueOnce(context);
    await expect(getOrchestrationContext()).resolves.toBe(context);
    expect(h.invoke).toHaveBeenCalledWith('get_orchestration_context');
  });
});
