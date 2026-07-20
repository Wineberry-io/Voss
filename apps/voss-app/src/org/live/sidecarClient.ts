import { Channel, invoke } from '@tauri-apps/api/core';

import type { AgentEvent } from '../../../../../sdk/typescript/src/client/sse';
import type {
  AcceptedResponse,
  CostInfo,
  DoctorReport,
  SavedSession,
  SessionInfo,
} from '../../../../../sdk/typescript/src/client/rest';
import type { PermissionChoice } from '../../../../../sdk/typescript/src/client/permission';

export interface SidecarHandle {
  sidecarId: string;
}

type SidecarOperation =
  | { kind: 'create_session' }
  | { kind: 'list_sessions' }
  | { kind: 'list_saved' }
  | { kind: 'get_session'; session_id: string }
  | { kind: 'delete_session'; session_id: string }
  | { kind: 'post_message'; session_id: string; text: string; mode: string }
  | { kind: 'abort_session'; session_id: string }
  | { kind: 'get_cost'; session_id: string }
  | { kind: 'doctor' }
  | { kind: 'reply_permission'; session_id: string; id: string; choice: string }
  | { kind: 'memory'; query?: string; top_k: number }
  | { kind: 'get_swarm'; swarm_id: string }
  | {
      kind: 'create_swarm';
      goal: string;
      builders: number;
      roster?: Array<Record<string, unknown>>;
    }
  | { kind: 'run_swarm'; swarm_id: string };

export async function startVossServe(cwd: string): Promise<SidecarHandle> {
  return invoke<SidecarHandle>('start_voss_serve', { cwd });
}

export async function callSidecar<T>(
  sidecarId: string,
  operation: SidecarOperation,
): Promise<T> {
  return invoke<T>('call_voss_sidecar', { sidecarId, operation });
}

function sessionsFrom(value: unknown): SessionInfo[] {
  if (Array.isArray(value)) return value as SessionInfo[];
  if (
    typeof value === 'object' &&
    value !== null &&
    Array.isArray((value as { sessions?: unknown }).sessions)
  ) {
    return (value as { sessions: SessionInfo[] }).sessions;
  }
  throw new Error('invalid sessions response');
}

export interface SidecarVossClient {
  createSession(cwd?: string): Promise<string>;
  listSessions(): Promise<SessionInfo[]>;
  listSaved(cwd?: string): Promise<SavedSession[]>;
  getSession(sessionId: string): Promise<SessionInfo>;
  deleteSession(sessionId: string): Promise<void>;
  postMessage(
    sessionId: string,
    text: string,
    mode?: string,
  ): Promise<AcceptedResponse>;
  abort(sessionId: string): Promise<void>;
  getCost(sessionId: string): Promise<CostInfo>;
  doctor(cwd?: string): Promise<DoctorReport>;
}

export function createSidecarVossClient(sidecarId: string): SidecarVossClient {
  return {
    async createSession(): Promise<string> {
      const value = await callSidecar<{ id?: unknown }>(sidecarId, {
        kind: 'create_session',
      });
      if (typeof value.id !== 'string') throw new Error('invalid session response');
      return value.id;
    },
    async listSessions(): Promise<SessionInfo[]> {
      return sessionsFrom(
        await callSidecar<unknown>(sidecarId, { kind: 'list_sessions' }),
      );
    },
    async listSaved(): Promise<SavedSession[]> {
      return sessionsFrom(
        await callSidecar<unknown>(sidecarId, { kind: 'list_saved' }),
      ) as SavedSession[];
    },
    getSession: (sessionId) =>
      callSidecar<SessionInfo>(sidecarId, {
        kind: 'get_session',
        session_id: sessionId,
      }),
    async deleteSession(sessionId): Promise<void> {
      await callSidecar(sidecarId, {
        kind: 'delete_session',
        session_id: sessionId,
      });
    },
    postMessage: (sessionId, text, mode = 'plan') =>
      callSidecar<AcceptedResponse>(sidecarId, {
        kind: 'post_message',
        session_id: sessionId,
        text,
        mode,
      }),
    async abort(sessionId): Promise<void> {
      await callSidecar(sidecarId, {
        kind: 'abort_session',
        session_id: sessionId,
      });
    },
    getCost: (sessionId) =>
      callSidecar<CostInfo>(sidecarId, {
        kind: 'get_cost',
        session_id: sessionId,
      }),
    doctor: () => callSidecar<DoctorReport>(sidecarId, { kind: 'doctor' }),
  };
}

export async function replySidecarPermission(
  sidecarId: string,
  sessionId: string,
  id: string,
  choice: PermissionChoice,
): Promise<void> {
  await callSidecar(sidecarId, {
    kind: 'reply_permission',
    session_id: sessionId,
    id,
    choice,
  });
}

type StreamMessage =
  | { type: 'event'; event: AgentEvent }
  | { type: 'end' }
  | { type: 'error'; message: string };

export async function* subscribeSidecarEvents(
  sidecarId: string,
  sessionId: string,
  signal?: AbortSignal,
): AsyncGenerator<AgentEvent> {
  const channel = new Channel<StreamMessage>();
  const queue: StreamMessage[] = [];
  let wake: (() => void) | null = null;
  channel.onmessage = (message) => {
    queue.push(message);
    wake?.();
    wake = null;
  };

  const streamId = await invoke<string>('subscribe_voss_events', {
    sidecarId,
    sessionId,
    onEvent: channel,
  });
  const abort = () => {
    void invoke('unsubscribe_voss_events', { streamId });
    wake?.();
    wake = null;
  };
  signal?.addEventListener('abort', abort, { once: true });

  try {
    while (!signal?.aborted) {
      if (queue.length === 0) {
        await new Promise<void>((resolve) => {
          wake = resolve;
        });
        if (signal?.aborted) break;
      }
      const message = queue.shift();
      if (!message) continue;
      if (message.type === 'event') yield message.event;
      if (message.type === 'end') break;
      if (message.type === 'error') throw new Error(message.message);
    }
  } finally {
    signal?.removeEventListener('abort', abort);
    await invoke('unsubscribe_voss_events', { streamId }).catch(() => undefined);
  }
}
