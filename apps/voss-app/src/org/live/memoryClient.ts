// VADE2-11 — typed client for the loopback server's GET /memory route.
//
import { callSidecar } from './sidecarClient';

export interface MemoryHit {
  source: string;
  locator: string;
  score: number;
  excerpt: string;
  session_id: string | null;
  ts: string | null;
  line_start: number | null;
  line_end: number | null;
}

export interface MemoryResponse {
  v: number;
  summary: string;
  query: string | null;
  hits: MemoryHit[];
}

/**
 * Fetch the memory summary (and recall hits when `q` is given) from the
 * `voss serve` sidecar at `baseUrl`. Throws on a non-OK response.
 */
export async function fetchMemory(
  sidecarId: string,
  q?: string,
  topK = 5,
): Promise<MemoryResponse> {
  return callSidecar<MemoryResponse>(sidecarId, {
    kind: 'memory',
    query: q?.trim() || undefined,
    top_k: topK,
  });
}
