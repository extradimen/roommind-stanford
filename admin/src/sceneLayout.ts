import type { Character } from "./api";

export type SeatPose = {
  position: [number, number, number];
  rotationY: number;
  scale?: number;
};

export type CameraPreset = {
  position: [number, number, number];
  fov: number;
  distance: number;
  min: number;
  max: number;
};

export type SeatLayout = {
  seats: Record<string, SeatPose>;
  camera?: {
    compact?: Partial<CameraPreset>;
    full?: Partial<CameraPreset>;
  };
};

export function round3(n: number): number {
  return Math.round(n * 1000) / 1000;
}

export function roundSeatPose(seat: SeatPose): SeatPose {
  return {
    position: [round3(seat.position[0]), round3(seat.position[1]), round3(seat.position[2])],
    rotationY: round3(seat.rotationY),
    scale: round3(seat.scale ?? 1),
  };
}

export function seatPosesEqual(a: SeatPose, b: SeatPose): boolean {
  const ra = roundSeatPose(a);
  const rb = roundSeatPose(b);
  return (
    ra.position[0] === rb.position[0] &&
    ra.position[1] === rb.position[1] &&
    ra.position[2] === rb.position[2] &&
    ra.rotationY === rb.rotationY &&
    ra.scale === rb.scale
  );
}

type Side = "opponent" | "player_ally" | "user";

const NEGOTIATION_SEATS = {
  northWest: { position: [-0.55, 0, -1.18] as [number, number, number], rotationY: 0 },
  northEast: { position: [0.55, 0, -1.18] as [number, number, number], rotationY: 0 },
  southWest: { position: [-0.55, 0, 0.42] as [number, number, number], rotationY: Math.PI },
  southEast: { position: [0.55, 0, 0.42] as [number, number, number], rotationY: Math.PI },
};

export const DEFAULT_CAMERA: { compact: CameraPreset; full: CameraPreset } = {
  compact: { position: [0, 2.5, 4.8], fov: 48, distance: 5.5, min: 2.6, max: 9.5 },
  full: { position: [0, 2.3, 4.2], fov: 55, distance: 5.0, min: 2.2, max: 10 },
};

function resolveNegotiationSeat(side: Side, opponentIndex: number): SeatPose {
  const base =
    side === "user"
      ? NEGOTIATION_SEATS.southEast
      : side === "player_ally"
        ? NEGOTIATION_SEATS.southWest
        : opponentIndex === 0
          ? NEGOTIATION_SEATS.northWest
          : NEGOTIATION_SEATS.northEast;
  return { position: [...base.position], rotationY: base.rotationY, scale: 1 };
}

function buildSideMap(characters: Character[]): Record<string, Side> {
  const map: Record<string, Side> = {};
  for (const c of characters) {
    if (c.character_id) map[c.character_id] = (c.side as Side) || "opponent";
  }
  return map;
}

function num(value: unknown, fallback: number): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function vec3(raw: unknown, fallback: [number, number, number]): [number, number, number] {
  if (!Array.isArray(raw) || raw.length < 3) return fallback;
  return [num(raw[0], fallback[0]), num(raw[1], fallback[1]), num(raw[2], fallback[2])];
}

function sanitizeSeatPose(raw: unknown, fallback: SeatPose): SeatPose {
  if (!raw || typeof raw !== "object") return fallback;
  const r = raw as Record<string, unknown>;
  const pos = vec3(r.position, fallback.position);
  if (pos[1] < -0.05) pos[1] = fallback.position[1];
  const scaleRaw = num(r.scale, fallback.scale ?? 1);
  const scale = scaleRaw > 1.35 ? (fallback.scale ?? 1) : Math.min(2, Math.max(0.4, scaleRaw));
  return {
    position: pos,
    rotationY: num(r.rotationY, fallback.rotationY),
    scale,
  };
}

function mergeCameraPreset(raw: unknown, fallback: CameraPreset): CameraPreset {
  if (!raw || typeof raw !== "object") return fallback;
  const r = raw as Record<string, unknown>;
  return {
    position: vec3(r.position, fallback.position),
    fov: num(r.fov, fallback.fov),
    distance: num(r.distance, fallback.distance),
    min: num(r.min, fallback.min),
    max: num(r.max, fallback.max),
  };
}

export function buildDefaultSeatLayout(characters: Character[], includePlayer = true): SeatLayout {
  const sideMap = buildSideMap(characters);
  const seats: Record<string, SeatPose> = {};
  let opponentIndex = 0;
  for (const c of characters) {
    if (!c.character_id) continue;
    const side = sideMap[c.character_id] || "opponent";
    const seat =
      side === "opponent"
        ? resolveNegotiationSeat(side, opponentIndex++)
        : resolveNegotiationSeat(side, 0);
    seats[c.character_id] = seat;
  }
  if (includePlayer) {
    seats.user = resolveNegotiationSeat("user", 0);
  }
  return {
    seats,
    camera: {
      compact: { ...DEFAULT_CAMERA.compact },
      full: { ...DEFAULT_CAMERA.full },
    },
  };
}

export function resolveSeatLayout(
  sceneConfig: Record<string, unknown> | undefined,
  characters: Character[],
  includePlayer = true,
): SeatLayout {
  const defaults = buildDefaultSeatLayout(characters, includePlayer);
  const raw = sceneConfig?.seat_layout;
  if (!raw || typeof raw !== "object") return defaults;

  const input = raw as SeatLayout;
  const seats = { ...defaults.seats };
  if (input.seats && typeof input.seats === "object") {
    for (const [id, pose] of Object.entries(input.seats)) {
      seats[id] = sanitizeSeatPose(pose, seats[id] || resolveNegotiationSeat("user", 0));
    }
  }

  return {
    seats,
    camera: {
      compact: mergeCameraPreset(input.camera?.compact, DEFAULT_CAMERA.compact),
      full: mergeCameraPreset(input.camera?.full, DEFAULT_CAMERA.full),
    },
  };
}
