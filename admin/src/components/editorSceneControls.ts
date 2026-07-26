import { useEffect, useRef, type RefObject } from "react";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import type { TransformControls as TransformControlsImpl } from "three-stdlib";

export type EditorToolMode = "view" | "translate" | "rotate" | "scale";

type DraggingTransformControls = TransformControlsImpl & {
  addEventListener(type: "dragging-changed", listener: (event: { value: boolean }) => void): void;
  removeEventListener(type: "dragging-changed", listener: (event: { value: boolean }) => void): void;
};

export function useTransformOrbitSync(
  transformRef: RefObject<TransformControlsImpl | null>,
  orbitRef: RefObject<OrbitControlsImpl | null>,
  active: boolean,
  onDragging: (dragging: boolean) => void,
  onDragEnd: () => void,
) {
  const onDragEndRef = useRef(onDragEnd);
  const onDraggingRef = useRef(onDragging);
  onDragEndRef.current = onDragEnd;
  onDraggingRef.current = onDragging;

  useEffect(() => {
    if (!active) return;
    const transform = transformRef.current as DraggingTransformControls | null;
    const orbit = orbitRef.current;
    if (!transform || !orbit) return;

    const handleDragging = (event: { value: boolean }) => {
      const dragging = Boolean(event.value);
      orbit.enabled = !dragging;
      onDraggingRef.current(dragging);
      if (!dragging) onDragEndRef.current();
    };

    transform.addEventListener("dragging-changed", handleDragging);
    return () => transform.removeEventListener("dragging-changed", handleDragging);
  }, [active, transformRef, orbitRef]);
}
