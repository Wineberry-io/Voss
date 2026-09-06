import { Show, createSignal, type JSX } from 'solid-js';
import PaneHeader from '../grid/PaneHeader';
import RestoreBanner from '../grid/RestoreBanner';
import NodeMenu from './NodeMenu';
import NodeCloseBanner from './NodeCloseBanner';
import type { CanvasNode } from './model';

export interface NodeFrameProps {
  node: CanvasNode;
  focused: boolean;
  dragging: boolean;
  process?: string;
  prefixActive?: boolean;
  prefixReserved?: boolean;
  isAgent?: boolean;
  roleColor?: string;
  isStreaming?: boolean;
  costUsd?: number;
  restoredLineCount?: number;
  closeBanner: string | null;
  onFocus: () => void;
  onHeaderPointerDown: (e: PointerEvent) => void;
  onResizePointerDown: (e: PointerEvent) => void;
  onFork: () => void;
  onSplitRight: () => void;
  onSplitBelow: () => void;
  onRequestClose: () => void;
  onConfirmClose: () => void;
  onKeepOpen: () => void;
  children: JSX.Element;
}

export default function NodeFrame(props: NodeFrameProps) {
  const [menuOpen, setMenuOpen] = createSignal(false);

  return (
    <div
      data-pane-id={props.node.id}
      data-dragging={props.dragging ? '' : undefined}
      classList={{
        'canvas-node grid-pane-leaf': true,
        'grid-pane-leaf--focused': props.focused,
      }}
      style={{
        transform: `translate(${props.node.x}px, ${props.node.y}px)`,
        width: `${props.node.w}px`,
        height: `${props.node.h}px`,
        'z-index': props.node.z,
      }}
      onPointerDown={() => props.onFocus()}
    >
      <PaneHeader
        index={props.node.index}
        focused={props.focused}
        cwd={props.node.cwd}
        shell={props.node.shell}
        process={props.process}
        prefixActive={props.focused && props.prefixActive}
        prefixReserved={props.prefixReserved}
        onToggleMenu={() => setMenuOpen((v) => !v)}
        onDragPointerDown={(e) => props.onHeaderPointerDown(e)}
        isAgent={props.isAgent}
        roleColor={props.roleColor}
        isStreaming={props.isStreaming}
        costUsd={props.costUsd}
      />
      <Show when={menuOpen()}>
        <NodeMenu
          onDismiss={() => setMenuOpen(false)}
          onFork={props.onFork}
          onSplitRight={props.onSplitRight}
          onSplitBelow={props.onSplitBelow}
          onRequestClose={props.onRequestClose}
        />
      </Show>
      <Show when={props.closeBanner !== null}>
        <NodeCloseBanner
          process={props.closeBanner as string}
          active={props.focused}
          onConfirm={props.onConfirmClose}
          onKeepOpen={props.onKeepOpen}
        />
      </Show>
      <Show when={props.restoredLineCount != null}>
        <RestoreBanner lineCount={props.restoredLineCount!} />
      </Show>
      <div class="canvas-node__body">{props.children}</div>
      <div
        class="canvas-node__resize"
        data-resize-handle=""
        onPointerDown={(e) => {
          e.stopPropagation();
          props.onResizePointerDown(e);
        }}
      />
    </div>
  );
}
