import * as THREE from "three";
import type { Character } from "./api";
import { DEFAULT_CAMERA, round3, type CameraPreset, type SeatLayout } from "./sceneLayout";

export type AssetCategory = "environment" | "furniture" | "avatar_slot" | "decor";
export type InstanceRole = "environment" | "prop" | "avatar_slot";
export type ConstraintMode = "attach" | "position_only" | "inherit_scale";

export type SceneTransform = {
  position: [number, number, number];
  rotationY: number;
  scale: number;
};

export type SceneAsset = {
  model_url: string;
  label: string;
  category: AssetCategory;
  default_scale?: number;
};

export type SceneInstance = {
  id: string;
  asset_id: string;
  role: InstanceRole;
  editor_label: string;
  transform: SceneTransform;
  locked?: boolean;
};

export type SceneConstraint = {
  id: string;
  child_id: string;
  parent_id: string;
  mode: ConstraintMode;
  inherit: Array<"position" | "rotationY" | "scale">;
  offset: SceneTransform;
};

export type SceneGraph = {
  version: number;
  assets: Record<string, SceneAsset>;
  instances: SceneInstance[];
  constraints: SceneConstraint[];
  camera?: {
    compact?: Partial<CameraPreset>;
    full?: Partial<CameraPreset>;
  };
};

export type PlotCastBinding = {
  character_id: string;
  instance_id: string;
};

export type WorldInstance = SceneInstance & {
  world: SceneTransform;
  model_url: string;
};

const DEFAULT_TRANSFORM: SceneTransform = {
  position: [0, 0, 0],
  rotationY: 0,
  scale: 1,
};

export function roundTransform(t: SceneTransform): SceneTransform {
  return {
    position: [round3(t.position[0]), round3(t.position[1]), round3(t.position[2])],
    rotationY: round3(t.rotationY),
    scale: round3(t.scale),
  };
}

export function transformsEqual(a: SceneTransform, b: SceneTransform): boolean {
  const ra = roundTransform(a);
  const rb = roundTransform(b);
  return (
    ra.position[0] === rb.position[0] &&
    ra.position[1] === rb.position[1] &&
    ra.position[2] === rb.position[2] &&
    ra.rotationY === rb.rotationY &&
    ra.scale === rb.scale
  );
}

export function createEmptySceneGraph(): SceneGraph {
  return {
    version: 1,
    assets: {},
    instances: [],
    constraints: [],
    camera: {
      compact: { ...DEFAULT_CAMERA.compact },
      full: { ...DEFAULT_CAMERA.full },
    },
  };
}

export function newAssetId(): string {
  return `asset_${Math.random().toString(36).slice(2, 10)}`;
}

export function newInstanceId(): string {
  return `inst_${Math.random().toString(36).slice(2, 10)}`;
}

export function newConstraintId(): string {
  return `cst_${Math.random().toString(36).slice(2, 10)}`;
}

function sanitizeTransform(raw: unknown): SceneTransform {
  if (!raw || typeof raw !== "object") return { ...DEFAULT_TRANSFORM };
  const o = raw as Record<string, unknown>;
  const pos = Array.isArray(o.position) ? o.position : [0, 0, 0];
  const scale = typeof o.scale === "number" ? o.scale : 1;
  return roundTransform({
    position: [
      typeof pos[0] === "number" ? pos[0] : 0,
      typeof pos[1] === "number" ? pos[1] : 0,
      typeof pos[2] === "number" ? pos[2] : 0,
    ],
    rotationY: typeof o.rotationY === "number" ? o.rotationY : 0,
    scale: Math.min(3, Math.max(0.1, scale)),
  });
}

