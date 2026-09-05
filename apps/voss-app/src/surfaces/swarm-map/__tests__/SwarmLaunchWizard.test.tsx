// V24 swarm surface — SwarmLaunchWizard: stepped intake, presets, per-role
// agent/model, self-connect launch with an explicit roster.

import { afterEach, describe, expect, it, vi } from 'vitest';
import { render } from 'solid-js/web';

const launchSwarmMock = vi.fn();
vi.mock('../../../org/live/swarmLaunch', () => ({
  launchSwarm: (...args: unknown[]) => launchSwarmMock(...args),
}));

import SwarmLaunchWizard from '../SwarmLaunchWizard';
import {
  __resetLiveServer,
  setLiveServer,
  setLiveServerConnector,
  type LiveServer,
} from '../../../org/live/liveServer';

let dispose: (() => void) | undefined;
function mount(ui: () => unknown): HTMLElement {
  const root = document.createElement('div');
  document.body.appendChild(root);
  dispose = render(ui as () => never, root);
  return root;
}

afterEach(() => {
  dispose?.();
  dispose = undefined;
  document.body.innerHTML = '';
  __resetLiveServer();
  launchSwarmMock.mockReset();
});

const flush = () => new Promise((r) => setTimeout(r, 0));

function typeGoal(el: HTMLElement, text: string): void {
  const ta = el.querySelector('.swz__goal') as HTMLTextAreaElement;
  ta.value = text;
  ta.dispatchEvent(new Event('input', { bubbles: true }));
}

const primary = (el: HTMLElement) =>
  el.querySelector('.swz__nav--primary') as HTMLButtonElement;
const back = (el: HTMLElement) => el.querySelector('.swz__nav--ghost') as HTMLButtonElement;

/** Advance from step 1 (goal) to step 2 (roster). */
function toRoster(el: HTMLElement): void {
  typeGoal(el, 'ship the thing');
  primary(el).click();
}

describe('SwarmLaunchWizard', () => {
  it('gates Next on a non-empty goal at step 1', () => {
    const el = mount(() => <SwarmLaunchWizard />);
    expect(el.textContent).toContain('Step 1 of 3');
    expect(primary(el).disabled).toBe(true);
    typeGoal(el, 'do it');
    expect(primary(el).disabled).toBe(false);
  });

  it('defaults to coordinator + 2 builders + reviewer on the roster step', () => {
    const el = mount(() => <SwarmLaunchWizard />);
    toRoster(el);
    expect(el.textContent).toContain('Build your roster');
    expect(el.querySelectorAll('.swz-role').length).toBe(4); // coord + 2 + reviewer
    expect(el.textContent).toContain('2 Engineers');
    expect(el.textContent).toContain('4 total');
  });

  it('applies a preset (builder count) and reflects it in the chips', () => {
    const el = mount(() => <SwarmLaunchWizard />);
    toRoster(el);
    const crew = [...el.querySelectorAll('.swz-preset')].find((b) =>
      b.textContent?.includes('Crew'),
    ) as HTMLButtonElement;
    crew.click();
    expect(el.querySelectorAll('.swz-role').length).toBe(6); // coord + 4 + reviewer
    expect(el.textContent).toContain('4 Engineers');
  });

  it('adds and removes builders, renumbering', () => {
    const el = mount(() => <SwarmLaunchWizard />);
    toRoster(el);
    (el.querySelector('.swz__add') as HTMLButtonElement).click();
    expect(el.querySelectorAll('.swz-role').length).toBe(5); // coord + 3 + reviewer
    const remove = el.querySelector('.swz-role__remove') as HTMLButtonElement;
    remove.click();
    expect(el.querySelectorAll('.swz-role').length).toBe(4);
  });

  it('launches with an explicit roster carrying the chosen per-role agent/model', async () => {
    const srv: LiveServer = { sidecarId: 'test-sidecar', cwd: '/repo' };
    setLiveServer(srv);
    launchSwarmMock.mockResolvedValue('sw1');

    const el = mount(() => <SwarmLaunchWizard />);
    toRoster(el);

    // Set the coordinator's option to Claude · Opus.
    const coordSelect = el.querySelector('.swz-role__select') as HTMLSelectElement;
    coordSelect.value = 'claude:opus';
    coordSelect.dispatchEvent(new Event('change', { bubbles: true }));

    primary(el).click(); // step 2 → 3 (review)
    expect(el.textContent).toContain('Review & launch');
    primary(el).click(); // launch
    await flush();

    expect(launchSwarmMock).toHaveBeenCalledTimes(1);
    const [, opts] = launchSwarmMock.mock.calls[0];
    expect(opts.goal).toBe('ship the thing');
    expect(opts.roster[0]).toEqual({ name: 'coordinator', agent: 'claude', model: 'opus' });
    expect(opts.roster).toHaveLength(4);
  });

  it('self-connects on launch when not yet connected', async () => {
    const srv: LiveServer = { sidecarId: 'test-sidecar', cwd: '/repo' };
    setLiveServerConnector(async () => setLiveServer(srv));
    launchSwarmMock.mockResolvedValue('sw2');

    const el = mount(() => <SwarmLaunchWizard />);
    toRoster(el);
    primary(el).click(); // → review (the launch step carries the connect note)
    expect(el.textContent).toContain(
      'Launch will start a live Voss server for this workspace.',
    );
    primary(el).click(); // launch (self-connects first)
    await flush();

    expect(launchSwarmMock).toHaveBeenCalledTimes(1);
    const [server] = launchSwarmMock.mock.calls[0];
    expect(server).toEqual(srv);
  });

  it('Back returns to the previous step', () => {
    const el = mount(() => <SwarmLaunchWizard />);
    expect(back(el).disabled).toBe(true); // step 1
    toRoster(el);
    expect(el.textContent).toContain('Step 2 of 3');
    back(el).click();
    expect(el.textContent).toContain('Step 1 of 3');
  });
});
