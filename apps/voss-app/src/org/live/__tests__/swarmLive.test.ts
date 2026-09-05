// V24 swarm surface — swarm.* SSE ingestion into the live store.

import { afterEach, describe, expect, it } from 'vitest';
import {
  ingestSwarmEvent,
  swarmAssignments,
  swarmGates,
  swarmOperatorNeeds,
  swarmComplete,
  swarmCandidateReady,
  swarmCandidatesReady,
  swarmLiveEdges,
  swarmEventSeq,
  __resetSwarmLive,
} from '../swarmLive';

afterEach(() => __resetSwarmLive());

describe('ingestSwarmEvent', () => {
  it('ignores non-swarm events', () => {
    ingestSwarmEvent({ type: 'budget.updated', spent: 1 });
    ingestSwarmEvent(null);
    ingestSwarmEvent({ nope: true });
    expect(Object.keys(swarmAssignments())).toHaveLength(0);
    expect(swarmLiveEdges()).toHaveLength(0);
  });

  it('records assign as the builder↔task binding + a live edge', () => {
    ingestSwarmEvent(
      {
        type: 'swarm.assign',
        swarm_id: 'sw1',
        task_id: 't1',
        session_id: 's-b1',
        owned_files: ['a.py'],
        role: 'builder-1',
      },
      1000,
    );
    expect(swarmAssignments().t1).toEqual({
      taskId: 't1',
      sessionId: 's-b1',
      role: 'builder-1',
      ownedFiles: ['a.py'],
    });
    expect(swarmLiveEdges()).toHaveLength(1);
    expect(swarmLiveEdges()[0]).toMatchObject({
      type: 'assign',
      source: 'sse_event:swarm.assign',
      timestamp: 1000,
    });
  });

  it('records gate, needs_operator, and complete', () => {
    ingestSwarmEvent({ type: 'swarm.gate', swarm_id: 'sw1', task_id: 't2', gate_type: 'reviewer_reject', detail: 'no' });
    ingestSwarmEvent({ type: 'swarm.needs_operator', swarm_id: 'sw1', task_id: 't1', session_id: 's-b1', tool_name: 'fs_write', path: 'c.py' });
    ingestSwarmEvent({ type: 'swarm.complete', swarm_id: 'sw1', task_count: 2, summary: 'done' });

    expect(swarmGates().t2?.gate_type).toBe('reviewer_reject');
    expect(swarmOperatorNeeds().t1?.path).toBe('c.py');
    expect(swarmComplete().sw1?.task_count).toBe(2);
  });

  it('records preserved candidates without marking the swarm complete', () => {
    ingestSwarmEvent({
      type: 'swarm.candidate_ready',
      swarm_id: 'sw1',
      task_id: 't1',
      role: 'builder-1',
      branch: 'swarm/sw1/builder-1',
      worktree: '/tmp/wt',
      head: 'deadbeef',
    });
    ingestSwarmEvent({
      type: 'swarm.candidates_ready',
      swarm_id: 'sw1',
      candidate_count: 1,
    });

    expect(swarmCandidateReady().t1?.head).toBe('deadbeef');
    expect(swarmCandidatesReady().sw1?.candidate_count).toBe(1);
    expect(swarmComplete().sw1).toBeUndefined();
  });

  it('clears an operator escalation when its task reports worker_done', () => {
    ingestSwarmEvent({ type: 'swarm.needs_operator', swarm_id: 'sw1', task_id: 't1', session_id: 's-b1', tool_name: 'fs_write', path: 'c.py' });
    expect(swarmOperatorNeeds().t1).toBeDefined();
    // A different task finishing must NOT clear t1's escalation.
    ingestSwarmEvent({ type: 'swarm.worker_done', swarm_id: 'sw1', task_id: 't2', session_id: 's-b2' });
    expect(swarmOperatorNeeds().t1).toBeDefined();
    // t1 finishing resolves its own escalation.
    ingestSwarmEvent({ type: 'swarm.worker_done', swarm_id: 'sw1', task_id: 't1', session_id: 's-b1' });
    expect(swarmOperatorNeeds().t1).toBeUndefined();
  });

  it('bounds the live-edge ring', () => {
    for (let i = 0; i < 250; i++) {
      ingestSwarmEvent(
        { type: 'swarm.assign', swarm_id: 'sw1', task_id: `t${i}`, session_id: `s${i}`, owned_files: [], role: `r${i}` },
        i,
      );
    }
    expect(swarmLiveEdges().length).toBeLessThanOrEqual(200);
  });

  it('dedups broadcast fan-out copies by eid (same eid ingested once)', () => {
    const copy = {
      type: 'swarm.assign' as const,
      eid: 'e-abc',
      swarm_id: 'sw1',
      task_id: 't1',
      session_id: 's1',
      owned_files: [],
      role: 'builder-1',
    };
    // A 4-member swarm delivers the SAME logical event 4 times (one per stream).
    ingestSwarmEvent(copy, 1000);
    ingestSwarmEvent({ ...copy }, 1001);
    ingestSwarmEvent({ ...copy }, 1002);
    ingestSwarmEvent({ ...copy }, 1003);
    // Only the first counts: one edge, one seq bump, one assignment.
    expect(swarmLiveEdges()).toHaveLength(1);
    expect(swarmEventSeq()).toBe(1);
    // A genuinely distinct event (new eid) is NOT starved by the guard.
    ingestSwarmEvent({ ...copy, eid: 'e-xyz', task_id: 't2', role: 'builder-2' }, 1004);
    expect(swarmLiveEdges()).toHaveLength(2);
    expect(swarmEventSeq()).toBe(2);
  });

  it('events without an eid bypass the dedup guard (older server back-compat)', () => {
    ingestSwarmEvent({ type: 'swarm.assign', swarm_id: 'sw1', task_id: 't1', session_id: 's1', owned_files: [], role: 'r1' }, 1);
    ingestSwarmEvent({ type: 'swarm.assign', swarm_id: 'sw1', task_id: 't1', session_id: 's1', owned_files: [], role: 'r1' }, 2);
    expect(swarmEventSeq()).toBe(2);
  });

  it('swarmEventSeq increments monotonically and keeps climbing past the edge-ring cap', () => {
    expect(swarmEventSeq()).toBe(0);
    for (let i = 0; i < 250; i++) {
      ingestSwarmEvent(
        { type: 'swarm.assign', swarm_id: 'sw1', task_id: `t${i}`, session_id: `s${i}`, owned_files: [], role: `r${i}` },
        i,
      );
    }
    // The edge ring is capped at 200, but the seq counter must NOT plateau —
    // otherwise SwarmMap's refetch trigger freezes after the ring saturates.
    expect(swarmLiveEdges().length).toBeLessThanOrEqual(200);
    expect(swarmEventSeq()).toBe(250);
  });
});