export function sanitizeSceneGraph(raw: unknown): SceneGraph {
  if (!raw || typeof raw !== "object") return createEmptySceneGraph();
  const o = raw as Record<string, unknown>;
  const assets: Record<string, SceneAsset> = {};
  const assetsRaw = o.assets;
  if (assetsRaw && typeof assetsRaw === "object") {
    for (const [key, item] of Object.entries(assetsRaw)) {
      if (!item || typeof item !== "object") continue;
      const a = item as Record<string, unknown>;
      const url = typeof a.model_url === "string" ? a.model_url.trim() : "";
      const cat = typeof a.category === "string" ? a.category : "decor";
      const category = (["environment", "furniture", "avatar_slot", "decor"].includes(cat)
        ? cat
        : "decor") as AssetCategory;
      if (!url && category !== "avatar_slot") continue;
      assets[key] = {
        model_url: url,
        label: typeof a.label === "string" ? a.label : key,
        category,
        default_scale:
          typeof a.default_scale === "number" ? Math.min(3, Math.max(0.1, a.default_scale)) : 1,
      };
    }
  }

  const instances: SceneInstance[] = [];
  const instancesRaw = o.instances;
  if (Array.isArray(instancesRaw)) {
    for (const item of instancesRaw) {
      if (!item || typeof item !== "object") continue;
      const inst = item as Record<string, unknown>;
      const id = typeof inst.id === "string" ? inst.id.trim() : "";
      const assetId = typeof inst.asset_id === "string" ? inst.asset_id.trim() : "";
      if (!id || !assetId || !assets[assetId]) continue;
      const roleRaw = typeof inst.role === "string" ? inst.role : assets[assetId].category;
      instances.push({
        id,
        asset_id: assetId,
        role: (["environment", "prop", "avatar_slot"].includes(roleRaw)
          ? roleRaw
          : "prop") as InstanceRole,
        editor_label: typeof inst.editor_label === "string" ? inst.editor_label : id,
        transform: sanitizeTransform(inst.transform),
        locked: !!inst.locked,
      });
    }
  }

  const instanceIds = new Set(instances.map((i) => i.id));
  const constraints: SceneConstraint[] = [];
  const constraintsRaw = o.constraints;
  if (Array.isArray(constraintsRaw)) {
    for (const item of constraintsRaw) {
      if (!item || typeof item !== "object") continue;
      const c = item as Record<string, unknown>;
      const id = typeof c.id === "string" ? c.id.trim() : "";
      const child = typeof c.child_id === "string" ? c.child_id.trim() : "";
      const parent = typeof c.parent_id === "string" ? c.parent_id.trim() : "";
      if (!id || !child || !parent || child === parent || !instanceIds.has(child) || !instanceIds.has(parent))
        continue;
      const mode = typeof c.mode === "string" ? c.mode : "attach";
      const inheritRaw = Array.isArray(c.inherit) ? c.inherit : null;
      let inherit: SceneConstraint["inherit"] = ["position", "rotationY", "scale"];
      if (inheritRaw) {
        inherit = inheritRaw.filter((x): x is "position" | "rotationY" | "scale" =>
          x === "position" || x === "rotationY" || x === "scale",
        );
      }
      if (!inherit.length) {
        inherit = mode === "position_only" ? ["position"] : ["position", "rotationY", "scale"];
      }
      constraints.push({
        id,
        child_id: child,
        parent_id: parent,
        mode: (["attach", "position_only", "inherit_scale"].includes(mode)
          ? mode
          : "attach") as ConstraintMode,
        inherit,
        offset: sanitizeTransform(c.offset),
      });
    }
  }

  const cameraRaw = o.camera;
  const camera =
    cameraRaw && typeof cameraRaw === "object"
      ? (cameraRaw as SceneGraph["camera"])
      : { compact: { ...DEFAULT_CAMERA.compact }, full: { ...DEFAULT_CAMERA.full } };

  return {
    version: typeof o.version === "number" ? o.version : 1,
    assets,
    instances,
    constraints,
    camera,
  };
}

export function sanitizePlotCastBinding(raw: unknown): PlotCastBinding[] {
  if (!Array.isArray(raw)) return [];
  const out: PlotCastBinding[] = [];
  const seenChar = new Set<string>();
  const seenInst = new Set<string>();
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const o = item as Record<string, unknown>;
    const character_id = typeof o.character_id === "string" ? o.character_id.trim() : "";
    const instance_id = typeof o.instance_id === "string" ? o.instance_id.trim() : "";
    if (!character_id || !instance_id || seenChar.has(character_id) || seenInst.has(instance_id)) continue;
    seenChar.add(character_id);
    seenInst.add(instance_id);
    out.push({ character_id, instance_id });
  }
  return out;
}

