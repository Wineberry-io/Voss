import { batch, createSignal, type Accessor } from 'solid-js';
import type { LayoutPreset } from '../canvas/arrange';
import {
  CURRENT_WORKSPACES_VERSION,
  DEFAULT_ACCENT_COLOR,
  DEFAULT_WORKSPACE_ID,
  loadWorkspacesIndex,
  saveWorkspacesIndex,
  type WorkspaceEntry,
  type WorkspacesIndex,
} from './workspaceStorage';

/** Runtime workspace record — same wire shape as `WorkspaceEntry`. */
export type WorkspaceRecord = WorkspaceEntry;

/** UXP-08 close-guard metadata for tab UI (last workspace cannot close). */
export type WorkspaceCloseGuard = {
  canClose: boolean;
  isLastWorkspace: boolean;
};

export type WorkspaceStore = {
  workspaces: Accessor<readonly WorkspaceRecord[]>;
  activeId: Accessor<string | null>;
  load: () => Promise<void>;
  persist: () => Promise<void>;
  add: (input: {
    id?: string;
    name: string;
    projectPath?: string | null;
    accentColor?: string;
  }) => WorkspaceRecord;
  activate: (id: string) => void;
  rename: (id: string, name: string) => void;
  setAccentColor: (id: string, accentColor: string) => void;
  reorder: (fromIndex: number, toIndex: number) => void;
  setPinnedProfile: (id: string, profileId: string | null) => void;
  setActiveLayoutPreset: (
    id: string,
    preset: LayoutPreset | 'custom' | null,
  ) => void;
  setProjectPath: (id: string, projectPath: string | null) => void;
  remove: (id: string) => void;
  closeGuardFor: (id: string) => WorkspaceCloseGuard;
  canClose: (id: string) => boolean;
  snapshotIndex: () => WorkspacesIndex;
};

function newWorkspaceId(): string {
  return crypto.randomUUID();
}

function reindexOrders(workspaces: WorkspaceRecord[]): WorkspaceRecord[] {
  return workspaces.map((w, i) => ({ ...w, order: i }));
}

function sortByOrder(workspaces: WorkspaceRecord[]): WorkspaceRecord[] {
  return reindexOrders(
    workspaces.slice().sort((a, b) => a.order - b.order),
  );
}

function findWorkspace(
  workspaces: readonly WorkspaceRecord[],
  id: string,
): WorkspaceRecord | undefined {
  return workspaces.find((w) => w.id === id);
}

/** Compute UXP-08 close-guard metadata for a workspace tab. */
export function closeGuardFor(
  workspaces: readonly WorkspaceRecord[],
  _id: string,
): WorkspaceCloseGuard {
  const isLastWorkspace = workspaces.length <= 1;
  return { canClose: !isLastWorkspace, isLastWorkspace };
}

export function createWorkspaceStore(
  initial?: WorkspacesIndex,
): WorkspaceStore {
  const seed = initial ?? {
    version: CURRENT_WORKSPACES_VERSION,
    activeWorkspaceId: DEFAULT_WORKSPACE_ID,
    workspaces: [
      {
        id: DEFAULT_WORKSPACE_ID,
        name: 'Workspace',
        accentColor: DEFAULT_ACCENT_COLOR,
        order: 0,
      },
    ],
  };

  const [workspaces, setWorkspaces] = createSignal<WorkspaceRecord[]>(
    sortByOrder(seed.workspaces),
  );
  const [activeId, setActiveId] = createSignal<string | null>(
    seed.activeWorkspaceId ?? seed.workspaces[0]?.id ?? null,
  );

  const snapshotIndex = (): WorkspacesIndex => ({
    version: CURRENT_WORKSPACES_VERSION,
    activeWorkspaceId: activeId(),
    workspaces: workspaces().map((w) => ({ ...w })),
  });

  const persist = async () => {
    await saveWorkspacesIndex(snapshotIndex());
  };

  const load = async () => {
    let index: WorkspacesIndex;
    try {
      index = await loadWorkspacesIndex();
    } catch {
      return;
    }
    if (!index?.workspaces?.length) return;
    setWorkspaces(sortByOrder(index.workspaces));
    const active =
      index.activeWorkspaceId &&
      index.workspaces.some((w) => w.id === index.activeWorkspaceId)
        ? index.activeWorkspaceId
        : (index.workspaces[0]?.id ?? null);
    setActiveId(active);
  };

  const add: WorkspaceStore['add'] = (input) => {
    const id = input.id ?? newWorkspaceId();
    const entry: WorkspaceRecord = {
      id,
      name: input.name,
      projectPath: input.projectPath ?? null,
      accentColor: input.accentColor ?? DEFAULT_ACCENT_COLOR,
      order: workspaces().length,
    };
    setWorkspaces((prev) => reindexOrders([...prev, entry]));
    setActiveId(id);
    return entry;
  };

  const activate = (id: string) => {
    if (!findWorkspace(workspaces(), id)) return;
    setActiveId(id);
  };

  const rename = (id: string, name: string) => {
    setWorkspaces((prev) =>
      prev.map((w) => (w.id === id ? { ...w, name } : w)),
    );
  };

  const setAccentColor = (id: string, accentColor: string) => {
    setWorkspaces((prev) =>
      prev.map((w) => (w.id === id ? { ...w, accentColor } : w)),
    );
  };

  const reorder = (fromIndex: number, toIndex: number) => {
    setWorkspaces((prev) => {
      const sorted = sortByOrder(prev);
      if (
        fromIndex < 0 ||
        toIndex < 0 ||
        fromIndex >= sorted.length ||
        toIndex >= sorted.length
      ) {
        return sorted;
      }
      const next = sorted.slice();
      const [moved] = next.splice(fromIndex, 1);
      next.splice(toIndex, 0, moved);
      return reindexOrders(next);
    });
  };

  const setPinnedProfile = (id: string, profileId: string | null) => {
    setWorkspaces((prev) =>
      prev.map((w) =>
        w.id === id
          ? {
              ...w,
              pinnedProfile: profileId ?? undefined,
            }
          : w,
      ),
    );
  };

  const setActiveLayoutPreset = (
    id: string,
    preset: LayoutPreset | 'custom' | null,
  ) => {
    setWorkspaces((prev) =>
      prev.map((w) =>
        w.id === id
          ? {
              ...w,
              activeLayoutPreset:
                preset && preset !== 'custom' ? preset : undefined,
            }
          : w,
      ),
    );
  };

  const setProjectPath = (id: string, projectPath: string | null) => {
    setWorkspaces((prev) =>
      prev.map((w) =>
        w.id === id
          ? {
              ...w,
              projectPath: projectPath ?? undefined,
            }
          : w,
      ),
    );
  };

  const remove = (id: string) => {
    if (!closeGuardFor(workspaces(), id).canClose) return;
    batch(() => {
      setWorkspaces((prev) => reindexOrders(prev.filter((w) => w.id !== id)));
      setActiveId((current) => {
        if (current !== id) return current;
        return workspaces()[0]?.id ?? null;
      });
    });
  };

  return {
    workspaces,
    activeId,
    load,
    persist,
    add,
    activate,
    rename,
    setAccentColor,
    reorder,
    setPinnedProfile,
    setActiveLayoutPreset,
    setProjectPath,
    remove,
    closeGuardFor: (id) => closeGuardFor(workspaces(), id),
    canClose: (id) => closeGuardFor(workspaces(), id).canClose,
    snapshotIndex,
  };
}
