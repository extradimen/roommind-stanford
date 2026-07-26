import type { SeatPose } from "./sceneLayout";
import { resolveAssetUrl } from "./avatarManifest";
import { resolveSceneGraph } from "./sceneGraph";

export const DEFAULT_OFFICE_CHAIR_URL = "/static/props/office_chair-1-41805a48-web.glb";

/** Visual height after fit — keep in sync with admin sceneGraph CHAIR_FIT_HEIGHT. */
export const CHAIR_FIT_HEIGHT = 1.05;

/** Extra group scale on top of fit (Meshy-style GLB exports). */
export const CHAIR_GROUP_SCALE = 0.88;

/** Push chair back from the seat anchor, away from the table center (z ≈ -0.4). */
const CHAIR_BACK_OFFSET_Z = 0.16;
const CHAIR_OUTWARD_OFFSET_X = 0.03;

export type ChairPose = {
  id: string;
  position: [number, number, number];
  rotationY: number;
  scale?: number;
};

const DEFAULT_SEAT_POSES: Array<{ id: string; seat: SeatPose }> = [
  { id: "supplier_ceo_global", seat: { position: [-0.55, 0, -1.18], rotationY: 0 } },
  { id: "supplier_quality_manager", seat: { position: [0.55, 0, -1.18], rotationY: 0 } },
  { id: "procurement_strategy_manager", seat: { position: [-0.55, 0, 0.42], rotationY: Math.PI } },
  { id: "user", seat: { position: [0.55, 0, 0.42], rotationY: Math.PI } },
];

export function isChairAssetUrl(url: string): boolean {
  const trimmed = url.trim().toLowerCase();
  if (!trimmed) return false;
  if (trimmed.includes("conference_table") || trimmed.includes("meeting_table")) return false;
  return trimmed.includes("office_chair") || trimmed.includes("chair");
}

/** Derive chair transform from a character seat (chair slightly behind the sit point). */
export function chairPoseForSeat(seatId: string, seat: SeatPose): ChairPose {
  const [x, , z] = seat.position;
  const facesTable =
    Math.abs(seat.rotationY) < 0.01 || Math.abs(seat.rotationY - Math.PI * 2) < 0.01;
  const zBack = facesTable ? -CHAIR_BACK_OFFSET_Z : CHAIR_BACK_OFFSET_Z;
  const xOut = x < 0 ? -CHAIR_OUTWARD_OFFSET_X : CHAIR_OUTWARD_OFFSET_X;
  const shortId = seatId === "user" ? "se" : seatId.includes("ceo") ? "nw" : seatId.includes("quality") ? "ne" : "sw";
  return {
    id: `chair_${shortId}`,
    position: [x + xOut, 0, z + zBack],
    rotationY: seat.rotationY + Math.PI,
    scale: CHAIR_GROUP_SCALE,
  };
}

export function resolveNegotiationChairs(
  seats: Record<string, SeatPose> | undefined,
): ChairPose[] {
  if (seats && Object.keys(seats).length > 0) {
    return Object.entries(seats).map(([seatId, seat]) => chairPoseForSeat(seatId, seat));
  }
  return DEFAULT_SEAT_POSES.map(({ id, seat }) => chairPoseForSeat(id, seat));
}

export const DEFAULT_NEGOTIATION_CHAIRS: ChairPose[] = resolveNegotiationChairs(
  Object.fromEntries(DEFAULT_SEAT_POSES.map(({ id, seat }) => [id, seat])),
);

export function resolveChairModelUrl(sceneConfig: Record<string, unknown> | undefined): string | undefined {
  const graph = resolveSceneGraph(sceneConfig);
  if (graph) {
    for (const asset of Object.values(graph.assets)) {
      const raw = asset.model_url?.trim();
      if (raw && isChairAssetUrl(raw)) {
        return resolveAssetUrl(raw) || raw;
      }
    }
  }
  return resolveAssetUrl(DEFAULT_OFFICE_CHAIR_URL);
}

export function hasChairPropInstances(sceneConfig: Record<string, unknown> | undefined): boolean {
  const graph = resolveSceneGraph(sceneConfig);
  if (!graph) return false;
  return graph.instances.some((inst) => {
    if (inst.role === "avatar_slot") return false;
    const url = graph.assets[inst.asset_id]?.model_url ?? "";
    return isChairAssetUrl(url);
  });
}

/** World transforms for chair instances saved in scene_graph (prefer over fallback layout). */
export function resolveChairPosesFromGraph(
  sceneConfig: Record<string, unknown> | undefined,
): ChairPose[] | null {
  const graph = resolveSceneGraph(sceneConfig);
  if (!graph) return null;
  const chairs = graph.instances
    .filter((inst) => {
      if (inst.role === "avatar_slot") return false;
      const url = graph.assets[inst.asset_id]?.model_url ?? "";
      return isChairAssetUrl(url);
    })
    .map((inst) => ({
      id: inst.id,
      position: [...inst.transform.position] as [number, number, number],
      rotationY: inst.transform.rotationY,
      scale: inst.transform.scale,
    }));
  return chairs.length > 0 ? chairs : null;
}
