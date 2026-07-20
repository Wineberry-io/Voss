import { type Component } from 'solid-js';
import './orgStyles.css';
import CockpitShell from './cockpit/CockpitShell';
import type { FollowUpClient } from './feedbackWritePath';
import type { SidecarVossClient } from './live/sidecarClient';

// V14 (D-01/D-02): the legacy tab switcher is removed. The cockpit
// (Board spine + Card detail drawer + Timeline/replay rail + bottom gate bar) is
// the single Run Review surface. OrgViewShell is now a thin wrapper so App.tsx's
// existing mount/props/⌘⇧O toggle wiring is unchanged; all logic lives in
// CockpitShell. No legacy tab escape hatch (D-02).
const OrgViewShell: Component<{
  cwd: string;
  cliBinary: string;
  onClose: () => void;
  /** V15-02: live follow-up write client, threaded to the CardDrawer. */
  followUpClient?: FollowUpClient;
  /** V15-05: live sidecar client + Attach action for the sidebar section. */
  vossClient?: SidecarVossClient;
  onAttach?: (sessionId: string) => void;
}> = (props) => {
  return (
    <CockpitShell
      cwd={props.cwd}
      cliBinary={props.cliBinary}
      onClose={props.onClose}
      followUpClient={props.followUpClient}
      vossClient={props.vossClient}
      onAttach={props.onAttach}
    />
  );
};

export default OrgViewShell;