export function bindingByCharacter(bindings: PlotCastBinding[]): Map<string, string> {
  return new Map(bindings.map((b) => [b.character_id, b.instance_id]));
}

export function characterByInstance(bindings: PlotCastBinding[]): Map<string, string> {
  return new Map(bindings.map((b) => [b.instance_id, b.character_id]));
}

/** Uploaded office chair used in negotiation-room defaults. */
export const DEFAULT_OFFICE_CHAIR_URL = "/static/props/office_chair-1-41805a48-web.glb";

export const CHAIR_FIT_HEIGHT = 1.05;
export const CHAIR_GROUP_SCALE = 0.88;

const NEGOTIATION_CHAIR_POSES: Array<{
  id: string;
  label: string;
  position: [number, number, number];
  rotationY: number;
  scale: number;
}> = [
  { id: "chair_nw", label: "chair_north_west", position: [-0.58, 0, -1.34], rotationY: Math.PI, scale: CHAIR_GROUP_SCALE },
  { id: "chair_ne", label: "chair_north_east", position: [0.58, 0, -1.34], rotationY: Math.PI, scale: CHAIR_GROUP_SCALE },
  { id: "chair_sw", label: "chair_south_west", position: [-0.58, 0, 0.58], rotationY: 0, scale: CHAIR_GROUP_SCALE },
  { id: "chair_se", label: "chair_south_east", position: [0.58, 0, 0.58], rotationY: 0, scale: CHAIR_GROUP_SCALE },
];

export function isChairAssetUrl(url: string): boolean {
  const trimmed = url.trim().toLowerCase();
  if (!trimmed) return false;
  if (trimmed.includes("conference_table") || trimmed.includes("meeting_table")) return false;
  return trimmed.includes("office_chair") || trimmed.includes("chair");
}

/** Ensure four negotiation chairs exist when migrating or seeding a meeting layout. */
export function ensureNegotiationChairs(graph: SceneGraph): SceneGraph {
  let chairAssetId =
    Object.entries(graph.assets).find(([, asset]) => isChairAssetUrl(asset.model_url))?.[0] ?? null;

  const assets = { ...graph.assets };
  if (!chairAssetId) {
    chairAssetId = "asset_office_chair";
    assets[chairAssetId] = {
      model_url: DEFAULT_OFFICE_CHAIR_URL,
      label: chairAssetId,
      category: "furniture",
      default_scale: 1,
    };
  }

  const chairPoseById = new Map(NEGOTIATION_CHAIR_POSES.map((pose) => [pose.id, pose]));
  const instances = graph.instances.map((inst) => {
    if (inst.asset_id !== chairAssetId) return inst;
    const pose = chairPoseById.get(inst.id);
    if (!pose) return inst;
    return {
      ...inst,
      transform: {
        position: [...pose.position],
        rotationY: pose.rotationY,
        scale: pose.scale,
      },
    };
  });
  const existingChairIds = new Set(
    instances.filter((inst) => inst.asset_id === chairAssetId).map((inst) => inst.id),
  );
  for (const pose of NEGOTIATION_CHAIR_POSES) {
    if (existingChairIds.has(pose.id)) continue;
    instances.push({
      id: pose.id,
      asset_id: chairAssetId,
      role: "prop",
      editor_label: pose.label,
      transform: {
        position: [...pose.position],
        rotationY: pose.rotationY,
        scale: pose.scale,
      },
    });
  }

  return { ...graph, assets, instances };
}

export function migrateSeatLayoutToSceneGraph(seatLayout: SeatLayout): SceneGraph {
  const graph = createEmptySceneGraph();
  graph.camera = {
    compact: { ...DEFAULT_CAMERA.compact, ...seatLayout.camera?.compact },
    full: { ...DEFAULT_CAMERA.full, ...seatLayout.camera?.full },
  };

  const placeholderId = newAssetId();
  graph.assets[placeholderId] = {
    model_url: "",
    label: placeholderId,
    category: "avatar_slot",
    default_scale: 1,
  };

  for (const [seatId, pose] of Object.entries(seatLayout.seats || {})) {
    graph.instances.push({
      id: `slot_${seatId}`,
      asset_id: placeholderId,
      role: "avatar_slot",
      editor_label: `slot_${seatId}`,
      transform: {
        position: [...pose.position] as [number, number, number],
        rotationY: pose.rotationY,
        scale: pose.scale ?? 1,
      },
    });
  }
  return graph;
}

