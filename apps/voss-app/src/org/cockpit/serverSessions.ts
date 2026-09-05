// V15-05 (VLIVE-06) — "Server sessions" list + attach. Mirrors the
// sseClient.ts module pattern: module-level signal + exported functions +
// __reset for test isolation.
//
// D-05: the list is an honest mirror of GET /session — newest first, NO
// source filtering (CLI `voss chat` sessions included). The live-session
// shape is {id, cwd, model, title, busy} (harness/server/app.py) — no
// timestamp — so accessors are defensive against the opaque SessionInfo (A1):
// title falls back to id, age renders blank without a created/updated field.
//
// D-06: attach ≡ start — the attached session registers as a native cockpit
// card (Bridge A) and opens a structured pane via the App openAttachedPane
// seam. T-V15-12: forward events only; PROTOCOL v1 has no history endpoint,
// so attach performs NO backfill fetch and the UI never fakes one.

import { createSignal } from 'solid-js';

import type {
  SessionInfo,
} from '../../../../../sdk/typescript/src/client/rest';
import type { SidecarVossClient } from '../live/sidecarClient';
import { registerNativeCard } from '../model/bridge';

const [serverSessions, setServerSessions] = createSignal<SessionInfo[]>([]);
const [sessionsLoading, setSessionsLoading] = createSignal(false);

/** Required id ('' for malformed rows — callers skip those). */
export function sessionId(info: SessionInfo): string {
  return typeof info.id === 'string' ? info.id : '';
}

/** Display title; falls back to the id (live sessions may carry title:null). */
export function sessionTitle(info: SessionInfo): string {
  if (typeof info.title === 'string' && info.title.length > 0)
    return info.title;
  return sessionId(info);
}

/**
 * Relative age ("3m" / "2h" / "1d") from an updated_at/created_at-like field
 * (epoch seconds, epoch ms, or ISO string); blank when absent — live
 * GET /session rows carry no timestamp today.
 */
export function sessionAgeLabel(info: SessionInfo): string {
  const ts =
    (info as Record<string, unknown>).updated_at ??
    (info as Record<string, unknown>).created_at;
  let ms: number | null = null;
  if (typeof ts === 'number') ms = ts > 1e12 ? ts : ts * 1000;
  else if (typeof ts === 'string') {
    const parsed = Date.parse(ts);
    if (!Number.isNaN(parsed)) ms = parsed;
  }
  if (ms === null) return '';
  const minutes = Math.floor(Math.max(0, Date.now() - ms) / 60_000);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

/** Newest first (D-05): sort by timestamp when present, else reverse the
 *  server's oldest→newest insertion order. Immutable. */
function sortNewestFirst(list: SessionInfo[]): SessionInfo[] {
  const ts = (info: SessionInfo): number | null => {
    const raw =
      (info as Record<string, unknown>).updated_at ??
      (info as Record<string, unknown>).created_at;
    if (typeof raw === 'number') return raw;
    if (typeof raw === 'string') {
      const parsed = Date.parse(raw);
      return Number.isNaN(parsed) ? null : parsed;
    }
    return null;
  };
  if (list.some((s) => ts(s) !== null)) {
    return [...list].sort((a, b) => (ts(b) ?? 0) - (ts(a) ?? 0));
  }
  return [...list].reverse();
}

/** Populate the list from GET /session; degrade silently on error. */
export async function refreshSessions(client: SidecarVossClient): Promise<void> {
  setSessionsLoading(true);
  try {
    setServerSessions(sortNewestFirst(await client.listSessions()));
  } catch {
    // Server gone / decode error — keep the previous list, never throw.
  } finally {
    setSessionsLoading(false);
  }
}

export interface AttachSessionArgs {
  cwd: string;
  sessionId: string;
  /** Respawns the sidecar if cold (post-restart) — Plan 02 ensureVossClient. */
  ensureClient: (
    cwd: string,
  ) => Promise<{ sidecarId: string; client: SidecarVossClient }>;
  /** Plan 03 App seam: D-02 split + nativeSessionByPaneId bind. */
  openAttachedPane: (record: {
    sessionId: string;
    sidecarId: string;
    client: SidecarVossClient;
  }) => void;
}

/**
 * Attach a structured pane onto an existing server session (D-06: attached ≡
 * started). Ensures a live client first (respawn-if-cold, T-V15-08), then
 * registers the native card and opens the pane. Forward events only — no
 * history fetch (T-V15-12).
 */
export async function attachSession(args: AttachSessionArgs): Promise<void> {
  const { sidecarId, client } = await args.ensureClient(args.cwd);
  registerNativeCard(args.sessionId, args.sessionId);
  args.openAttachedPane({
    sessionId: args.sessionId,
    sidecarId,
    client,
  });
}

export { serverSessions, sessionsLoading };

/** Test-only reset (mirrors __resetLiveStream). */
export function __resetServerSessions(): void {
  setServerSessions([]);
  setSessionsLoading(false);
}
