import { useMemo, useRef, type ReactNode } from "react";
import { useFrame } from "@react-three/fiber";
import { Text } from "@react-three/drei";
import * as THREE from "three";
import { fitSeatedGltfRoot } from "../gltfModelFit";
import { useLoadedGltf, type GltfLoadState } from "../hooks/useLoadedGltf";
import { useLocale } from "../i18n";

type Side = "opponent" | "player_ally" | "user";
type Pose = "stand" | "sit";

type Props = {
  url: string;
  instanceId: string;
  position: [number, number, number];
  manifestScale?: number;
  seatScale?: number;
  active?: boolean;
  name: string;
  sideLabel?: string;
  side?: Side;
  fallback?: ReactNode;
  pose?: Pose;
  rotationY?: number;
};

function fixMaterials(root: THREE.Object3D) {
  root.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.frustumCulled = false;
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    const clonedMats = materials.map((mat) => {
      if (!mat) return mat;
      const next = mat.clone();
      const record = next as THREE.MeshStandardMaterial & Record<string, THREE.Texture | undefined>;
      for (const key of ["map", "emissiveMap", "normalMap", "roughnessMap", "metalnessMap"] as const) {
        const tex = record[key];
        if (tex?.isTexture) tex.colorSpace = THREE.SRGBColorSpace;
      }
      return next;
    });
    mesh.material = Array.isArray(mesh.material) ? clonedMats : clonedMats[0]!;
  });
}

function LoadingPlaceholder({ position, sitting }: { position: [number, number, number]; sitting: boolean }) {
  return (
    <group position={position}>
      <mesh position={[0, sitting ? 0.55 : 0.85, 0]}>
        <boxGeometry args={[0.45, sitting ? 1.1 : 1.7, 0.32]} />
        <meshBasicMaterial color="#58a6ff" wireframe transparent opacity={0.55} />
      </mesh>
    </group>
  );
}

function GltfAvatarLabels({
  position,
  status,
  progress = 0,
  sitting,
  seatScale = 1,
}: Pick<Props, "position" | "seatScale"> & {
  status: GltfLoadState;
  progress?: number;
  sitting: boolean;
}) {
  const { t } = useLocale();
  const lift = seatScale;
  const statusY = (sitting ? 1.35 : 1.92) * lift;
  const statusColor = status === "loading" ? "#d29922" : status === "error" ? "#f85149" : "#58a6ff";
  const statusText =
    status === "loading"
      ? progress > 0
        ? t.game.avatarGlbLoadingPct.replace("{pct}", String(progress))
        : t.game.avatarGlbLoading
      : status === "error"
        ? t.game.avatarGlbFailed
        : t.game.avatarGlbReady;
  return (
    <>
      {status !== "ready" && (
        <Text position={[position[0], position[1] + statusY, position[2]]} fontSize={0.085} color={statusColor} anchorX="center" maxWidth={1.4}>
          {statusText}
        </Text>
      )}
    </>
  );
}

export default function GltfAvatarModel(props: Props) {
  const group = useRef<THREE.Group>(null);
  const { state, scene, progress } = useLoadedGltf(props.url, props.instanceId, 300000);
  const {
    position,
    manifestScale = 1,
    seatScale = 1,
    active = false,
    fallback,
    pose = "sit",
    rotationY = 0,
  } = props;
  const sitting = pose === "sit";

  const model = useMemo(() => {
    if (!scene) return null;
    const cloned = scene.clone(true);
    fixMaterials(cloned);
    if (sitting) {
      fitSeatedGltfRoot(cloned, manifestScale);
    } else {
      cloned.updateMatrixWorld(true);
      const box = new THREE.Box3().setFromObject(cloned);
      const size = box.getSize(new THREE.Vector3());
      const fitScale = (1.6 / Math.max(size.y, 0.001)) * manifestScale;
      cloned.scale.setScalar(fitScale);
      cloned.updateMatrixWorld(true);
      const fitted = new THREE.Box3().setFromObject(cloned);
      const c2 = fitted.getCenter(new THREE.Vector3());
      cloned.position.set(-c2.x, -fitted.min.y, -c2.z);
    }
    return cloned;
  }, [scene, manifestScale, sitting, props.instanceId]);

  useFrame((frameState) => {
    if (!group.current || state !== "ready" || sitting) return;
    const t = frameState.clock.elapsedTime;
    group.current.position.y = position[1] + Math.sin(t * 1.4 + position[0]) * 0.03;
    if (active) {
      group.current.rotation.y = rotationY + Math.sin(t * 2) * 0.08;
    }
  });

  return (
    <>
      {state === "loading" && <LoadingPlaceholder position={position} sitting={sitting} />}
      {state === "error" && (fallback ?? null)}
      {state === "ready" && model && (
        <group
          ref={group}
          position={position}
          rotation={[0, rotationY, 0]}
          scale={[seatScale, seatScale, seatScale]}
        >
          <primitive object={model} />
          {active && (
            <mesh position={[0.45, sitting ? 1.15 : 1.8 * manifestScale * seatScale, 0]}>
              <sphereGeometry args={[0.07, 8, 8]} />
              <meshStandardMaterial color="#3fb950" emissive="#3fb950" emissiveIntensity={0.9} />
            </mesh>
          )}
        </group>
      )}
      <GltfAvatarLabels position={position} status={state} progress={progress} sitting={sitting} seatScale={seatScale} />
    </>
  );
}
