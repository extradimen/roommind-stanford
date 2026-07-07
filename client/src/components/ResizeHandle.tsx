type Props = {
  direction: "horizontal" | "vertical";
  onDragStart: (e: React.MouseEvent) => void;
  label?: string;
};

export default function ResizeHandle({ direction, onDragStart, label }: Props) {
  return (
    <div
      className={`resize-handle resize-handle-${direction}`}
      role="separator"
      aria-orientation={direction === "horizontal" ? "vertical" : "horizontal"}
      aria-label={label}
      tabIndex={0}
      onMouseDown={onDragStart}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") e.preventDefault();
      }}
    />
  );
}
