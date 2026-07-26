import { Canvas, useThree, type ThreeEvent } from "@react-three/fiber";
import { Grid, OrbitControls, TransformControls } from "@react-three/drei";
import { Component, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from "react";
import * as THREE from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import type { TransformControls as TransformControlsImpl } from "three-stdlib";
import { avatarScaleFromManifest, resolveAssetUrl } from "../avatarAssets";
import { useLocale } from "../i18n";
import { DEFAULT_CAMERA, round3, roundSeatPose, seatPosesEqual, type SeatLayout, type SeatPose } from "../sceneLayout";
import { ensureKtx2Loader } from "../hooks/gltfKtx2";
import EditorGltfModel from "./EditorGltfModel";
import { useTransformOrbitSync, type EditorToolMode } from "./editorSceneControls";

export type LayoutSubject = {
  id: string;
  label: string;
  manifest?: Record<string, unknown>;
};

type TransformMode = "translate" | "rotate" | "scale";

type Props = {
  subjects: LayoutSubject[];
  seatLayout: SeatLayout;
  onChange: (layout: SeatLayout) => void;
  onResetDefaults: () => void;
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

function MeetingRoomShell() {
  return (
    <>
      <hemisphereLight args={["#fff8ef", "#8a7f72", 0.55]} />
      <ambientLight intensity={0.45} />
      <directionalLight position={[2, 6, 3]} intensity={0.75} castShadow />
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow position={[0, 0, 0]}>
        <planeGeometry args={[14, 14]} />
        <meshStandardMaterial color="#b8a898" roughness={0.92} />
      </mesh>
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
      <mesh position={[0, 2.2, -5.2]} receiveShadow>
        <planeGeometry args={[14, 4.8]} />
        <meshStandardMaterial color="#f2f2f0" />
      </mesh>
      <mesh position={[0, 0.75, -0.4]} castShadow receiveShadow>
        <boxGeometry args={[3.8, 0.08, 1.65]} />
        <meshStandardMaterial color="#6b4f3a" roughness={0.72} />
      </mesh>
      <mesh position={[0, 0.795, -0.4]} receiveShadow>
        <boxGeometry args={[1.6, 0.012, 0.38]} />
        <meshStandardMaterial color="#4a3728" />
      </mesh>
    </>
  );
}

function seatFromGroup(group: THREE.Group): SeatPose {
  return roundSeatPose({
    position: [group.position.x, group.position.y, group.position.z],
    rotationY: group.rotation.y,
    scale: Math.min(2, Math.max(0.4, group.scale.x)),
  });
}

function applySeatToGroup(group: THREE.Group, seat: SeatPose) {
  group.position.set(seat.position[0], seat.position[1], seat.position[2]);
  group.rotation.set(0, seat.rotationY, 0);
  group.scale.setScalar(seat.scale ?? 1);
  group.updateMatrixWorld(true);
}

type EditableSubjectProps = {
  id: string;
  modelUrl?: string;
  manifestScale: number;
  seat: SeatPose;
  selected: boolean;
  showGizmo: boolean;
  mode: TransformMode;
  orbitRef: RefObject<OrbitControlsImpl | null>;
  onSelect: (id: string) => void;
  onSeatChange: (id: string, seat: SeatPose) => void;
  onDragging: (dragging: boolean) => void;
};

function EditableSubject({
  id,
  modelUrl,
  manifestScale,
  seat,
  selected,
  showGizmo,
  mode,
  orbitRef,
  onSelect,
  onSeatChange,
  onDragging,
}: EditableSubjectProps) {
  const groupRef = useRef<THREE.Group>(null);
  const transformRef = useRef<TransformControlsImpl>(null);
  const draggingRef = useRef(false);
  const seatRef = useRef(seat);
  const [controlTarget, setControlTarget] = useState<THREE.Object3D | null>(null);
  seatRef.current = seat;

  const publish = useCallback(() => {
    const group = groupRef.current;
    if (!group) return;
    const next = seatFromGroup(group);
    if (seatPosesEqual(seatRef.current, next)) return;
    onSeatChange(id, next);
  }, [id, onSeatChange]);

  useTransformOrbitSync(transformRef, orbitRef, !!controlTarget, onDragging, publish);

  useLayoutEffect(() => {
    const group = groupRef.current;
    if (!group) return;
    if (!draggingRef.current) applySeatToGroup(group, seat);
    setControlTarget(selected && showGizmo ? group : null);
  }, [selected, showGizmo, seat]);

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
          <EditorGltfModel url={modelUrl} instanceId={id} manifestScale={manifestScale} />
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

type SceneProps = {
  subjects: LayoutSubject[];
  seatLayout: SeatLayout;
  selectedId: string | null;
  tool: EditorToolMode;
  orbitEnabled: boolean;
  onSelect: (id: string | null) => void;
  onSeatChange: (id: string, seat: SeatPose) => void;
  onDragging: (dragging: boolean) => void;
  captureToken: number;
  onCaptureCamera: (pos: [number, number, number], distance: number) => void;
};

function LayoutScene({
  subjects,
  seatLayout,
  selectedId,
  tool,
  orbitEnabled,
  onSelect,
  onSeatChange,
  onDragging,
  captureToken,
  onCaptureCamera,
}: SceneProps) {
  const orbitRef = useRef<OrbitControlsImpl>(null);
  const showGizmo = tool !== "view";
  const transformMode: TransformMode = tool === "view" ? "translate" : tool;

  return (
    <>
      <color attach="background" args={["#d8cfc4"]} />
      <fog attach="fog" args={["#d8cfc4", 10, 22]} />
      <MeetingRoomShell />
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
      {subjects.map((subject) => {
        const seat = seatLayout.seats[subject.id];
        if (!seat) return null;
        const modelUrl = resolveAssetUrl(
          typeof subject.manifest?.model_url === "string" ? subject.manifest.model_url : undefined,
        );
        return (
          <EditableSubject
            key={subject.id}
            id={subject.id}
            modelUrl={modelUrl}
            manifestScale={avatarScaleFromManifest(subject.manifest)}
            seat={seat}
            selected={selectedId === subject.id}
            showGizmo={showGizmo}
            mode={transformMode}
            orbitRef={orbitRef}
            onSelect={onSelect}
            onSeatChange={onSeatChange}
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
    // Only capture on explicit button click — not when orbiting.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [captureToken]);

  return null;
}

export default function SeatLayoutPreview({ subjects, seatLayout, onChange, onResetDefaults }: Props) {
  const { t } = useLocale();
  const [selectedId, setSelectedId] = useState<string | null>(subjects[0]?.id ?? null);
  const [tool, setTool] = useState<EditorToolMode>("view");
  const [orbitEnabled, setOrbitEnabled] = useState(true);
  const [captureToken, setCaptureToken] = useState(0);
  const layoutRef = useRef(seatLayout);
  layoutRef.current = seatLayout;

  useEffect(() => {
    if (selectedId && subjects.some((s) => s.id === selectedId)) return;
    setSelectedId(subjects[0]?.id ?? null);
  }, [subjects, selectedId]);

  const updateSeat = useCallback(
    (id: string, seat: SeatPose) => {
      const layout = layoutRef.current;
      const prev = layout.seats[id];
      if (prev && seatPosesEqual(prev, seat)) return;
      onChange({
        ...layout,
        seats: { ...layout.seats, [id]: seat },
      });
    },
    [onChange],
  );

  const captureCamera = useCallback(
    (position: [number, number, number], distance: number) => {
      const layout = layoutRef.current;
      const full = { ...DEFAULT_CAMERA.full, ...layout.camera?.full };
      onChange({
        ...layout,
        camera: {
          ...layout.camera,
          full: { ...full, position, distance },
          compact: layout.camera?.compact,
        },
      });
    },
    [onChange],
  );

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

  const selectedLabel = subjects.find((s) => s.id === selectedId)?.label ?? "—";

  return (
    <section className="seat-layout-preview">
      <div className="section-header">
        <div>
          <h2>{t.sceneVisual.previewSection}</h2>
          <p className="muted">{t.sceneVisual.previewHint}</p>
        </div>
        <button type="button" className="btn" onClick={onResetDefaults}>
          {t.sceneVisual.resetSeatDefaults}
        </button>
      </div>

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
          {t.sceneVisual.selectedCharacter.replace("{name}", selectedLabel)}
        </span>
        <button type="button" className="btn" onClick={() => setCaptureToken((n) => n + 1)}>
          {t.sceneVisual.captureCamera}
        </button>
      </div>

      <div className="seat-layout-body">
        <aside className="seat-layout-char-list" aria-label={t.sceneVisual.characterList}>
          {subjects.map((subject) => (
            <button
              key={subject.id}
              type="button"
              className={`seat-layout-char-btn${selectedId === subject.id ? " active" : ""}`}
              onClick={() => setSelectedId(subject.id)}
            >
              <strong>{subject.label}</strong>
              <code>{subject.id}</code>
            </button>
          ))}
        </aside>

        <div className="seat-layout-canvas">
          <PreviewErrorBoundary>
            <Canvas
              style={{ width: "100%", height: "100%", minHeight: 520 }}
              shadows
              camera={{ position: INITIAL_CAMERA.position, fov: INITIAL_CAMERA.fov }}
              dpr={[1, 1.5]}
              gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
              onPointerMissed={() => setSelectedId(null)}
              onCreated={({ gl }) => {
                ensureKtx2Loader(gl);
                gl.setClearColor("#d8cfc4");
                gl.outputColorSpace = THREE.SRGBColorSpace;
                gl.toneMapping = THREE.ACESFilmicToneMapping;
                gl.toneMappingExposure = 1.05;
              }}
            >
              <LayoutScene
                subjects={subjects}
                seatLayout={seatLayout}
                selectedId={selectedId}
                tool={tool}
                orbitEnabled={orbitEnabled}
                onSelect={setSelectedId}
                onSeatChange={updateSeat}
                onDragging={(dragging) => setOrbitEnabled(!dragging)}
                captureToken={captureToken}
                onCaptureCamera={captureCamera}
              />
            </Canvas>
          </PreviewErrorBoundary>
        </div>
      </div>
    </section>
  );
}
