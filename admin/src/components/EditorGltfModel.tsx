import { useMemo } from "react";
import * as THREE from "three";
import { fitPropGltfRoot, fitSeatedGltfRoot } from "../gltfModelFit";
import { useLoadedGltf } from "../hooks/useLoadedGltf";

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

type Props = {
  url: string;
  instanceId: string;
  manifestScale?: number;
  /** Furniture / decor props use height fit (chairs). */
  propFit?: boolean;
  fitHeight?: number;
  /** GLB already authored in world meters (room shell, table). */
  nativeScale?: boolean;
};

export default function EditorGltfModel({
  url,
  instanceId,
  manifestScale = 1,
  propFit = false,
  fitHeight,
  nativeScale = false,
}: Props) {
  const { state, scene } = useLoadedGltf(url, instanceId);

  const model = useMemo(() => {
    if (!scene) return null;
    const cloned = scene.clone(true);
    fixMaterials(cloned);
    if (nativeScale) {
      // keep authored scale
    } else if (propFit) fitPropGltfRoot(cloned, manifestScale, fitHeight);
    else fitSeatedGltfRoot(cloned, manifestScale);
    return cloned;
  }, [scene, manifestScale, instanceId, propFit, fitHeight, nativeScale]);

  if (state === "loading") {
    return (
      <group position={[0, 0.55, 0]}>
        <mesh>
          <boxGeometry args={[0.45, 1.1, 0.32]} />
          <meshBasicMaterial color="#58a6ff" wireframe transparent opacity={0.55} />
        </mesh>
      </group>
    );
  }

  if (state === "error" || !model) {
    return (
      <group position={[0, 0.55, 0]}>
        <mesh>
          <boxGeometry args={[0.45, 1.1, 0.32]} />
          <meshStandardMaterial color="#f85149" transparent opacity={0.6} />
        </mesh>
      </group>
    );
  }

  return <primitive object={model} />;
}
