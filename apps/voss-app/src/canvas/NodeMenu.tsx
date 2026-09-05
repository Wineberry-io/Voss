import { For, Show, onCleanup, onMount } from 'solid-js';

/**
 * The `⋯` popup for a canvas node: Fork / Split right / Split below /
 * separator / Close. Same contract as the grid DotMenu, callback-driven.
 */
export default function NodeMenu(props: {
  onFork: () => void;
  onSplitRight: () => void;
  onSplitBelow: () => void;
  onRequestClose: () => void;
  onDismiss: () => void;
}) {
  let root!: HTMLDivElement;

  const run = (fn: () => void) => {
    props.onDismiss();
    fn();
  };

  const items = [
    { copy: 'Fork pane', kbd: '⌘D', cls: 'text-fg-0', act: () => run(props.onFork) },
    { copy: 'Split right', kbd: '⌘\\', cls: 'text-fg-0', act: () => run(props.onSplitRight) },
    { copy: 'Split below', kbd: '⌘⇧\\', cls: 'text-fg-0', act: () => run(props.onSplitBelow) },
    { copy: 'Close pane', kbd: '⌘W', cls: 'text-accent-red', act: () => run(props.onRequestClose) },
  ];

  const onDocKey = (e: KeyboardEvent) => {
    if (e.key === 'Escape') props.onDismiss();
  };
  const onDocClick = (e: MouseEvent) => {
    if (root && !root.contains(e.target as Node)) props.onDismiss();
  };
  onMount(() => {
    document.addEventListener('keydown', onDocKey);
    document.addEventListener('click', onDocClick, true);
  });
  onCleanup(() => {
    document.removeEventListener('keydown', onDocKey);
    document.removeEventListener('click', onDocClick, true);
  });

  return (
    <div
      ref={root}
      class="font-ui bg-bg-3"
      role="menu"
      style={{
        position: 'absolute',
        top: '22px',
        right: 0,
        width: '128px',
        border: '1px solid var(--border)',
        'border-radius': 0,
        'box-shadow': '0 4px 12px rgba(0,0,0,0.4)',
        'z-index': 10,
      }}
    >
      <For each={items}>
        {(it, i) => (
          <>
            <button
              type="button"
              role="menuitem"
              class={`${it.cls} hover:bg-bg-2`}
              style={{
                display: 'flex',
                'align-items': 'center',
                width: '100%',
                height: '22px',
                padding: '0 16px',
                background: 'transparent',
                border: 'none',
                cursor: 'default',
                'font-size': '11px',
                'font-weight': 400,
              }}
              onClick={it.act}
            >
              <span>{it.copy}</span>
              <span style={{ flex: 1 }} />
              <span class="text-fg-3" style={{ 'font-size': '10px' }}>
                {it.kbd}
              </span>
            </button>
            <Show when={i() === 2}>
              <div style={{ height: '1px', margin: 0, background: 'var(--border)' }} />
            </Show>
          </>
        )}
      </For>
    </div>
  );
}
