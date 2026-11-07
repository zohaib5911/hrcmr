"use client";

import { Maximize2, Minus, Plus } from "lucide-react";
import {
  type PointerEvent,
  type Ref,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";

import { IconButton } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";

import { type Layout, NODE_HEIGHT, NODE_WIDTH, type OrgPerson } from "./layout";

const MIN_SCALE = 0.25;
const MAX_SCALE = 2.5;
const ZOOM_STEP = 1.25;
/** A press that moves less than this is a click, not a pan. */
const DRAG_SLOP = 4;
/** Space left around the chart when it is fitted to the frame. */
const MARGIN = 16;

interface View {
  x: number;
  y: number;
  scale: number;
}

interface Point {
  x: number;
  y: number;
}

/** What the page can ask the canvas to do. */
export interface CanvasHandle {
  /** Brings one person to the middle of the view, zooming in to at least 100%. */
  centreOn(id: string): void;
}

interface CanvasProps {
  layout: Layout;
  showVisa: boolean;
  selectedId: string | null;
  onOpen: (person: OrgPerson) => void;
  handle: Ref<CanvasHandle>;
}

const clamp = (value: number) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, value));
const START: View = { x: 0, y: 0, scale: 1 };

/**
 * The org chart as cards in an SVG: drag to pan, the zoom buttons or a pinch to zoom, and a card
 * opens its person. Panning and zooming are SVG transforms; no chart library.
 */
