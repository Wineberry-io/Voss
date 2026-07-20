// V24-10 / V24-11 (VADE2-10/11) — Memory surface.
//
// Voss memory lives in the harness (voss/harness/memory_store.py). V24-11 exposed it
// over the loopback server's GET /memory route, so when the app has a live server
// (baseUrl + token + cwd) this surface renders the real memory summary + a recall
// search. With no live server it falls back to the honest harness-backed state
// (the /memory slash command). It synthesizes NO rows — hits come only from the
// server (honest-signal discipline, like the swarm surface).

import {
  type Component,
  createResource,
  createSignal,
  For,
  Match,
  Show,
  Switch,
} from 'solid-js';
import '../surfaces.css';
import './memory.css';
import SurfaceEmpty from '../SurfaceEmpty';
import { fetchMemory, type MemoryResponse } from '../../org/live/memoryClient';

export interface MemorySurfaceProps {
  sidecarId?: string;
}

const MemoryIcon = () => (
  <svg
    width="22"
    height="22"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <rect x="6" y="6" width="12" height="12" rx="2" />
    <path d="M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3" />
  </svg>
);

/** Honest fallback when the app has no live server to query. */
const MemoryFallback: Component = () => (
  <div class="surface__body">
    <SurfaceEmpty
      icon={<MemoryIcon />}
      title="Memory lives in the Voss harness"
      hint={
        <>
          Recall and inspect memory from a Voss session with the{' '}
          <code>/memory</code> command. Start a session in this workspace to
          browse memory here.
        </>
      }
    />
  </div>
);

const MemorySurface: Component<MemorySurfaceProps> = (props) => {
  const live = () => !!props.sidecarId;

  const [submitted, setSubmitted] = createSignal('');
  const [query, setQuery] = createSignal('');

  const [data] = createResource(
    () =>
      live()
        ? {
            sidecarId: props.sidecarId!,
            q: submitted(),
          }
        : null,
    (args: { sidecarId: string; q: string }) =>
      fetchMemory(args.sidecarId, args.q || undefined),
  );

  return (
    <div class="surface" role="tabpanel" aria-label="Memory">
      <div class="surface__header">
        <span class="surface__title">Memory</span>
      </div>
      <Show when={live()} fallback={<MemoryFallback />}>
        <div class="surface__body">
          <form
            class="memory-search"
            onSubmit={(e) => {
              e.preventDefault();
              setSubmitted(query());
            }}
          >
            <input
              class="memory-search__input"
              type="search"
              placeholder="Search memory…"
              aria-label="Search memory"
              value={query()}
              onInput={(e) => setQuery(e.currentTarget.value)}
            />
          </form>

          <Switch>
            <Match when={data.loading}>
              <div class="org-spinner">
                <span class="org-spinner__glyph">⟳</span>
              </div>
            </Match>
            <Match when={data.error}>
              <div class="org-error-state">
                <p class="org-error-state__heading">Couldn't load memory.</p>
                <p class="org-error-state__body">Check that Voss is running.</p>
              </div>
            </Match>
            <Match when={data()}>
              {(resp: () => MemoryResponse) => (
                <>
                  <Show when={resp().hits.length > 0} fallback={
                    <pre class="memory-summary">{resp().summary}</pre>
                  }>
                    <div class="memory-hits">
                      <For each={resp().hits}>
                        {(hit) => (
                          <div class="memory-hit">
                            <div class="memory-hit__head">
                              <span class="memory-hit__locator">{hit.locator}</span>
                              <span class="memory-hit__source">{hit.source}</span>
                            </div>
                            <p class="memory-hit__excerpt">{hit.excerpt}</p>
                          </div>
                        )}
                      </For>
                    </div>
                  </Show>
                </>
              )}
            </Match>
          </Switch>
        </div>
      </Show>
    </div>
  );
};

export default MemorySurface;
