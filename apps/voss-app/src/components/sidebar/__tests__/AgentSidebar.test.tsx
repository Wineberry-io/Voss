import { describe, it, expect, vi, afterEach } from 'vitest';
import { render } from 'solid-js/web';
import { fireEvent } from '@testing-library/dom';
import AgentSidebar from '../AgentSidebar';

let dispose: (() => void) | undefined;
function mount(ui: () => unknown) {
  const root = document.createElement('div');
  document.body.appendChild(root);
  dispose = render(ui as () => never, root);
  return root;
}
afterEach(() => {
  dispose?.();
  dispose = undefined;
  document.body.innerHTML = '';
});

const defaultProps = () => ({
  collapsed: false,
  onToggle: vi.fn(),
  agents: [] as any[],
  focusedPaneId: undefined as string | undefined,
  onAgentClick: vi.fn(),
  onAgentContextMenu: vi.fn(),
  onLaunchAgent: vi.fn(),
  activityEvents: [] as any[],
  usageEntries: [] as any[],
  workspacePath: null as string | null,
});

describe('AgentSidebar', () => {
  it('renders 4 section headings', () => {
    const p = defaultProps();
    const el = mount(() => <AgentSidebar {...p} />);
    const labels = el.querySelectorAll('.sidebar-section-label');
    const texts = Array.from(labels).map((l) => l.textContent?.trim());
    expect(texts).toEqual(['AGENTS', 'ACTIVITY', 'USAGE', 'FILES']);
  });

  it('collapsed renders with sidebar--collapsed class', () => {
    const p = defaultProps();
    p.collapsed = true;
    const el = mount(() => <AgentSidebar {...p} />);
    expect(el.querySelector('.sidebar--collapsed')).toBeTruthy();
  });

  it('renders expand handle when collapsed', () => {
    const p = defaultProps();
    p.collapsed = true;
    const el = mount(() => <AgentSidebar {...p} />);
    const expandBtn = el.querySelector('[aria-label="Expand sidebar"]');
    expect(expandBtn).toBeTruthy();
  });

  it('renders agent items', () => {
    const p = defaultProps();
    p.agents = [
      { paneId: 'p1', cliBinary: 'claude', model: 'opus', role: 'planner', costUsd: 0.5, isStreaming: false },
      { paneId: 'p2', cliBinary: 'codex', model: 'gpt-4', role: 'executor', costUsd: 0.1, isStreaming: true },
    ];
    const el = mount(() => <AgentSidebar {...p} />);
    const items = el.querySelectorAll('.agent-item');
    expect(items).toHaveLength(2);
  });

  it('empty agents shows placeholder', () => {
    const p = defaultProps();
    const el = mount(() => <AgentSidebar {...p} />);
    expect(el.textContent).toContain('No agents running');
  });

  it('calls onToggle when chevron clicked', () => {
    const p = defaultProps();
    const el = mount(() => <AgentSidebar {...p} />);
    const chevron = el.querySelector('[aria-label="Collapse sidebar"]') as HTMLButtonElement;
    expect(chevron).toBeTruthy();
    fireEvent.click(chevron);
    expect(p.onToggle).toHaveBeenCalledOnce();
  });

  it('calls onLaunchAgent when + Agent clicked', () => {
    const p = defaultProps();
    const el = mount(() => <AgentSidebar {...p} />);
    const btn = el.querySelector('[aria-label="Launch agent"]') as HTMLButtonElement;
    expect(btn).toBeTruthy();
    fireEvent.click(btn);
    expect(p.onLaunchAgent).toHaveBeenCalledOnce();
  });
});
