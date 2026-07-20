// V24 Orchestra command bar: honest disabled-with-reason +
// real postMessage send path. fetchSwarm/registry are not involved here.

import { afterEach, describe, expect, it, vi } from 'vitest';
import { render } from 'solid-js/web';
import SwarmCommandBar from '../SwarmCommandBar';
import { setLiveServer, __resetLiveServer } from '../../../org/live/liveServer';
import { ingestSwarmEvent, __resetSwarmLive } from '../../../org/live/swarmLive';

let dispose: (() => void) | undefined;
function mount(): HTMLElement {
  const root = document.createElement('div');
  document.body.appendChild(root);
  dispose = render(() => <SwarmCommandBar />, root);
  return root;
}

afterEach(() => {
  dispose?.();
  dispose = undefined;
  document.body.innerHTML = '';
  __resetLiveServer();
  __resetSwarmLive();
});

function assign(role: string, sessionId: string): void {
  ingestSwarmEvent({
    type: 'swarm.assign',
    swarm_id: 'sw1',
    task_id: `task-${role}`,
    session_id: sessionId,
    owned_files: [],
    role,
  });
}

describe('SwarmCommandBar', () => {
  it('disabled-with-reason when not connected', () => {
    const el = mount();
    const input = el.querySelector<HTMLInputElement>('.swarm-bar__input')!;
    expect(input.disabled).toBe(true);
    expect(input.placeholder).toMatch(/Not connected/);
  });

  it('disabled-with-reason when connected but no live agents', () => {
    setLiveServer({ sidecarId: 'test-sidecar', followUpClient: { postMessage: vi.fn() } });
    const el = mount();
    const input = el.querySelector<HTMLInputElement>('.swarm-bar__input')!;
    expect(input.disabled).toBe(true);
    expect(input.placeholder).toMatch(/start an orchestra/);
  });

  it('directs the selected target via postMessage when live', async () => {
    const postMessage = vi.fn().mockResolvedValue(undefined);
    setLiveServer({ sidecarId: 'test-sidecar', followUpClient: { postMessage } });
    assign('builder-1', 's-b1');
    assign('builder-2', 's-b2');

    const el = mount();
    const input = el.querySelector<HTMLInputElement>('.swarm-bar__input')!;
    expect(input.disabled).toBe(false);
    expect(input.getAttribute('aria-label')).toBe('Direct the Orchestra');
    expect(input.placeholder).toContain('Direct the Orchestra');

    // default target @all → broadcasts to both sessions
    input.value = 'ship it';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    await Promise.resolve();
    await Promise.resolve();

    expect(postMessage).toHaveBeenCalledTimes(2);
    expect(postMessage.mock.calls.map((c) => c[0]).sort()).toEqual(['s-b1', 's-b2']);
    expect(postMessage.mock.calls[0][1]).toBe('ship it');
  });

  it('parses a leading @role to target one session', async () => {
    const postMessage = vi.fn().mockResolvedValue(undefined);
    setLiveServer({ sidecarId: 'test-sidecar', followUpClient: { postMessage } });
    assign('builder-1', 's-b1');
    assign('builder-2', 's-b2');

    const el = mount();
    const input = el.querySelector<HTMLInputElement>('.swarm-bar__input')!;
    input.value = '@builder-2 focus on the gate';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    await Promise.resolve();
    await Promise.resolve();

    expect(postMessage).toHaveBeenCalledTimes(1);
    expect(postMessage).toHaveBeenCalledWith('s-b2', 'focus on the gate');
  });

  it('Status report broadcasts a canned prompt to all live sessions', async () => {
    const postMessage = vi.fn().mockResolvedValue(undefined);
    setLiveServer({ sidecarId: 'test-sidecar', followUpClient: { postMessage } });
    assign('builder-1', 's-b1');

    const el = mount();
    const btn = Array.from(el.querySelectorAll('button')).find(
      (b) => b.textContent === 'Status report',
    )!;
    btn.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await Promise.resolve();
    await Promise.resolve();

    expect(postMessage).toHaveBeenCalledWith('s-b1', expect.stringMatching(/status report/i));
  });
});