export function resolveSceneGraph(sceneConfig: Record<string, unknown> | undefined | null): SceneGraph | null {
  if (!sceneConfig || typeof sceneConfig !== "object") return null;
  const raw = sceneConfig.scene_graph;
  if (raw && typeof raw === "object") {
    const graph = sanitizeSceneGraph(raw);
    if (graph.instances.length > 0 || Object.keys(graph.assets).length > 0) return graph;
  }
  return null;
}

function transformToMatrix(t: SceneTransform): THREE.Matrix4 {
  const m = new THREE.Matrix4();
  const pos = new THREE.Vector3(t.position[0], t.position[1], t.position[2]);
  const quat = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), t.rotationY);
  const scale = new THREE.Vector3(t.scale, t.scale, t.scale);
  m.compose(pos, quat, scale);
  return m;
}

function matrixToTransform(m: THREE.Matrix4): SceneTransform {
  const pos = new THREE.Vector3();
  const quat = new THREE.Quaternion();
  const scale = new THREE.Vector3();
  m.decompose(pos, quat, scale);
  const euler = new THREE.Euler().setFromQuaternion(quat, "YXZ");
  return roundTransform({
    position: [pos.x, pos.y, pos.z],
    rotationY: euler.y,
    scale: Math.min(3, Math.max(0.1, scale.x)),
  });
}

function composeConstrained(
  parent: SceneTransform,
  offset: SceneTransform,
  mode: ConstraintMode,
): SceneTransform {
  if (mode === "attach" || mode === "inherit_scale") {
    const pm = transformToMatrix(parent);
    const om = transformToMatrix(offset);
    const wm = new THREE.Matrix4().multiplyMatrices(pm, om);
    const world = matrixToTransform(wm);
    if (mode === "inherit_scale") {
      return { ...world, scale: roundTransform({ ...world, scale: parent.scale * offset.scale }).scale };
    }
    return world;
  }
  const rotated = new THREE.Vector3(offset.position[0], offset.position[1], offset.position[2]).applyAxisAngle(
    new THREE.Vector3(0, 1, 0),
    parent.rotationY,
  );
  return roundTransform({
    position: [parent.position[0] + rotated.x, parent.position[1] + rotated.y, parent.position[2] + rotated.z],
    rotationY: offset.rotationY,
    scale: offset.scale,
  });
}

export function getConstraintForChild(graph: SceneGraph, childId: string): SceneConstraint | undefined {
  return graph.constraints.find((c) => c.child_id === childId);
}

export function computeWorldTransforms(graph: SceneGraph): Map<string, SceneTransform> {
  const byId = new Map(graph.instances.map((i) => [i.id, i]));
  const constraintByChild = new Map(graph.constraints.map((c) => [c.child_id, c]));
  const cache = new Map<string, SceneTransform>();
  const visiting = new Set<string>();

  const resolve = (id: string): SceneTransform => {
    const cached = cache.get(id);
    if (cached) return cached;
    if (visiting.has(id)) return { ...DEFAULT_TRANSFORM };
    visiting.add(id);
    const inst = byId.get(id);
    if (!inst) {
      visiting.delete(id);
      return { ...DEFAULT_TRANSFORM };
    }
    const constraint = constraintByChild.get(id);
    let world: SceneTransform;
    if (constraint) {
      const parentWorld = resolve(constraint.parent_id);
      world = composeConstrained(parentWorld, constraint.offset, constraint.mode);
    } else {
      world = { ...inst.transform };
    }
    cache.set(id, world);
    visiting.delete(id);
    return world;
  };

  for (const inst of graph.instances) resolve(inst.id);
  return cache;
}

