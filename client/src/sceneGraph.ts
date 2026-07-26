import * as THREE from "three";
import { DEFAULT_CAMERA, type CameraPreset } from "./sceneLayout";

function round3(n: number): number {
  return Math.round(n * 1000) / 1000;
}

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
      constraints.push({
        id,
        child_id: child,
        parent_id: parent,
        mode: (["attach", "position_only", "inherit_scale"].includes(mode)
          ? mode
          : "attach") as ConstraintMode,
        inherit: ["position", "rotationY", "scale"],
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

export function bindingByCharacter(bindings: PlotCastBinding[]): Map<string, string> {
  return new Map(bindings.map((b) => [b.character_id, b.instance_id]));
}

export function characterByInstance(bindings: PlotCastBinding[]): Map<string, string> {
  return new Map(bindings.map((b) => [b.instance_id, b.character_id]));
}

export function hasActiveSceneGraph(sceneConfig: Record<string, unknown> | undefined): boolean {
  const graph = resolveSceneGraph(sceneConfig);
  return !!graph && graph.instances.length > 0;
}

export function hasPlotCastBindings(sceneConfig: Record<string, unknown> | undefined): boolean {
  return sanitizePlotCastBinding(sceneConfig?.plot_cast_binding).length > 0;
}

export function hasEnvironmentInstance(graph: SceneGraph | null): boolean {
  if (!graph) return false;
  return graph.instances.some((i) => {
    if (i.role !== "environment") return false;
    return !!graph.assets[i.asset_id]?.model_url;
  });
}

export function collectBoundAvatarModelUrls(
  sceneConfig: Record<string, unknown> | undefined,
  characters: Array<{ character_id: string; avatar_manifest?: unknown }>,
  playerCharacter?: { avatar_manifest?: unknown } | null,
): string[] {
  const graph = resolveSceneGraph(sceneConfig);
  if (!graph) return [];
  const bindings = sanitizePlotCastBinding(sceneConfig?.plot_cast_binding);
  const instToChar = characterByInstance(bindings);
  const manifestByChar = new Map<string, Record<string, unknown> | undefined>();
  for (const c of characters) {
    manifestByChar.set(
      c.character_id,
      c.avatar_manifest && typeof c.avatar_manifest === "object"
        ? (c.avatar_manifest as Record<string, unknown>)
        : undefined,
    );
  }
  if (playerCharacter?.avatar_manifest && typeof playerCharacter.avatar_manifest === "object") {
    manifestByChar.set("user", playerCharacter.avatar_manifest as Record<string, unknown>);
  }

  const urls = new Set<string>();
  for (const inst of graph.instances) {
    if (inst.role !== "avatar_slot" || !instToChar.has(inst.id)) continue;
    const charId = instToChar.get(inst.id)!;
    const modelUrl = resolveBindingModelUrl(graph, inst.id, manifestByChar.get(charId));
    if (modelUrl) urls.add(modelUrl);
  }
  return [...urls];
}
