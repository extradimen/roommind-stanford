import type { Character } from "../api";
import { useLocale } from "../i18n";
import {
  buildDefaultSeatLayout,
  DEFAULT_CAMERA,
  round3,
  type CameraPreset,
  type SeatLayout,
  type SeatPose,
} from "../sceneLayout";
import SeatLayoutPreview, { type LayoutSubject } from "./SeatLayoutPreview";

type Props = {
  characters: Character[];
  playerLabel: string;
  playerManifest: Record<string, unknown>;
  seatLayout: SeatLayout;
  onChange: (layout: SeatLayout) => void;
};

function radToDeg(r: number): number {
  return Math.round((r * 180) / Math.PI);
}

function degToRad(d: number): number {
  return (d * Math.PI) / 180;
}

function numInput(value: number, onChange: (n: number) => void, step: number | "any", min?: number, max?: number) {
  return (
    <input
      type="number"
      step={step}
      min={min}
      max={max}
      value={Number.isFinite(value) ? round3(value) : 0}
      onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
    />
  );
}

function buildSubjects(characters: Character[], playerLabel: string, playerManifest: Record<string, unknown>): LayoutSubject[] {
  return [
    ...characters.map((c) => ({
      id: c.character_id,
      label: c.character_name || c.character_id,
      manifest: c.avatar_manifest,
    })),
    { id: "user", label: playerLabel, manifest: playerManifest },
  ];
}

export default function SeatLayoutEditor({
  characters,
  playerLabel,
  playerManifest,
  seatLayout,
  onChange,
}: Props) {
  const { t } = useLocale();
  const subjects = buildSubjects(characters, playerLabel, playerManifest);

  const updateSeat = (id: string, patch: Partial<SeatPose>) => {
    const current = seatLayout.seats[id] || { position: [0, 0, 0], rotationY: 0, scale: 1 };
    onChange({
      ...seatLayout,
      seats: { ...seatLayout.seats, [id]: { ...current, ...patch } },
    });
  };

  const updatePosition = (id: string, axis: 0 | 1 | 2, value: number) => {
    const current = seatLayout.seats[id];
    const pos: [number, number, number] = [...(current?.position || [0, 0, 0])] as [number, number, number];
    pos[axis] = value;
    updateSeat(id, { position: pos });
  };

  const updateCamera = (mode: "compact" | "full", patch: Partial<CameraPreset>) => {
    const cam = seatLayout.camera?.[mode] || {};
    onChange({
      ...seatLayout,
      camera: {
        ...seatLayout.camera,
        [mode]: { ...cam, ...patch },
      },
    });
  };

  const updateCameraPosition = (mode: "compact" | "full", axis: 0 | 1 | 2, value: number) => {
    const cam = seatLayout.camera?.[mode];
    const pos: [number, number, number] = [...(cam?.position || [0, 2.5, 4.8])] as [number, number, number];
    pos[axis] = value;
    updateCamera(mode, { position: pos });
  };

  const rows = subjects;

  return (
    <>
      <SeatLayoutPreview
        subjects={subjects}
        seatLayout={seatLayout}
        onChange={onChange}
        onResetDefaults={() => onChange(buildDefaultSeatLayout(characters, true))}
      />

      <details className="seat-layout-advanced">
        <summary>{t.sceneVisual.advancedNumeric}</summary>
        <section style={{ marginTop: "1rem" }}>
          <p className="muted">{t.sceneVisual.seatLayoutHint}</p>
          {rows.map((row) => {
            const seat = seatLayout.seats[row.id];
            if (!seat) return null;
            return (
              <div key={row.id} className="char-card">
                <div className="char-header">
                  <strong>{row.label}</strong>
                  <code>{row.id}</code>
                </div>
                <div className="row" style={{ gap: "0.75rem", flexWrap: "wrap", alignItems: "flex-end" }}>
                  {(["X", "Y", "Z"] as const).map((label, i) => (
                    <label key={label}>
                      {label}
                      {numInput(seat.position[i as 0 | 1 | 2], (v) => updatePosition(row.id, i as 0 | 1 | 2, v), 0.01)}
                    </label>
                  ))}
                  <label>
                    {t.sceneVisual.rotationDeg}
                    {numInput(radToDeg(seat.rotationY), (v) => updateSeat(row.id, { rotationY: degToRad(v) }), 1)}
                  </label>
                  <label>
                    {t.sceneVisual.scale}
                    {numInput(seat.scale ?? 1, (v) => updateSeat(row.id, { scale: v }), 0.05, 0.4, 2)}
                  </label>
                </div>
              </div>
            );
          })}

          <h3 style={{ marginTop: "1.25rem" }}>{t.sceneVisual.cameraSection}</h3>
          <p className="muted">{t.sceneVisual.cameraHint}</p>
          {(["compact", "full"] as const).map((mode) => {
            const fallback = DEFAULT_CAMERA[mode];
            const cam: CameraPreset = { ...fallback, ...seatLayout.camera?.[mode] };
            const title = mode === "compact" ? t.sceneVisual.cameraCompact : t.sceneVisual.cameraFull;
            return (
              <div key={mode} className="char-card">
                <strong>{title}</strong>
                <div className="row" style={{ gap: "0.75rem", flexWrap: "wrap", alignItems: "flex-end" }}>
                  <label>
                    {t.sceneVisual.cameraDistance}
                    {numInput(cam.distance, (v) => updateCamera(mode, { distance: v }), "any", 1, 15)}
                  </label>
                  <label>
                    FOV
                    {numInput(cam.fov, (v) => updateCamera(mode, { fov: v }), 1, 20, 90)}
                  </label>
                  <label>
                    {t.sceneVisual.cameraMin}
                    {numInput(cam.min, (v) => updateCamera(mode, { min: v }), "any", 1, 15)}
                  </label>
                  <label>
                    {t.sceneVisual.cameraMax}
                    {numInput(cam.max, (v) => updateCamera(mode, { max: v }), "any", 2, 20)}
                  </label>
                  {(["X", "Y", "Z"] as const).map((label, i) => (
                    <label key={`${mode}-${label}`}>
                      {t.sceneVisual.cameraPos} {label}
                      {numInput(cam.position[i as 0 | 1 | 2], (v) => updateCameraPosition(mode, i as 0 | 1 | 2, v), "any")}
                    </label>
                  ))}
                </div>
              </div>
            );
          })}
        </section>
      </details>
    </>
  );
}
