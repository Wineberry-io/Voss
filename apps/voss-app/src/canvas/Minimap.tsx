import { For } from 'solid-js';
import type { Size } from './geometry';
import type { CanvasNode, CanvasView } from './model';
import { MINIMAP_SIZE, minimapLayout, viewCenteredOnMinimapPoint } from './minimapLayout';

/**
 * Bottom-right overview: every node as a rectangle, the viewport as an
 * outline. Click centres the view there; dragging scrubs it.
 */
export default function Minimap(props: {
  nodes: readonly CanvasNode[];
  view: CanvasView;
  viewport: Size;
  focusedId: string;
  colorFor: (node: CanvasNode) => string;
  onPan: (view: CanvasView) => void;
}) {
  let el!: HTMLDivElement;
  const layout = () => minimapLayout(props.nodes, props.view, props.viewport);

  const panTo = (e: PointerEvent) => {
    const r = el.getBoundingClientRect();
    props.onPan(viewCenteredOnMinimapPoint(layout(), props.view, props.viewport, e.clientX - r.left, e.clientY - r.top));
  };

  const onPointerDown = (e: PointerEvent) => {
    if (e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    panTo(e);
    const move = (ev: PointerEvent) => panTo(ev);
    const end = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', end);
      window.removeEventListener('pointercancel', end);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', end);
    window.addEventListener('pointercancel', end);
  };

  return (
    <div
      ref={el}
      class="canvas-minimap"
      data-minimap=""
      role="img"
      aria-label="Canvas overview"
      style={{ width: `${MINIMAP_SIZE.w}px`, height: `${MINIMAP_SIZE.h}px` }}
      onPointerDown={onPointerDown}
    >
      <For each={layout().nodes}>
        {(r) => {
          const node = () => props.nodes.find((n) => n.id === r.id)!;
          return (
            <div
              class="canvas-minimap__node"
              data-minimap-node={r.id}
              classList={{ 'canvas-minimap__node--focused': r.id === props.focusedId }}
              style={{
                left: `${r.x}px`,
                top: `${r.y}px`,
                width: `${Math.max(2, r.w)}px`,
                height: `${Math.max(2, r.h)}px`,
                background: props.colorFor(node()),
              }}
            />
          );
        }}
      </For>
      <div
        class="canvas-minimap__viewport"
        data-minimap-viewport=""
        style={{
          left: `${layout().viewport.x}px`,
          top: `${layout().viewport.y}px`,
          width: `${layout().viewport.w}px`,
          height: `${layout().viewport.h}px`,
        }}
      />
    </div>
  );
}
