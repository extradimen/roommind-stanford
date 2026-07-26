import { useEffect, useRef, useState } from "react";
import { round3 } from "../sceneLayout";

type Props = {
  value: number;
  onCommit: (value: number) => void;
  step?: number | "any";
  min?: number;
  max?: number;
  className?: string;
};

function clamp(value: number, min?: number, max?: number) {
  let next = value;
  if (min != null) next = Math.max(min, next);
  if (max != null) next = Math.min(max, next);
  return next;
}

export default function NumericInput({ value, onCommit, step = "any", min, max, className }: Props) {
  const [draft, setDraft] = useState<string | null>(null);
  const valueRef = useRef(value);
  valueRef.current = value;

  useEffect(() => {
    if (draft == null) return;
    const external = String(round3(valueRef.current));
    if (draft === external) setDraft(null);
  }, [value, draft]);

  const commit = (raw: string) => {
    const parsed = parseFloat(raw);
    if (!Number.isFinite(parsed)) {
      setDraft(null);
      return;
    }
    onCommit(clamp(parsed, min, max));
    setDraft(null);
  };

  return (
    <input
      type="number"
      className={className}
      step={step}
      min={min}
      max={max}
      value={draft ?? (Number.isFinite(value) ? round3(value) : 0)}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={(e) => commit(e.target.value)}
      onKeyDown={(e) => {
        if (e.key !== "Enter") return;
        commit((e.currentTarget as HTMLInputElement).value);
        (e.currentTarget as HTMLInputElement).blur();
      }}
    />
  );
}