export function resolveWorldInstances(graph: SceneGraph): WorldInstance[] {
  const worlds = computeWorldTransforms(graph);
  return graph.instances
    .map((inst) => {
      const asset = graph.assets[inst.asset_id];
      if (!asset?.model_url) return null;
      return {
        ...inst,
        world: worlds.get(inst.id) || inst.transform,
        model_url: asset.model_url,
      };
    })
    .filter((x): x is WorldInstance => !!x);
}

export function spawnInstanceFromAsset(graph: SceneGraph, assetId: string, label?: string): SceneGraph {
  const asset = graph.assets[assetId];
  if (!asset) return graph;
  const role: InstanceRole =
    asset.category === "environment" ? "environment" : asset.category === "avatar_slot" ? "avatar_slot" : "prop";
  const instId = newInstanceId();
  const inst: SceneInstance = {
    id: instId,
    asset_id: assetId,
    role,
    editor_label: label || instId,
    transform: {
      position: [0, 0, 0],
      rotationY: 0,
      scale: asset.default_scale ?? 1,
    },
    locked: asset.category === "environment",
  };
  return { ...graph, instances: [...graph.instances, inst] };
}

export function removeInstance(graph: SceneGraph, instanceId: string): SceneGraph {
  return {
    ...graph,
    instances: graph.instances.filter((i) => i.id !== instanceId),
    constraints: graph.constraints.filter((c) => c.child_id !== instanceId && c.parent_id !== instanceId),
  };
}

export function instancesForAsset(graph: SceneGraph, assetId: string): SceneInstance[] {
  return graph.instances.filter((i) => i.asset_id === assetId);
}

export function updateAsset(
  graph: SceneGraph,
  assetId: string,
  patch: Partial<SceneAsset>,
): SceneGraph {
  const current = graph.assets[assetId];
  if (!current) return graph;
  const category = patch.category ?? current.category;
  const next: SceneAsset = {
    ...current,
    ...patch,
    category,
    default_scale:
      patch.default_scale != null
        ? Math.min(3, Math.max(0.1, patch.default_scale))
        : current.default_scale,
  };
  const instances = graph.instances.map((inst) => {
    if (inst.asset_id !== assetId) return inst;
    const role: InstanceRole =
      category === "environment" ? "environment" : category === "avatar_slot" ? "avatar_slot" : "prop";
    return {
      ...inst,
      role,
      locked: category === "environment" ? true : inst.locked,
    };
  });
  return { ...graph, assets: { ...graph.assets, [assetId]: next }, instances };
}

export function removeAsset(graph: SceneGraph, assetId: string): SceneGraph {
  const instanceIds = new Set(instancesForAsset(graph, assetId).map((i) => i.id));
  const assets = { ...graph.assets };
  delete assets[assetId];
  return {
    ...graph,
    assets,
    instances: graph.instances.filter((i) => i.asset_id !== assetId),
    constraints: graph.constraints.filter(
      (c) => !instanceIds.has(c.child_id) && !instanceIds.has(c.parent_id),
    ),
  };
}

export function prunePlotBindings(bindings: PlotCastBinding[], graph: SceneGraph): PlotCastBinding[] {
  const instanceIds = new Set(graph.instances.map((i) => i.id));
  return bindings.filter((b) => instanceIds.has(b.instance_id));
}

export function addAsset(
  graph: SceneGraph,
  asset: SceneAsset,
  assetId: string = newAssetId(),
): { graph: SceneGraph; assetId: string } {
  return {
    graph: { ...graph, assets: { ...graph.assets, [assetId]: asset } },
    assetId,
  };
}

export function updateInstanceTransform(
  graph: SceneGraph,
  instanceId: string,
  transform: SceneTransform,
): SceneGraph {
  return {
    ...graph,
    instances: graph.instances.map((i) =>
      i.id === instanceId ? { ...i, transform: roundTransform(transform) } : i,
    ),
  };
}

export function updateConstraintOffset(
  graph: SceneGraph,
  childId: string,
  offset: SceneTransform,
): SceneGraph {
  return {
    ...graph,
    constraints: graph.constraints.map((c) =>
      c.child_id === childId ? { ...c, offset: roundTransform(offset) } : c,
    ),
  };
}

