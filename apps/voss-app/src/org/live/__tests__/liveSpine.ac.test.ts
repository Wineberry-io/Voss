// V15-06 (VLIVE-08) — hermetic live-spine AC suite. Spawns a REAL
// `voss serve` (VOSS_SERVE_FAKE_TURN canned turn — no creds, no network) and
// drives the full spine: handshake → client construction → createSession →
// SSE subscription → events → follow-up → teardown label flip.
//
// GATED: default `vitest run` SKIPS this file (it spawns a real process).
// Run with `VOSS_AC_LIVE=1 npx vitest run src/org/live/__tests__/liveSpine.ac.test.ts`.
//
// Permission leg honesty (plan step 4): the canned turn never requests
// permission, so no permission.updated is fabricated into the real stream.
// The transport is proven by POSTing a reply for a known-absent id and
// asserting the server's stale-tolerant 200 — the in-pane gate behavior is
// covered by the Plan-04 ProtocolPane unit gate.

import { describe, it, expect, afterAll } from 'vitest';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { spawnHermeticServe, type HermeticServe } from './acSpawn';
import { connectLiveStream, liveLabel, __resetLiveStream } from '../sseClient';
import { __resetAttentionQueue } from '../../attention/attentionQueue';
import { __resetBridgeMaps } from '../../model/bridge';
import { replyPermission } from '../../../../../../sdk/typescript/src/client/permission';
import type { AgentEvent } from '../../../../../../sdk/typescript/src/client/sse';
import { subscribeToEvents } from '../../../../../../sdk/typescript/src/client/sse';
import { createVossClient } from '../../../../../../sdk/typescript/src/client/rest';

const STEP_TIMEOUT = 30_000; // every network wait bounded — CI fails fast
const SPAWN_TIMEOUT = 90_000; // cold .pyc compile can take ~45-60s

let serve: HermeticServe | undefined;
let client: ReturnType<typeof createVossClient> | undefined;
let sessionId = '';
let workdir = '';

describe.skipIf(process.env.VOSS_AC_LIVE !== '1')(
  'VLIVE-08 live spine (hermetic)',
  () => {
    afterAll(async () => {
      // T-V15-SC / T-V15-02: reap deterministically — no orphan survives.
      await serve?.kill();
      __resetLiveStream();
      __resetAttentionQueue();
      __resetBridgeMaps();
      if (workdir) rmSync(workdir, { recursive: true, force: true });
    });

    it(
      'spawns a real voss serve and completes the {port, token} handshake (VLIVE-01)',
      async () => {
        workdir = mkdtempSync(join(tmpdir(), 'voss-ac-spine-'));
        serve = await spawnHermeticServe(workdir);

        expect(serve.port).toBeGreaterThan(0);
        expect(serve.token.length).toBeGreaterThan(0);
      },
      SPAWN_TIMEOUT,
    );

    it(
      'builds the client and creates a real server session (VLIVE-02)',
      async () => {
        client = createVossClient(
          `http://127.0.0.1:${serve!.port}`,
          serve!.token,
        );

        sessionId = await client.createSession(workdir);
        expect(typeof sessionId).toBe('string');
        expect(sessionId.length).toBeGreaterThan(0);

        // The honest list mirror sees it (VLIVE-06 transport).
        const sessions = await client.listSessions();
        expect(sessions.map((s) => s.id)).toContain(sessionId);
      },
      STEP_TIMEOUT,
    );

    it(
      'streams real §6 events for a posted turn; liveLabel flips live→snapshot (VLIVE-03)',
      async () => {
        const events: AgentEvent[] = [];
        let sawIdle: (() => void) | undefined;
        const idle = new Promise<void>((resolve) => {
          sawIdle = resolve;
        });

        const handle = connectLiveStream({
          sessionId,
          stream: subscribeToEvents(
            `http://127.0.0.1:${serve!.port}`,
            sessionId,
            serve!.token,
          ),
          cardId: sessionId,
          onEvent: (ev) => {
            events.push(ev);
            if (ev.type === 'session.idle') sawIdle?.();
          },
        });

        expect(liveLabel()).toBe('live');

        const accepted = await client!.postMessage(
          sessionId,
          'do something small',
        );
        expect(accepted).toBeTruthy(); // 202 body

        // Bounded wait for the canned turn to finish (session.idle terminal).
        await Promise.race([
          idle,
          new Promise((_, reject) =>
            setTimeout(
              () => reject(new Error(`no session.idle within ${STEP_TIMEOUT}ms`)),
              STEP_TIMEOUT,
            ),
          ),
        ]);

        const types = events.map((e) => e.type);
        expect(types.length).toBeGreaterThan(0);
        expect(types).toContain('user');
        expect(types).toContain('final');
        expect(types).toContain('session.idle');

        handle.abort();
        expect(liveLabel()).toBe('snapshot');
      },
      STEP_TIMEOUT * 2,
    );

    it(
      'permission transport: a reply POST for an absent id is answered (stale-tolerant 200)',
      async () => {
        // Honest leg: the canned turn never gates, so prove the authed
        // transport only — replyPermission resolves on the server's
        // {v:1, status:"stale"} 200 for an unknown id.
        await expect(
          replyPermission(client!, sessionId, {
            id: 'ac-absent-id',
            choice: 'a',
          }),
        ).resolves.toBeUndefined();
      },
      STEP_TIMEOUT,
    );

    it(
      'a follow-up postMessage on the same session is accepted (VLIVE-02 follow-up)',
      async () => {
        const accepted = await client!.postMessage(
          sessionId,
          'follow up',
        );
        expect(accepted).toBeTruthy();
      },
      STEP_TIMEOUT,
    );
  },
);
