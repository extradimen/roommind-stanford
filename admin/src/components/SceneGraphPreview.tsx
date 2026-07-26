import { Canvas, useThree, type ThreeEvent } from "@react-three/fiber";
import { Grid, OrbitControls, TransformControls } from "@react-three/drei";
import { Component, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from "react";
import * as THREE from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import type { TransformControls as TransformControlsImpl } from "three-stdlib";
import { resolveAssetUrl, avatarScaleFromManifest } from "../avatarAssets";
import type { Character } from "../api";
import { useLocale } from "../i18n";
import { DEFAULT_CAMERA, round3 } from "../sceneLayout";
import {
  characterByInstance,
  computeWorldTransforms,
  resolveBindingModelUrl,
  roundTransform,
  transformsEqual,
  worldToEditableTransform,
  CHAIR_FIT_HEIGHT,
  isChairAssetUrl,
  type PlotCastBinding,
  type SceneGraph,
  type SceneTransform,
} from "../sceneGraph";
import { ensureKtx2Loader } from "../hooks/gltfKtx2";
import EditorGltfModel from "./EditorGltfModel";
import NumericInput from "./NumericInput";
import { useTransformOrbitSync, type EditorToolMode } from "./editorSceneControls";

type TransformMode = "translate" | "rotate" | "scale";

type Props = {
  graph: SceneGraph;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onTransformChange: (instanceId: string, transform: SceneTransform) => void;
  onCaptureCamera: (pos: [number, number, number], distance: number) => void;
  editableTransform?: SceneTransform | null;
  onEditablePatch?: (patch: Partial<SceneTransform>) => void;
  plotBindings?: import("../sceneGraph").PlotCastBinding[];
  characters?: import("../api").Character[];
  playerCharacter?: Record<string, unknown> | null;
};

const ORBIT_TARGET: [number, number, number] = [0, 1, -0.5];
const INITIAL_CAMERA = DEFAULT_CAMERA.full;

class PreviewErrorBoundary extends Component<{ children: ReactNode }, { error: string | null }> {
  state = { error: null as string | null };

  static getDerivedStateFromError(error: Error) {
    return { error: error.message || String(error) };
  }

  render() {
    if (this.state.error) {
      return <div className="seat-layout-error">3D 预览加载失败：{this.state.error}</div>;
    }
    return this.props.children;
  }
}

function radToDeg(r: number): number {
  return Math.round((r * 180) / Math.PI);
}

function degToRad(d: number): number {
  return (d * Math.PI) / 180;
}

function transformFromGroup(group: THREE.Group): SceneTransform {
  return roundTransform({
    position: [group.position.x, group.position.y, group.position.z],
    rotationY: group.rotation.y,
    scale: Math.min(3, Math.max(0.1, group.scale.x)),
  });
}

function applyTransformToGroup(group: THREE.Group, t: SceneTransform) {
  group.position.set(t.position[0], t.position[1], t.position[2]);
  group.rotation.set(0, t.rotationY, 0);
  group.scale.setScalar(t.scale);
  group.updateMatrixWorld(true);
}

type EditableInstanceProps = {
  id: string;
  modelUrl?: string;
  propFit?: boolean;
  fitHeight?: number;
  nativeScale?: boolean;
  manifestScale?: number;
  world: SceneTransform;
  selected: boolean;
  locked?: boolean;
  showGizmo: boolean;
  mode: TransformMode;
  orbitRef: RefObject<OrbitControlsImpl | null>;
  onSelect: (id: string) => void;
  onWorldChange: (id: string, world: SceneTransform) => void;
  onDragging: (dragging: boolean) => void;
};

function EditableInstance({
  id,
  modelUrl,
  propFit = false,
  fitHeight,
  nativeScale = false,
  manifestScale = 1,
  world,
  selected,
  locked,
  showGizmo,
  mode,
  orbitRef,
  onSelect,
  onWorldChange,
  onDragging,
}: EditableInstanceProps) {
  const groupRef = useRef<THREE.Group>(null);
  const transformRef = useRef<TransformControlsImpl>(null);
  const draggingRef = useRef(false);
  const worldRef = useRef(world);
  const [controlTarget, setControlTarget] = useState<THREE.Object3D | null>(null);
  worldRef.current = world;

  const publish = useCallback(() => {
    const group = groupRef.current;
    if (!group) return;
    const next = transformFromGroup(group);
    if (transformsEqual(worldRef.current, next)) return;
    onWorldChange(id, next);
  }, [id, onWorldChange]);

  useTransformOrbitSync(transformRef, orbitRef, !!controlTarget, onDragging, publish);

  useLayoutEffect(() => {
    const group = groupRef.current;
    if (!group) return;
    if (!draggingRef.current) applyTransformToGroup(group, world);
    setControlTarget(selected && !locked && showGizmo ? group : null);
  }, [selected, locked, showGizmo, world]);

  return (
    <>
      <group
        ref={groupRef}
        onClick={(event: ThreeEvent<MouseEvent>) => {
          event.stopPropagation();
          onSelect(id);
        }}
      >
        {modelUrl ? (
          <EditorGltfModel
            url={modelUrl}
            instanceId={id}
            manifestScale={manifestScale}
            propFit={propFit}
            fitHeight={fitHeight}
            nativeScale={nativeScale}
          />
        ) : (
          <mesh position={[0, 0.55, 0]}>
            <boxGeometry args={[0.45, 1.1, 0.32]} />
            <meshStandardMaterial color="#8b949e" transparent opacity={0.75} />
          </mesh>
        )}
        {selected && (
          <mesh position={[0, 0.04, 0]} rotation={[-Math.PI / 2, 0, 0]}>
            <ringGeometry args={[0.5, 0.58, 32]} />
            <meshBasicMaterial color="#58a6ff" transparent opacity={0.85} side={THREE.DoubleSide} />
          </mesh>
        )}
      </group>
      {controlTarget && (
        <TransformControls
          ref={transformRef}
          object={controlTarget}
          mode={mode}
          space={mode === "rotate" ? "local" : "world"}
          showX={mode !== "rotate"}
          showY={mode !== "rotate"}
          showZ={mode !== "rotate"}
          onMouseDown={() => {
            draggingRef.current = true;
          }}
          onMouseUp={() => {
            draggingRef.current = false;
            publish();
          }}
        />
      )}
    </>
  );
}

function SceneContent({
  graph,
  selectedId,
  tool,
  orbitEnabled,
  onSelect,
  onTransformChange,
  onDragging,
  captureToken,
  onCaptureCamera,
  plotBindings = [],
  characters = [],
  playerCharacter,
}: {
  graph: SceneGraph;
  selectedId: string | null;
  tool: EditorToolMode;
  orbitEnabled: boolean;
  onSelect: (id: string | null) => void;
  onTransformChange: (instanceId: string, world: SceneTransform) => void;
  onDragging: (dragging: boolean) => void;
  captureToken: number;
  onCaptureCamera: (pos: [number, number, number], distance: number) => void;
  plotBindings?: PlotCastBinding[];
  characters?: Character[];
  playerCharacter?: Record<string, unknown> | null;
}) {
  const orbitRef = useRef<OrbitControlsImpl>(null);
  const worlds = useMemo(() => computeWorldTransforms(graph), [graph]);
  const showGizmo = tool !== "view";
  const transformMode: TransformMode = tool === "view" ? "translate" : tool;
  const instToChar = useMemo(() => characterByInstance(plotBindings), [plotBindings]);
  const hasEnvironment = graph.instances.some(
    (i) => i.role === "environment" && !!resolveAssetUrl(graph.assets[i.asset_id]?.model_url),
  );

  const sorted = useMemo(() => {
    const order = { environment: 0, prop: 1, avatar_slot: 2 } as const;
    return [...graph.instances].sort((a, b) => (order[a.role] ?? 1) - (order[b.role] ?? 1));
  }, [graph.instances]);

  return (
    <>
      <color attach="background" args={["#d8cfc4"]} />
      <fog attach="fog" args={["#d8cfc4", 10, 22]} />
      <hemisphereLight args={["#fff8ef", "#8a7f72", 0.5]} />
      <ambientLight intensity={0.38} color="#fff5e8" />
      <directionalLight position={[1, 7, 4]} intensity={0.7} color="#fff2dc" castShadow />
      {!hasEnvironment && (
        <Grid
          args={[14, 14]}
          cellSize={0.5}
          cellThickness={0.4}
          sectionSize={2}
          sectionThickness={0.8}
          fadeDistance={18}
          position={[0, 0.01, 0]}
          infiniteGrid={false}
          raycast={() => null}
        />
      )}
      <OrbitControls
        makeDefault
        ref={orbitRef}
        enabled={orbitEnabled}
        target={ORBIT_TARGET}
        minDistance={2}
        maxDistance={14}
        mouseButtons={{
          LEFT: THREE.MOUSE.ROTATE,
          MIDDLE: THREE.MOUSE.DOLLY,
          RIGHT: THREE.MOUSE.ROTATE,
        }}
      />
      {sorted.map((inst) => {
        const asset = graph.assets[inst.asset_id];
        const assetUrl = resolveAssetUrl(asset?.model_url);
        const world = worlds.get(inst.id) || inst.transform;
        const isChair = assetUrl ? isChairAssetUrl(assetUrl) : false;
        const nativeScale = inst.role === "environment" || (!!assetUrl && !isChair);
        const boundChar = inst.role === "avatar_slot" ? instToChar.get(inst.id) : undefined;
        let displayUrl = assetUrl;
        let manifestScale = 1;
        if (boundChar) {
          const manifest =
            boundChar === "user"
              ? (playerCharacter?.avatar_manifest as Record<string, unknown> | undefined)
              : (characters.find((c) => c.character_id === boundChar)?.avatar_manifest as
                  | Record<string, unknown>
                  | undefined);
          const boundUrl = resolveBindingModelUrl(graph, inst.id, manifest);
          const resolved = boundUrl ? resolveAssetUrl(boundUrl) : undefined;
          if (resolved) {
            displayUrl = resolved;
            manifestScale = avatarScaleFromManifest(manifest);
          }
        }
        return (
          <EditableInstance
            key={inst.id}
            id={inst.id}
            modelUrl={displayUrl}
            propFit={isChair}
            fitHeight={isChair ? CHAIR_FIT_HEIGHT : undefined}
            nativeScale={nativeScale && !boundChar}
            manifestScale={manifestScale}
            world={world}
            selected={selectedId === inst.id}
            locked={inst.locked}
            showGizmo={showGizmo}
            mode={transformMode}
            orbitRef={orbitRef}
            onSelect={onSelect}
            onWorldChange={(id, nextWorld) => onTransformChange(id, nextWorld)}
            onDragging={onDragging}
          />
        );
      })}
      <CameraCaptureHelper captureToken={captureToken} onCapture={onCaptureCamera} />
    </>
  );
}

function CameraCaptureHelper({
  captureToken,
  onCapture,
}: {
  captureToken: number;
  onCapture: (pos: [number, number, number], distance: number) => void;
}) {
  const { camera } = useThree();
  const onCaptureRef = useRef(onCapture);
  onCaptureRef.current = onCapture;

  useEffect(() => {
    if (!captureToken) return;
    const target = new THREE.Vector3(...ORBIT_TARGET);
    const distance = camera.position.distanceTo(target);
    onCaptureRef.current(
      [round3(camera.position.x), round3(camera.position.y), round3(camera.position.z)],
      round3(distance),
    );
  }, [captureToken, camera]);

  return null;
}

export default function SceneGraphPreview({
  graph,
  selectedId,
  onSelect,
  onTransformChange,
  onCaptureCamera,
  editableTransform,
  onEditablePatch,
  plotBindings = [],
  characters = [],
  playerCharacter,
}: Props) {
  const { t } = useLocale();
  const [tool, setTool] = useState<EditorToolMode>("view");
  const [orbitEnabled, setOrbitEnabled] = useState(true);
  const [captureToken, setCaptureToken] = useState(0);
  const graphRef = useRef(graph);
  graphRef.current = graph;

  const handleWorldChange = useCallback(
    (instanceId: string, world: SceneTransform) => {
      const editable = worldToEditableTransform(graphRef.current, instanceId, world);
      onTransformChange(instanceId, editable);
    },
    [onTransformChange],
  );

  const selectedLabel = graph.instances.find((i) => i.id === selectedId)?.editor_label ?? "—";

  const modeButtons = useMemo(
    () =>
      [
        { id: "view" as const, label: t.sceneVisual.toolView },
        { id: "translate" as const, label: t.sceneVisual.toolMove },
        { id: "rotate" as const, label: t.sceneVisual.toolRotate },
        { id: "scale" as const, label: t.sceneVisual.toolScale },
      ] satisfies Array<{ id: EditorToolMode; label: string }>,
    [t.sceneVisual.toolView, t.sceneVisual.toolMove, t.sceneVisual.toolRotate, t.sceneVisual.toolScale],
  );

  return (
    <div className="seat-layout-preview">
      <div className="seat-layout-toolbar">
        <div className="seat-layout-tool-group">
          {modeButtons.map((btn) => (
            <button
              key={btn.id}
              type="button"
              className={`btn${tool === btn.id ? " primary" : ""}`}
              onClick={() => setTool(btn.id)}
            >
              {btn.label}
            </button>
          ))}
        </div>
        <span className="muted seat-layout-selected">
          {t.sceneVisual.selectedInstance.replace("{name}", selectedLabel)}
        </span>
        <button type="button" className="btn" onClick={() => setCaptureToken((n) => n + 1)}>
          {t.sceneVisual.captureCamera}
        </button>
      </div>

      {editableTransform && onEditablePatch && selectedId && tool !== "view" && (
        <div className="scene-transform-toolbar" aria-label={t.sceneVisual.transformNumeric}>
          <div className="scene-transform-field">
            <span>{t.sceneVisual.scale}</span>
            <NumericInput
              value={editableTransform.scale}
              step={0.05}
              min={0.1}
              max={3}
              onCommit={(v) => onEditablePatch({ scale: v })}
            />
            <input
              type="range"
              min={0.1}
              max={3}
              step={0.05}
              value={editableTransform.scale}
              onChange={(e) => onEditablePatch({ scale: parseFloat(e.target.value) })}
              aria-label={t.sceneVisual.scaleSlider}
            />
          </div>
          <div className="scene-transform-field">
            <span>{t.sceneVisual.rotationDeg}</span>
            <NumericInput
              value={radToDeg(editableTransform.rotationY)}
              step={1}
              onCommit={(v) => onEditablePatch({ rotationY: degToRad(v) })}
            />
          </div>
          <div className="scene-transform-field scene-transform-field-wide">
            <span>{t.sceneVisual.position}</span>
            {([0, 1, 2] as const).map((axis) => (
              <label key={axis} className="scene-axis-input">
                {axis === 0 ? "X" : axis === 1 ? "Y" : "Z"}
                <NumericInput
                  value={editableTransform.position[axis]}
                  step={0.01}
                  onCommit={(v) => {
                    const pos: [number, number, number] = [...editableTransform.position];
                    pos[axis] = v;
                    onEditablePatch({ position: pos });
                  }}
                />
              </label>
            ))}
          </div>
        </div>
      )}

      <div className="seat-layout-canvas">
        <PreviewErrorBoundary>
          <Canvas
            style={{ width: "100%", height: "100%", minHeight: 520 }}
            shadows
            camera={{ position: INITIAL_CAMERA.position, fov: INITIAL_CAMERA.fov }}
            dpr={[1, 1.5]}
            gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
            onPointerMissed={() => onSelect(null)}
            onCreated={({ gl }) => {
              ensureKtx2Loader(gl);
              gl.setClearColor("#d8cfc4");
              gl.outputColorSpace = THREE.SRGBColorSpace;
              gl.toneMapping = THREE.ACESFilmicToneMapping;
              gl.toneMappingExposure = 1.05;
            }}
          >
            <SceneContent
              graph={graph}
              selectedId={selectedId}
              tool={tool}
              orbitEnabled={orbitEnabled}
              onSelect={onSelect}
              onTransformChange={handleWorldChange}
              onDragging={(dragging) => setOrbitEnabled(!dragging)}
              captureToken={captureToken}
              onCaptureCamera={onCaptureCamera}
              plotBindings={plotBindings}
              characters={characters}
              playerCharacter={playerCharacter}
            />
          </Canvas>
        </PreviewErrorBoundary>
      </div>
    </div>
  );
}