export function addConstraint(
  graph: SceneGraph,
  childId: string,
  parentId: string,
  mode: ConstraintMode = "attach",
): SceneGraph {
  if (childId === parentId) return graph;
  const filtered = graph.constraints.filter((c) => c.child_id !== childId);
  const inherit: SceneConstraint["inherit"] =
    mode === "position_only" ? ["position"] : ["position", "rotationY", "scale"];
  const child = graph.instances.find((i) => i.id === childId);
  return {
    ...graph,
    constraints: [
      ...filtered,
      {
        id: newConstraintId(),
        child_id: childId,
        parent_id: parentId,
        mode,
        inherit,
        offset: child ? { ...child.transform } : { ...DEFAULT_TRANSFORM },
      },
    ],
  };
}

export function removeConstraint(graph: SceneGraph, childId: string): SceneGraph {
  const constraint = getConstraintForChild(graph, childId);
  if (!constraint) return graph;
  return {
    ...graph,
    instances: graph.instances.map((i) =>
      i.id === childId ? { ...i, transform: { ...constraint.offset } } : i,
    ),
    constraints: graph.constraints.filter((c) => c.child_id !== childId),
  };
}

export function getEditableTransform(graph: SceneGraph, instanceId: string): SceneTransform {
  const constraint = getConstraintForChild(graph, instanceId);
  if (constraint) return { ...constraint.offset };
  const inst = graph.instances.find((i) => i.id === instanceId);
  return inst ? { ...inst.transform } : { ...DEFAULT_TRANSFORM };
}

export function setEditableTransform(
  graph: SceneGraph,
  instanceId: string,
  transform: SceneTransform,
): SceneGraph {
  const constraint = getConstraintForChild(graph, instanceId);
  if (constraint) return updateConstraintOffset(graph, instanceId, transform);
  return updateInstanceTransform(graph, instanceId, transform);
}

export function worldToEditableTransform(
  graph: SceneGraph,
  instanceId: string,
  world: SceneTransform,
): SceneTransform {
  const constraint = getConstraintForChild(graph, instanceId);
  if (!constraint) return roundTransform(world);
  const worlds = computeWorldTransforms(graph);
  const parentWorld = worlds.get(constraint.parent_id);
  if (!parentWorld) return roundTransform(world);
  const invParent = new THREE.Matrix4().copy(transformToMatrix(parentWorld)).invert();
  const local = new THREE.Matrix4().multiplyMatrices(invParent, transformToMatrix(world));
  return matrixToTransform(local);
}

export function listAvatarSlotInstances(graph: SceneGraph): SceneInstance[] {
  return graph.instances.filter((i) => i.role === "avatar_slot");
}

export function resolveBindingModelUrl(
  graph: SceneGraph,
  instanceId: string,
  plotManifest?: Record<string, unknown> | null,
): string | undefined {
  const plotUrl = typeof plotManifest?.model_url === "string" ? plotManifest.model_url.trim() : "";
  if (plotUrl) return plotUrl;
  const inst = graph.instances.find((i) => i.id === instanceId);
  if (!inst) return undefined;
  return graph.assets[inst.asset_id]?.model_url;
}

export function buildPlotCharacterList(
  characters: Character[],
  playerCharacter?: Record<string, unknown> | null,
): Array<{ character_id: string; label: string }> {
  const list: Array<{ character_id: string; label: string }> = characters
    .filter((c) => c.character_id)
    .map((c) => ({
      character_id: c.character_id,
      label: c.character_name || c.character_id,
    }));
  if (playerCharacter && typeof playerCharacter === "object") {
    const name = String(playerCharacter.character_name || "Player");
    list.push({ character_id: "user", label: name });
  }
  return list;
}

export function upsertPlotBinding(
  bindings: PlotCastBinding[],
  characterId: string,
  instanceId: string,
): PlotCastBinding[] {
  const without = bindings.filter(
    (b) => b.character_id !== characterId && b.instance_id !== instanceId,
  );
  if (!instanceId) return without;
  return [...without, { character_id: characterId, instance_id: instanceId }];
}
