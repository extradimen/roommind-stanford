import { useCallback, useState } from "react";

function clamp(v: number, min: number, max: number) {
  return Math.min(max, Math.max(min, v));
}

function readRatio(key: string, defaultValue: number, min: number, max: number) {
  try {
    const raw = localStorage.getItem(key);
    if (raw != null) {
      const n = parseFloat(raw);
      if (Number.isFinite(n)) return clamp(n, min, max);
    }
  } catch {
    /* ignore */
  }
  return defaultValue;
}

export function usePersistedRatio(
  storageKey: string,
  defaultValue: number,
  min: number,
  max: number,
) {
  const [ratio, setRatioState] = useState(() => readRatio(storageKey, defaultValue, min, max));

  const setRatio = useCallback(
    (value: number) => {
      const next = clamp(value, min, max);
      setRatioState(next);
      try {
        localStorage.setItem(storageKey, String(next));
      } catch {
        /* ignore */
      }
    },
    [storageKey, min, max],
  );

  return [ratio, setRatio] as const;
}

export function bindDragResize(
  e: React.MouseEvent,
  onMove: (clientX: number, clientY: number) => void,
  cursor: "col-resize" | "row-resize",
) {
  e.preventDefault();
  document.body.style.cursor = cursor;
  document.body.style.userSelect = "none";

  const move = (ev: MouseEvent) => onMove(ev.clientX, ev.clientY);
  const up = () => {
    document.removeEventListener("mousemove", move);
    document.removeEventListener("mouseup", up);
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
  };

  document.addEventListener("mousemove", move);
  document.addEventListener("mouseup", up);
}
