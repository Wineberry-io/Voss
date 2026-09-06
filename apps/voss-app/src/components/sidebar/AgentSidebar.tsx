import { type Component, createEffect, createSignal, For, Show } from 'solid-js';
import type { AgentItemProps } from './AgentItem';
import AgentItem from './AgentItem';
import ActivitySection from './ActivitySection';
import type { ActivityEvent } from './ActivitySection';
import UsageSection from './UsageSection';
import type { UsageEntry } from './UsageSection';
import FileTree from './FileTree';
import './sidebar.css';

type AgentEntry = Omit<AgentItemProps, 'onClick' | 'onContextMenu' | 'isActive'>;

export interface AgentSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  agents: AgentEntry[];
  focusedPaneId?: string;
  onAgentClick: (paneId: string) => void;
  onAgentContextMenu: (paneId: string, e: MouseEvent) => void;
  onLaunchAgent: () => void;
  activityEvents: ActivityEvent[];
  usageEntries: UsageEntry[];
  workspacePath: string | null;
  onOpenFile?: (relPath: string) => void;
}

const AgentSidebar: Component<AgentSidebarProps> = (props) => {
  const [agentOrder, setAgentOrder] = createSignal<AgentEntry[]>(props.agents);

  createEffect(() => {
    setAgentOrder(props.agents);
  });

  const onDragOver = (e: DragEvent) => {
    e.preventDefault();
    e.dataTransfer!.dropEffect = 'move';
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    const droppedPaneId = e.dataTransfer?.getData('text/plain');
    if (!droppedPaneId) return;

    const current = agentOrder();
    const fromIndex = current.findIndex((a) => a.paneId === droppedPaneId);
    if (fromIndex === -1) return;

    // Find drop target based on mouse position
    const container = e.currentTarget as HTMLElement;
    const items = container.querySelectorAll('.agent-item');
    let toIndex = current.length;
    for (let i = 0; i < items.length; i++) {
      const rect = items[i].getBoundingClientRect();
      if (e.clientY < rect.top + rect.height / 2) {
        toIndex = i;
        break;
      }
    }

    if (fromIndex === toIndex) return;

    const next = [...current];
    const [moved] = next.splice(fromIndex, 1);
    const insertAt = toIndex > fromIndex ? toIndex - 1 : toIndex;
    next.splice(insertAt, 0, moved);
    setAgentOrder(next);
  };

  return (
    <>
      <div class={`sidebar${props.collapsed ? ' sidebar--collapsed' : ''}`}>
        {/* Header 44px */}
        <div class="sidebar-header">
          <svg
            class="sidebar-header__logo"
            viewBox="0 0 2048 2048"
            fill="none"
            style="color: var(--focus)"
          >
            <path
              d="M332 471h278l566 908-136 226L332 471Z"
              fill="currentColor"
            />
            <path
              d="M1432 470h308l-503 724-144-197 339-527Z"
              fill="currentColor"
            />
          </svg>
          <span class="sidebar-header__title">Agents</span>
          <div class="sidebar-header__spacer" />
          <button
            class="sidebar-header__btn"
            style={{ 'border-radius': '3px' }}
            onClick={() => props.onLaunchAgent()}
            aria-label="Launch agent"
          >
            +
          </button>
          <button
            class="sidebar-header__btn"
            onClick={() => props.onToggle()}
            aria-label="Collapse sidebar"
          >
            &#x25C0;
          </button>
        </div>

        {/* AGENTS section */}
        <div class="sidebar-section-label">AGENTS</div>
        <div class="sidebar-section-body" onDragOver={onDragOver} onDrop={onDrop}>
          <Show
            when={agentOrder().length > 0}
            fallback={<div class="sidebar-empty">No agents running</div>}
          >
            <For each={agentOrder()}>
              {(agent) => (
                <AgentItem
                  {...agent}
                  isActive={props.focusedPaneId === agent.paneId}
                  onClick={() => props.onAgentClick(agent.paneId)}
                  onContextMenu={(e) =>
                    props.onAgentContextMenu(agent.paneId, e)
                  }
                />
              )}
            </For>
          </Show>
          {/* V14 chunk C — quick-launch row (mockup .qlbtn): same launch
              path as the header + button. */}
          <button
            type="button"
            class="sidebar-quick-launch"
            aria-label="Quick-launch agent"
            onClick={() => props.onLaunchAgent()}
          >
            + Quick-launch agent
          </button>
        </div>

        {/* ACTIVITY section */}
        <div class="sidebar-section-label">ACTIVITY</div>
        <div class="sidebar-section-body" style={{ flex: '1', 'min-height': '0' }}>
          <ActivitySection events={props.activityEvents} />
        </div>

        {/* USAGE section */}
        <div class="sidebar-section-label">USAGE</div>
        <div class="sidebar-section-body">
          <UsageSection entries={props.usageEntries} />
        </div>

        {/* FILES section */}
        <div class="sidebar-section-label">FILES</div>
        <div class="sidebar-section-body" style={{ flex: '1', 'min-height': '0', overflow: 'auto' }}>
          <FileTree projectPath={props.workspacePath} onOpenFile={props.onOpenFile} />
        </div>
      </div>

      {/* Expand handle when collapsed */}
      <Show when={props.collapsed}>
        <button
          class="sidebar-expand"
          style={{ 'border-radius': '0 3px 3px 0' }}
          onClick={() => props.onToggle()}
          aria-label="Expand sidebar"
        >
          &#x25B8;
        </button>
      </Show>
    </>
  );
};

export default AgentSidebar;
