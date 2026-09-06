import { For, Show, createSignal, type JSX } from 'solid-js';
import PaneHeader from '../grid/PaneHeader';
import RestoreBanner from '../grid/RestoreBanner';
import NodeMenu from './NodeMenu';
import NodeCloseBanner from './NodeCloseBanner';
import type { CanvasNode } from './model';
import { RESIZE_HANDLES, type ResizeHandle } from './store';

export interface NodeFrameProps {
  node: CanvasNode;
  focused: boolean;
  selected: boolean;
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
  onFocus: (e: PointerEvent) => void;
  onHeaderPointerDown: (e: PointerEvent) => void;
  onResizePointerDown: (e: PointerEvent, handle: ResizeHandle) => void;
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
      data-selected={props.selected ? '' : undefined}
      classList={{
        'canvas-node grid-pane-leaf': true,
        'grid-pane-leaf--focused': props.focused,
        'canvas-node--selected': props.selected,
      }}
      style={{
        transform: `translate(${props.node.x}px, ${props.node.y}px)`,
        width: `${props.node.w}px`,
        height: `${props.node.h}px`,
        'z-index': props.node.z,
      }}
      onPointerDown={(e) => props.onFocus(e)}
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
      <For each={RESIZE_HANDLES}>
        {(handle) => (
          <div
            class={`canvas-node__resize canvas-node__resize--${handle}`}
            data-resize-handle={handle}
            onPointerDown={(e) => {
              e.stopPropagation();
              props.onResizePointerDown(e, handle);
            }}
          />
        )}
      </For>
    </div>
  );
}
