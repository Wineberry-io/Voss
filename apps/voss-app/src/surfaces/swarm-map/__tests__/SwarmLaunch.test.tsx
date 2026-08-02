// V24 swarm surface — launch intake copy and compact overlay mode.

import { afterEach, describe, expect, it, vi } from 'vitest';
import { render } from 'solid-js/web';

const launchSwarmMock = vi.fn();
vi.mock('../../../org/live/swarmLaunch', () => ({
  launchSwarm: (...args: unknown[]) => launchSwarmMock(...args),
}));

import SwarmLaunch from '../SwarmLaunch';
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
  const ta = el.querySelector('textarea') as HTMLTextAreaElement;
  ta.value = text;
  ta.dispatchEvent(new Event('input', { bubbles: true }));
}

function launchBtn(el: HTMLElement): HTMLButtonElement {
  return el.querySelector('.swarm-launch__btn') as HTMLButtonElement;
}

describe('SwarmLaunch', () => {
  it('renders the full empty-state orchestra intake', () => {
    const el = mount(() => <SwarmLaunch />);
    expect(el.textContent).toContain('No orchestra running');
    expect(el.textContent).toContain('Launch orchestra');
    expect(el.querySelector('textarea')?.getAttribute('placeholder')).toBe(
      'Describe the work to coordinate...',
    );
  });

  it('omits the empty-state heading in compact mode', () => {
    const el = mount(() => <SwarmLaunch compact />);
    expect(el.textContent).not.toContain('No orchestra running');
    expect(el.textContent).toContain('Launch orchestra');
  });

  it('disables launch with the honest gate when no connector is wired', () => {
    const el = mount(() => <SwarmLaunch />);
    typeGoal(el, 'ship it');
    expect(launchBtn(el).disabled).toBe(true);
    expect(el.textContent).toContain('Open a workspace to connect a live Voss server.');
  });

  it('enables launch and shows the self-connect hint when a connector is wired', () => {
    setLiveServerConnector(async () => {});
    const el = mount(() => <SwarmLaunch />);
    typeGoal(el, 'ship it');
    expect(launchBtn(el).disabled).toBe(false);
    expect(el.textContent).toContain(
      'Launch will start a live Voss server for this workspace.',
    );
  });

  it('spawns the server on launch, then launches the orchestra', async () => {
    const srv: LiveServer = { sidecarId: 'test-sidecar', cwd: '/repo' };
    // Connector mimics ensureVossClient: side-effect sets the live server.
    setLiveServerConnector(async () => setLiveServer(srv));
    launchSwarmMock.mockResolvedValue(undefined);

    const el = mount(() => <SwarmLaunch />);
    typeGoal(el, 'ship it');
    launchBtn(el).click();
    await flush();

    expect(launchSwarmMock).toHaveBeenCalledWith(srv, {
      goal: 'ship it',
      builders: 2,
    });
  });

  it('reports an honest reason when on-demand connect finds no workspace', async () => {
    // Connector resolves without setting a server (no folder open).
    setLiveServerConnector(async () => {});
    const el = mount(() => <SwarmLaunch />);
    typeGoal(el, 'ship it');
    launchBtn(el).click();
    await flush();

    expect(launchSwarmMock).not.toHaveBeenCalled();
    expect(el.textContent).toContain(
      'Open a workspace folder to connect a live Voss server.',
    );
  });
});
