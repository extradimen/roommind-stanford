import type { Character } from "./api";
import { buildCharacterSideMap, type CharacterSide } from "./characterSide";

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

function resolveNegotiationSeat(side: CharacterSide | "user", opponentIndex: number): SeatPose {
  const base =
    side === "user"
      ? NEGOTIATION_SEATS.southEast
      : side === "player_ally"
        ? NEGOTIATION_SEATS.southWest
        : opponentIndex === 0
          ? NEGOTIATION_SEATS.northWest
          : NEGOTIATION_SEATS.northEast;
  return { position: [...base.position], rotationY: base.rotationY, scale: 1.25 };
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
  // Legacy editor sessions saved negative Y (feet sunk into floor after fitSeatedGltfRoot).
  if (pos[1] < -0.05) pos[1] = fallback.position[1];
  const scaleRaw = num(r.scale, fallback.scale ?? 1);
  const scale = Math.min(2, Math.max(0.4, scaleRaw));
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
  const sideMap = buildCharacterSideMap(characters);
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

export function resolveSeatForCharacter(
  layout: SeatLayout,
  characterId: string,
  characters: Character[],
  includePlayer = true,
): SeatPose {
  const saved = layout.seats[characterId];
  if (saved) return saved;
  return buildDefaultSeatLayout(characters, includePlayer).seats[characterId] || resolveNegotiationSeat("user", 0);
}
