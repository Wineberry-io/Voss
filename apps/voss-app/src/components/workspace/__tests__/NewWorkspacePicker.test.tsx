import { afterEach, describe, expect, it, vi } from 'vitest';
import { render } from 'solid-js/web';
import { fireEvent, waitFor } from '@testing-library/dom';

const h = vi.hoisted(() => ({
  pickFolder: vi.fn(),
  listLayouts: vi.fn(),
}));

vi.mock('../../../project/projectStorage', () => ({
  pickFolder: h.pickFolder,
}));

vi.mock('../../../grid/layoutStorage', () => ({
  listLayouts: h.listLayouts,
}));

import NewWorkspacePicker, {
  COPY_CREATE_WORKSPACE,
  COPY_OPEN_FOLDER,
  COPY_START_EMPTY,
  COPY_UNTITLED_WORKSPACE,
} from '../NewWorkspacePicker';

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
  vi.clearAllMocks();
});

describe('NewWorkspacePicker — dismiss', () => {
  it('Escape dismisses the overlay', () => {
    const onDismiss = vi.fn();
    mount(() => (
      <NewWorkspacePicker
        onDismiss={onDismiss}
        onCreate={vi.fn()}
        onStartEmpty={vi.fn()}
      />
    ));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it('outside click dismisses the overlay', () => {
    const onDismiss = vi.fn();
    mount(() => (
      <NewWorkspacePicker
        onDismiss={onDismiss}
        onCreate={vi.fn()}
        onStartEmpty={vi.fn()}
      />
    ));
    fireEvent.click(document.querySelector('[data-new-workspace-backdrop]')!);
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});

describe('NewWorkspacePicker — Start empty', () => {
  it('Start empty submits name and accent color', () => {
    const onStartEmpty = vi.fn();
    const el = mount(() => (
      <NewWorkspacePicker
        onDismiss={vi.fn()}
        onCreate={vi.fn()}
        onStartEmpty={onStartEmpty}
      />
    ));
    fireEvent.click(
      el.querySelector('[data-new-workspace-start-empty]') as HTMLButtonElement,
    );
    expect(onStartEmpty).toHaveBeenCalledWith({
      name: COPY_UNTITLED_WORKSPACE,
      accentColor: 'blue',
    });
  });
});

describe('NewWorkspacePicker — Open folder', () => {
  it('Open folder picks a directory and enables Create workspace', async () => {
    h.pickFolder.mockResolvedValueOnce('/tmp/my-project');
    const onCreate = vi.fn();
    const el = mount(() => (
      <NewWorkspacePicker
        onDismiss={vi.fn()}
        onCreate={onCreate}
        onStartEmpty={vi.fn()}
      />
    ));

    fireEvent.click(
      el.querySelector('[data-new-workspace-open-folder]') as HTMLButtonElement,
    );

    await waitFor(() =>
      expect(el.querySelector('[data-new-workspace-folder]')?.textContent).toBe(
        '/tmp/my-project',
      ),
    );
    expect(h.pickFolder).toHaveBeenCalledTimes(1);
    expect(h.listLayouts).not.toHaveBeenCalled();

    const createBtn = el.querySelector(
      '[data-new-workspace-create]',
    ) as HTMLButtonElement;
    expect(createBtn.disabled).toBe(false);

    fireEvent.click(createBtn);
    expect(onCreate).toHaveBeenCalledWith({
      name: 'my-project',
      accentColor: 'blue',
      folderPath: '/tmp/my-project',
      layoutName: null,
    });
  });
});

describe('NewWorkspacePicker — Enter submit', () => {
  it('Enter submits when folder and name are valid', async () => {
    h.pickFolder.mockResolvedValueOnce('/tmp/demo');
    h.listLayouts.mockResolvedValueOnce([]);

    const onCreate = vi.fn();
    mount(() => (
      <NewWorkspacePicker
        onDismiss={vi.fn()}
        onCreate={onCreate}
        onStartEmpty={vi.fn()}
      />
    ));

    fireEvent.click(
      document.querySelector('[data-new-workspace-open-folder]') as HTMLButtonElement,
    );
    await waitFor(() => expect(h.pickFolder).toHaveBeenCalled());

    fireEvent.keyDown(document, { key: 'Enter' });
    expect(onCreate).toHaveBeenCalledWith({
      name: 'demo',
      accentColor: 'blue',
      folderPath: '/tmp/demo',
      layoutName: null,
    });
  });

  it('Create workspace stays disabled without a folder', () => {
    const el = mount(() => (
      <NewWorkspacePicker
        onDismiss={vi.fn()}
        onCreate={vi.fn()}
        onStartEmpty={vi.fn()}
      />
    ));
    const createBtn = el.querySelector(
      '[data-new-workspace-create]',
    ) as HTMLButtonElement;
    expect(createBtn.disabled).toBe(true);
    expect(createBtn.textContent?.trim()).toBe(COPY_CREATE_WORKSPACE);
    expect(
      el.querySelector('[data-new-workspace-open-folder]')?.textContent?.trim(),
    ).toBe(COPY_OPEN_FOLDER);
    expect(
      el.querySelector('[data-new-workspace-start-empty]')?.textContent?.trim(),
    ).toBe(COPY_START_EMPTY);
  });
});
