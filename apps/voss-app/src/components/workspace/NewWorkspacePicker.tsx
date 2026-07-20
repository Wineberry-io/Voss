import {
  For,
  createSignal,
  onCleanup,
  onMount,
} from 'solid-js';
import { pickFolder } from '../../project/projectStorage';
import {
  COPY_NEW_WORKSPACE,
  WORKSPACE_ACCENT_COLORS,
  workspaceAccentVar,
  type WorkspaceAccentColor,
} from './WorkspaceTabBar';
import './workspace.css';

export const COPY_OPEN_FOLDER = 'Open folder';
export const COPY_START_EMPTY = 'Start empty';
export const COPY_CREATE_WORKSPACE = 'Create workspace';
export const COPY_WORKSPACE_NAME_PLACEHOLDER = 'workspace name';
export const COPY_SHELL_LABEL = 'Shell';
export const COPY_UNTITLED_WORKSPACE = 'Untitled workspace';

export type NewWorkspacePickerCreatePayload = {
  name: string;
  accentColor: string;
  folderPath: string | null;
  layoutName: string | null;
};

export type NewWorkspacePickerStartEmptyPayload = {
  name: string;
  accentColor: string;
};

export type NewWorkspacePickerProps = {
  onDismiss: () => void;
  onCreate: (payload: NewWorkspacePickerCreatePayload) => void | Promise<void>;
  onStartEmpty: (
    payload: NewWorkspacePickerStartEmptyPayload,
  ) => void | Promise<void>;
  defaultShell?: string;
};

function basename(path: string): string {
  return path.split('/').filter(Boolean).pop() ?? path;
}

function focusableIn(root: HTMLElement): HTMLElement[] {
  return [
    ...root.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ].filter((el) => !el.hasAttribute('disabled') && el.offsetParent !== null);
}

export default function NewWorkspacePicker(props: NewWorkspacePickerProps) {
  let panelRef: HTMLDivElement | undefined;
  let nameInputRef: HTMLInputElement | undefined;

  const [name, setName] = createSignal(COPY_UNTITLED_WORKSPACE);
  const [folderPath, setFolderPath] = createSignal<string | null>(null);
  const [accentColor, setAccentColor] = createSignal<WorkspaceAccentColor>('blue');
  const [openingFolder, setOpeningFolder] = createSignal(false);

  const shellLabel = () => props.defaultShell ?? '/bin/zsh';
  const trimmedName = () => name().trim();
  const canCreate = () => trimmedName().length > 0 && folderPath() !== null;
  const canStartEmpty = () => trimmedName().length > 0;

  const dismiss = () => props.onDismiss();

  const submitCreate = () => {
    if (!canCreate()) return;
    void props.onCreate({
      name: trimmedName(),
      accentColor: accentColor(),
      folderPath: folderPath(),
      layoutName: null,
    });
  };

  const submitStartEmpty = () => {
    if (!canStartEmpty()) return;
    void props.onStartEmpty({
      name: trimmedName(),
      accentColor: accentColor(),
    });
  };

  const onOpenFolder = async () => {
    if (openingFolder()) return;
    setOpeningFolder(true);
    try {
      const picked = await pickFolder();
      if (!picked) return;
      setFolderPath(picked);
      if (name() === COPY_UNTITLED_WORKSPACE || !name().trim()) {
        setName(basename(picked));
      }
    } finally {
      setOpeningFolder(false);
    }
  };

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      dismiss();
      return;
    }
    if (e.key === 'Enter' && canCreate()) {
      e.preventDefault();
      submitCreate();
      return;
    }
    if (e.key !== 'Tab' || !panelRef) return;
    const items = focusableIn(panelRef);
    if (items.length === 0) return;
    const first = items[0];
    const last = items[items.length - 1];
    const active = document.activeElement as HTMLElement | null;
    if (e.shiftKey && active === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && active === last) {
      e.preventDefault();
      first.focus();
    }
  };

  const onBackdropClick = (e: MouseEvent) => {
    if (panelRef && !panelRef.contains(e.target as Node)) {
      dismiss();
    }
  };

  onMount(() => {
    document.addEventListener('keydown', onKeyDown, true);
    queueMicrotask(() => nameInputRef?.focus());
  });
  onCleanup(() => {
    document.removeEventListener('keydown', onKeyDown, true);
  });

  return (
    <div
      class="new-workspace-backdrop"
      data-new-workspace-backdrop=""
      onClick={onBackdropClick}
    >
      <div
        ref={panelRef}
        class="new-workspace-picker"
        data-new-workspace-picker=""
        role="dialog"
        aria-modal="true"
        aria-label={COPY_NEW_WORKSPACE}
        onClick={(e) => e.stopPropagation()}
      >
        <header class="new-workspace-picker__header">{COPY_NEW_WORKSPACE}</header>

        <div class="new-workspace-picker__body">
          <label class="new-workspace-picker__row">
            <span class="new-workspace-picker__label">Name</span>
            <input
              ref={nameInputRef}
              class="new-workspace-picker__input"
              data-new-workspace-name=""
              type="text"
              placeholder={COPY_WORKSPACE_NAME_PLACEHOLDER}
              value={name()}
              onInput={(e) => setName(e.currentTarget.value)}
            />
          </label>

          <div class="new-workspace-picker__row">
            <span class="new-workspace-picker__label">Folder</span>
            <span class="new-workspace-picker__value" data-new-workspace-folder="">
              {folderPath() ?? '—'}
            </span>
            <button
              type="button"
              class="new-workspace-picker__action"
              data-new-workspace-open-folder=""
              disabled={openingFolder()}
              onClick={() => void onOpenFolder()}
            >
              {COPY_OPEN_FOLDER}
            </button>
          </div>

          <div class="new-workspace-picker__row">
            <span class="new-workspace-picker__label">{COPY_SHELL_LABEL}</span>
            <span class="new-workspace-picker__value" data-new-workspace-shell="">
              {shellLabel()}
            </span>
          </div>

          <div class="new-workspace-picker__colors">
            <For each={[...WORKSPACE_ACCENT_COLORS]}>
              {(color) => (
                <button
                  type="button"
                  class="workspace-color-dot"
                  data-new-workspace-color={color}
                  data-selected={accentColor() === color ? 'true' : 'false'}
                  aria-label={color}
                  style={{
                    '--workspace-dot-color': workspaceAccentVar(color),
                  }}
                  onClick={() => setAccentColor(color)}
                />
              )}
            </For>
          </div>
        </div>

        <footer class="new-workspace-picker__footer">
          <button
            type="button"
            class="new-workspace-picker__secondary"
            data-new-workspace-start-empty=""
            disabled={!canStartEmpty()}
            onClick={submitStartEmpty}
          >
            {COPY_START_EMPTY}
          </button>
          <button
            type="button"
            class="new-workspace-picker__primary"
            data-new-workspace-create=""
            disabled={!canCreate()}
            onClick={submitCreate}
          >
            {COPY_CREATE_WORKSPACE}
          </button>
        </footer>
      </div>
    </div>
  );
}
