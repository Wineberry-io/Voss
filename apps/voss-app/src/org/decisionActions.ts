// Decision-action wrappers for the Blocked panel (D-07/D-08).
//
// The ONLY non-interactive run-level write path verified in the harness
// (voss/harness/cli.py audit_cmd) is `voss audit <run_id> --cwd <cwd> --approve`.
// There is NO standalone `voss approve/reject/unblock <card>` command, and the
// `voss team run` sign-off uses an interactive click.prompt that cannot be
// shelled non-interactively. So the actionable decision surfaced here is
// `approve`; reject/unblock/per-card sign-off have no non-interactive CLI
// surface in V7/V9 and the Blocked panel (Plan 07) renders them
// disabled-with-explanation until a harness command exists. This preserves the
// one-write-path invariant without inventing harness behavior.

import { invoke } from '@tauri-apps/api/core';
import type { DecisionResult } from './types';

export type DecisionAction = 'approve';

/** The real CLI argv for a decision (the verified `--approve` write path). */
export function buildDecisionArgs(_action: DecisionAction, runId: string): string[] {
  return ['audit', runId, '--approve'];
}

/** The literal command string shown in the D-07 confirmation dialog. */
export function buildDecisionCommand(
  _action: DecisionAction,
  runId: string,
  cwd: string,
): string {
  return `voss audit ${runId} --cwd ${cwd} --approve`;
}

/** Shell the decision via the Rust `run_decision` command (D-08 capture). */
export async function runDecision(
  _cliBinary: string,
  _cwd: string,
  action: DecisionAction,
  runId: string,
): Promise<DecisionResult> {
  return invoke<DecisionResult>('run_decision', {
    args: buildDecisionArgs(action, runId),
  });
}
