import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import { getCurrentWindow } from '@tauri-apps/api/window';
import {
  createMemo,
  createSignal,
  onCleanup,
  onMount,
  Show,
  Switch,
  Match,
  type Component,
} from 'solid-js';
import TopChrome from '../components/titlebar/TopChrome';
import VossComposer from '../composer/VossComposer';
import OrgViewShell from '../org/OrgViewShell';
import RunCommandBar, {
  dispatchRunSpec,
  type RunNativeClient,
} from '../org/cockpit/RunCommandBar';
import { liveLabel } from '../org/live/sseClient';
import { setLiveServer, setLiveServerConnector } from '../org/live/liveServer';
import { startVossServe } from '../org/live/sidecarClient';
import {
  buildVossClientFromHandle,
  type BuiltVossClient,
} from '../org/live/vossClientBuild';
import { setSelectedCardId } from '../org/selection';
import PortalRail from '../portal/PortalRail';
import type { PortalItem } from '../portal/portalTypes';
import MemorySurface from '../surfaces/memory/MemorySurface';
import SwarmMap from '../surfaces/swarm-map/SwarmMap';
import {
  getOrchestrationContext,
  type OrchestrationContext,
  type OrchestrationView,
} from './window';
import './orchestrationConsole.css';

const ORCHESTRATION_ITEMS: readonly PortalItem[] = [
  { id: 'review', label: 'Review', glyph: '※' },
  { id: 'swarm-map', label: 'Orchestra', glyph: '◈' },
  { id: 'memory', label: 'Memory', glyph: '◉' },
];

function projectName(cwd: string): string {
  const parts = cwd.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] ?? 'Voss';
}

const OrchestrationConsole: Component = () => {
  const [context, setContext] = createSignal<OrchestrationContext | null>(null);
  const [activeView, setActiveView] = createSignal<OrchestrationView>('review');
  const [client, setClient] = createSignal<BuiltVossClient | null>(null);
  const [loading, setLoading] = createSignal(true);
  const [error, setError] = createSignal<string | null>(null);
  const [composerOpen, setComposerOpen] = createSignal(false);
  let unlisten: UnlistenFn | undefined;
  let connectionGeneration = 0;

  const nativeClient = createMemo<RunNativeClient | undefined>(() => {
    const built = client();
    if (!built) return undefined;
    return {
      createSession: async (spec) => {
        const id = await built.client.createSession();
        await built.client.postMessage(id, spec.goal, spec.mode.toLowerCase());
        return { id };
      },
    };
  });

  const connect = async (next: OrchestrationContext): Promise<void> => {
    const generation = ++connectionGeneration;
    setContext(next);
    setActiveView(next.initialView);
    if (next.cardId) setSelectedCardId(next.cardId);
    setLoading(true);
    setError(null);
    try {
      const handle = await startVossServe(next.cwd);
      if (generation !== connectionGeneration) return;
      const built = buildVossClientFromHandle(handle);
      setClient(built);
      setLiveServer({
        sidecarId: built.sidecarId,
        cwd: next.cwd,
        followUpClient: built.followUpClient,
      });
      setLiveServerConnector(async () => built);
    } catch (cause) {
      if (generation !== connectionGeneration) return;
      setClient(null);
      setLiveServer(null);
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      if (generation === connectionGeneration) setLoading(false);
    }
  };

  onMount(() => {
    void getOrchestrationContext().then(connect).catch((cause) => {
      setError(cause instanceof Error ? cause.message : String(cause));
      setLoading(false);
    });
    void listen<OrchestrationContext>('voss://orchestration-context', (event) => {
      void connect(event.payload);
    }).then((stop) => {
      unlisten = stop;
    });
  });

  onCleanup(() => {
    connectionGeneration += 1;
    unlisten?.();
    setLiveServerConnector(null);
    setLiveServer(null);
  });

  const close = () => void getCurrentWindow().close();
  const cwd = () => context()?.cwd ?? '';

  return (
    <div class="orchestration-console">
      <TopChrome
        projectName={context() ? projectName(context()!.cwd) : 'Voss'}
        sectionLabel={(ORCHESTRATION_ITEMS.find((item) => item.id === activeView())?.label ?? 'Review').toUpperCase()}
        liveState={liveLabel()}
        onOpenComposer={() => setComposerOpen(true)}
      />
      <div class="orchestration-body">
        <PortalRail
          activeView={activeView()}
          items={ORCHESTRATION_ITEMS}
          onNavTo={(view) => setActiveView(view as OrchestrationView)}
          onOpenComposer={() => setComposerOpen(true)}
        />
        <main class="orchestration-main">
          <RunCommandBar
            cwd={cwd()}
            cliBinary="voss"
            client={nativeClient()}
            allowedTargets={['native']}
          />
          <Show when={loading()}>
            <div class="orchestration-state" role="status">Connecting to Voss...</div>
          </Show>
          <Show when={error()}>
            {(message) => <div class="orchestration-state orchestration-state--error" role="alert">{message()}</div>}
          </Show>
          <Show when={!loading() && !error()}>
            <div class="orchestration-surface">
              <Switch>
                <Match when={activeView() === 'review'}>
                  <OrgViewShell
                    cwd={cwd()}
                    cliBinary="voss"
                    onClose={close}
                    followUpClient={client()?.followUpClient}
                    vossClient={client()?.client}
                  />
                </Match>
                <Match when={activeView() === 'swarm-map'}>
                  <SwarmMap />
                </Match>
                <Match when={activeView() === 'memory'}>
                  <MemorySurface sidecarId={client()?.sidecarId} />
                </Match>
              </Switch>
            </div>
          </Show>
        </main>
      </div>
      <VossComposer
        open={composerOpen()}
        allowedTargets={['native']}
        onClose={() => setComposerOpen(false)}
        onCreated={(spec) =>
          dispatchRunSpec(spec, {
            cliBinary: 'voss',
            cwd: cwd(),
            client: nativeClient(),
          })
        }
      />
    </div>
  );
};

export default OrchestrationConsole;
