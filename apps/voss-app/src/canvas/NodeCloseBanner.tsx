import { onCleanup, onMount } from 'solid-js';

/**
 * Close-confirm row under a node header when its foreground process is busy.
 * Enter / "Close anyway" confirms, Escape / "Keep open" dismisses; any other
 * key passes through to the PTY.
 */
export default function NodeCloseBanner(props: {
  process: string;
  onConfirm: () => void;
  onKeepOpen: () => void;
}) {
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      e.stopPropagation();
      props.onConfirm();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      props.onKeepOpen();
    }
  };
  onMount(() => document.addEventListener('keydown', onKey, true));
  onCleanup(() => document.removeEventListener('keydown', onKey, true));

  return (
    <div
      class="font-ui bg-bg-3"
      role="alertdialog"
      style={{
        display: 'flex',
        'align-items': 'center',
        width: '100%',
        height: '22px',
        padding: '0 10px',
        'border-bottom': '1px solid var(--border)',
        'font-size': '11px',
        'font-weight': 400,
      }}
    >
      <span class="text-accent-red" style={{ 'font-size': '8px' }} aria-hidden="true">
        ●
      </span>
      <span class="text-fg-1" style={{ 'margin-left': '8px' }}>
        "{props.process}" is running. Close anyway?
      </span>
      <span style={{ flex: 1 }} />
      <button
        type="button"
        class="text-fg-0"
        style={{ background: 'transparent', border: 'none', padding: '0 8px', cursor: 'default', 'font-size': '11px' }}
        onClick={() => props.onKeepOpen()}
      >
        Keep open
      </button>
      <button
        type="button"
        class="text-accent-red"
        style={{ background: 'transparent', border: 'none', padding: '0 8px', cursor: 'default', 'font-size': '11px' }}
        onClick={() => props.onConfirm()}
      >
        Close anyway
      </button>
    </div>
  );
}
