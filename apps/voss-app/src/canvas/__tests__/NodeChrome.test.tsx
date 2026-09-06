import { afterEach, describe, expect, it, vi } from 'vitest';
import { render } from 'solid-js/web';
import { createSignal } from 'solid-js';
import NodeMenu from '../NodeMenu';
import NodeCloseBanner from '../NodeCloseBanner';

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

function menuHandlers() {
  return { onFork: vi.fn(), onSplitRight: vi.fn(), onSplitBelow: vi.fn(), onRequestClose: vi.fn(), onDismiss: vi.fn() };
}

describe('NodeMenu', () => {
  it('lists fork, split right, split below, close and dismisses before running an item', () => {
    const h = menuHandlers();
    const el = mount(() => <NodeMenu {...h} />);
    const items = [...el.querySelectorAll('[role="menuitem"]')].map((b) => b.textContent);
    expect(items).toEqual(['Fork pane⌘D', 'Split right⌘\\', 'Split below⌘⇧\\', 'Close pane⌘W']);
    (el.querySelectorAll('[role="menuitem"]')[2] as HTMLButtonElement).click();
    expect(h.onDismiss).toHaveBeenCalledTimes(1);
    expect(h.onSplitBelow).toHaveBeenCalledTimes(1);
    (el.querySelectorAll('[role="menuitem"]')[3] as HTMLButtonElement).click();
    expect(h.onRequestClose).toHaveBeenCalledTimes(1);
    (el.querySelectorAll('[role="menuitem"]')[0] as HTMLButtonElement).click();
    expect(h.onFork).toHaveBeenCalledTimes(1);
    (el.querySelectorAll('[role="menuitem"]')[1] as HTMLButtonElement).click();
    expect(h.onSplitRight).toHaveBeenCalledTimes(1);
  });

  it('Escape and a click outside dismiss; a click inside does not', () => {
    const h = menuHandlers();
    const el = mount(() => <NodeMenu {...h} />);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(h.onDismiss).toHaveBeenCalledTimes(1);
    (el.querySelector('[role="menu"]') as HTMLElement).dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(h.onDismiss).toHaveBeenCalledTimes(1);
    document.body.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(h.onDismiss).toHaveBeenCalledTimes(2);
  });
});

describe('NodeCloseBanner', () => {
  it('names the process and the buttons confirm or keep open', () => {
    const onConfirm = vi.fn();
    const onKeepOpen = vi.fn();
    const el = mount(() => <NodeCloseBanner process="vim" active onConfirm={onConfirm} onKeepOpen={onKeepOpen} />);
    expect(el.querySelector('[role="alertdialog"]')?.textContent).toContain('"vim" is running. Close anyway?');
    const [keep, close] = [...el.querySelectorAll('button')];
    keep.click();
    close.click();
    expect(onKeepOpen).toHaveBeenCalledTimes(1);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('Enter confirms and Escape keeps open only while active; other keys pass through', () => {
    const onConfirm = vi.fn();
    const onKeepOpen = vi.fn();
    const [active, setActive] = createSignal(false);
    mount(() => <NodeCloseBanner process="top" active={active()} onConfirm={onConfirm} onKeepOpen={onKeepOpen} />);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    expect(onConfirm).not.toHaveBeenCalled();
    setActive(true);
    const other = new KeyboardEvent('keydown', { key: 'x', cancelable: true });
    document.dispatchEvent(other);
    expect(other.defaultPrevented).toBe(false);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(onKeepOpen).toHaveBeenCalledTimes(1);
  });
});
