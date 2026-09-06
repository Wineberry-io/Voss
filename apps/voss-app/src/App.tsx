import { onCleanup, onMount } from 'solid-js';
import { loadModelPrefs } from './agents/modelPrefs';
import { applyWindowEffects } from './appearance/windowEffects';
import { showToast } from './command-palette/toast';
import { COPY_LAST_WORKSPACE_BLOCKED } from './components/workspace/WorkspaceTabBar';
import { createAgentHost } from './app/agentHost';
import AppShell from './app/AppShell';
import { createKeymapHost } from './app/keymapHost';
import { createLiveBoot } from './app/liveBoot';
import { createViewRouter } from './app/viewRouter';
import { createWorkspaceHost } from './app/workspaceHost';

export { openAttachedPane } from './app/liveBoot';
export type { MountedWorkspace } from './app/workspaceHost';

/**
 * Composition root. Each host owns one concern; this file only wires them
 * and mounts the shell. See `src/app/`.
 */
export default function App() {
  let keys: ReturnType<typeof createKeymapHost> | undefined;

  const ws = createWorkspaceHost({
    onProjectOpened: (path) => void keys?.installWorkspaceKeymap(path),
    onCloseBlocked: () => showToast('info', COPY_LAST_WORKSPACE_BLOCKED),
  });
  const view = createViewRouter(ws);
  keys = createKeymapHost(ws, view);
  const live = createLiveBoot(ws, view);
  const agents = createAgentHost(ws);

  onMount(() => {
    keys!.install();
    live.install();
    void applyWindowEffects({ enabled: true });
    void loadModelPrefs().catch(() => ({}));
    void ws.boot();
  });

  onCleanup(() => {
    keys!.dispose();
    live.dispose();
    ws.dispose();
  });

  return <AppShell ws={ws} view={view} live={live} agents={agents} keys={keys} />;
}
