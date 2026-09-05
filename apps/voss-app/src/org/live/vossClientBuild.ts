import type { RunNativeClient } from '../cockpit/RunCommandBar';
import type { FollowUpClient } from '../feedbackWritePath';
import {
  createSidecarVossClient,
  type SidecarHandle,
  type SidecarVossClient,
} from './sidecarClient';

export interface BuiltVossClient {
  client: SidecarVossClient;
  sidecarId: string;
  runNativeClient: RunNativeClient;
  followUpClient: FollowUpClient;
}

export function buildVossClientFromHandle(
  handle: SidecarHandle,
): BuiltVossClient {
  const client = createSidecarVossClient(handle.sidecarId);
  return {
    client,
    sidecarId: handle.sidecarId,
    runNativeClient: {
      createSession: async () => ({ id: await client.createSession() }),
    },
    followUpClient: {
      postMessage: (sessionId, text) => client.postMessage(sessionId, text),
    },
  };
}