export function OrgCanvas({ layout, showVisa, selectedId, onOpen, handle }: CanvasProps) {
  const frame = useRef<HTMLDivElement>(null);
  const viewRef = useRef<View>(START);
  const [view, setView] = useState<View>(START);
  const pointers = useRef(new Map<number, Point>());
  const drag = useRef<{
    startX: number;
    startY: number;
    lastX: number;
    lastY: number;
    moved: boolean;
  } | null>(null);
  const pinch = useRef<{ distance: number; scale: number; px: number; py: number } | null>(null);

  const commit = useCallback((next: View) => {
    viewRef.current = next;
    setView(next);
  }, []);

  const size = useCallback(() => {
    const el = frame.current;
    return el ? { width: el.clientWidth, height: el.clientHeight } : { width: 0, height: 0 };
  }, []);

  const pointIn = useCallback((x: number, y: number): Point => {
    const rect = frame.current?.getBoundingClientRect();
    return rect ? { x: x - rect.left, y: y - rect.top } : { x: 0, y: 0 };
  }, []);

  // Show the whole chart, as large as the frame allows (at most 100%), centred across the top.
  const fitView = useCallback(() => {
    const { width, height } = size();
    if (layout.width === 0 || layout.height === 0 || width === 0 || height === 0) {
      commit({ x: 0, y: 0, scale: 1 });
      return;
    }
    const scale = clamp(
      Math.min(1, (width - 2 * MARGIN) / layout.width, (height - 2 * MARGIN) / layout.height),
    );
    commit({ scale, x: (width - layout.width * scale) / 2, y: MARGIN });
  }, [layout, size, commit]);

  // Where the chart opens: at 100% so the names read, centred across the top. People pan from
  // there, and the Fit button shows the whole chart when they want the overview.
  const openView = useCallback(() => {
    const { width } = size();
    commit({ scale: 1, x: (width - layout.width) / 2, y: MARGIN });
  }, [layout, size, commit]);

  // Open at first paint, and again whenever the frame changes size. The observer is a subscription,
  // so the view is set from its callback rather than in the effect body.
  useEffect(() => {
    const el = frame.current;
    if (!el) return;
    const observer = new ResizeObserver(() => openView());
    observer.observe(el);
    return () => observer.disconnect();
  }, [openView]);

  const centreOn = useCallback(
    (id: string) => {
      const node = layout.nodes.find((placed) => placed.person.id === id);
      if (!node) return;
      const { width, height } = size();
      const scale = Math.max(viewRef.current.scale, 1);
      commit({
        scale,
        x: width / 2 - (node.x + NODE_WIDTH / 2) * scale,
        y: height / 2 - (node.y + NODE_HEIGHT / 2) * scale,
      });
    },
    [layout, size, commit],
  );

  useImperativeHandle(handle, () => ({ centreOn }), [centreOn]);

  function zoomTo(nextScale: number, px: number, py: number) {
    const current = viewRef.current;
    const scale = clamp(nextScale);
    const worldX = (px - current.x) / current.scale;
    const worldY = (py - current.y) / current.scale;
    commit({ scale, x: px - worldX * scale, y: py - worldY * scale });
  }

  function zoomBy(factor: number) {
    const { width, height } = size();
    zoomTo(viewRef.current.scale * factor, width / 2, height / 2);
  }

  /** The two pressed points, when two fingers are down. */
  function twoPoints(): [Point, Point] | null {
    const [a, b] = [...pointers.current.values()];
    return a && b ? [a, b] : null;
  }

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointers.current.size === 1) {
      drag.current = {
        startX: event.clientX,
        startY: event.clientY,
        lastX: event.clientX,
        lastY: event.clientY,
        moved: false,
      };
      return;
    }
    const pair = twoPoints();
    if (pair) {
      const [a, b] = pair;
      const mid = pointIn((a.x + b.x) / 2, (a.y + b.y) / 2);
      const current = viewRef.current;
      pinch.current = {
        distance: Math.hypot(a.x - b.x, a.y - b.y) || 1,
        scale: current.scale,
        px: (mid.x - current.x) / current.scale,
        py: (mid.y - current.y) / current.scale,
      };
      drag.current = null;
    }
  }

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    const pointer = pointers.current.get(event.pointerId);
    if (!pointer) return;
    pointer.x = event.clientX;
    pointer.y = event.clientY;
    const pair = twoPoints();
    if (pair && pinch.current) {
      const [a, b] = pair;
      const mid = pointIn((a.x + b.x) / 2, (a.y + b.y) / 2);
      const scale = clamp(
        (pinch.current.scale * Math.hypot(a.x - b.x, a.y - b.y)) / pinch.current.distance,
      );
      commit({
        scale,
        x: mid.x - pinch.current.px * scale,
        y: mid.y - pinch.current.py * scale,
      });
      return;
    }
    const press = drag.current;
    if (!press || pointers.current.size !== 1) return;
    if (!press.moved) {
      if (Math.hypot(event.clientX - press.startX, event.clientY - press.startY) < DRAG_SLOP)
        return;
      press.moved = true;
      // From here the pointer belongs to the canvas, so a press that became a pan opens no card.
      frame.current?.setPointerCapture(event.pointerId);
    }
    const current = viewRef.current;
    commit({
      ...current,
      x: current.x + event.clientX - press.lastX,
      y: current.y + event.clientY - press.lastY,
    });
    press.lastX = event.clientX;
    press.lastY = event.clientY;
  }

  function onPointerEnd(event: PointerEvent<HTMLDivElement>) {
    pointers.current.delete(event.pointerId);
    if (pointers.current.size < 2) pinch.current = null;
    if (pointers.current.size === 0) drag.current = null;
  }

  return (
    <div className="relative">
      <div
        ref={frame}
        role="group"
        aria-label="Org chart. Drag to move around. Use the zoom buttons, or pinch, to zoom."
        className="bg-grouped border-separator relative h-[min(68vh,640px)] min-h-80 touch-none overflow-hidden rounded-xl border select-none"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerEnd}
        onPointerCancel={onPointerEnd}
      >
        <svg width="100%" height="100%" className="block">
          <g transform={`translate(${view.x} ${view.y}) scale(${view.scale})`}>
            {layout.links.map((link) => {
              const middle = (link.from[1] + link.to[1]) / 2;
              return (
                <path
                  key={`${link.from.join(",")}-${link.to.join(",")}`}
                  d={`M${link.from[0]} ${link.from[1]} V${middle} H${link.to[0]} V${link.to[1]}`}
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.5}
                  className="text-label-tertiary"
                />
              );
            })}
            {layout.nodes.map((placed) => {
              const { person } = placed;
              const selected = person.id === selectedId;
              const label = [person.name, person.job_title, person.level]
                .filter(Boolean)
                .join(", ");
              return (
                <foreignObject
                  key={person.id}
                  x={placed.x}
                  y={placed.y}
                  width={NODE_WIDTH}
                  height={NODE_HEIGHT}
                >
                  <button
                    type="button"
                    aria-label={label}
                    aria-current={selected ? "true" : undefined}
                    onClick={() => onOpen(person)}
                    className={
                      "bg-elevated flex h-full w-full flex-col justify-center gap-0.5 rounded-xl border px-3 text-left shadow-sm " +
                      (selected ? "border-accent bg-accent-tint" : "border-separator")
                    }
                  >
                    <span className="text-callout text-label truncate font-semibold">
                      {person.name}
                    </span>
                    {person.job_title ? (
                      <span className="text-footnote text-label-secondary truncate">
                        {person.job_title}
                      </span>
                    ) : null}
                    <span className="text-caption text-label-secondary flex min-w-0 gap-1">
                      {person.level ? (
                        <span className="bg-fill-secondary truncate rounded-md px-1.5">
                          {person.level}
                        </span>
                      ) : null}
                      {showVisa && person.rtw_status ? (
                        <span className="border-separator truncate rounded-md border px-1.5">
                          RTW {person.rtw_status.replace(/_/g, " ")}
                        </span>
                      ) : null}
                    </span>
                  </button>
                </foreignObject>
              );
            })}
          </g>
        </svg>
      </div>
      <div className="absolute right-3 bottom-3 flex gap-1">
        <IconButton label="Zoom in" variant="gray" size="sm" onClick={() => zoomBy(ZOOM_STEP)}>
          <Icon icon={Plus} />
        </IconButton>
        <IconButton label="Zoom out" variant="gray" size="sm" onClick={() => zoomBy(1 / ZOOM_STEP)}>
          <Icon icon={Minus} />
        </IconButton>
        <IconButton label="Fit the whole chart" variant="gray" size="sm" onClick={fitView}>
          <Icon icon={Maximize2} />
        </IconButton>
      </div>
    </div>
  );
}
