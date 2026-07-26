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
  seated?: boolean;
  manifestScale?: number;
  fitHeight?: number;
  /** GLB already authored in world meters (room shell, table). */
  nativeScale?: boolean;
};

export default function GltfPropModel({
  url,
  instanceId,
  seated = false,
  manifestScale = 1,
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
    } else if (seated) fitSeatedGltfRoot(cloned, manifestScale);
    else if (fitHeight != null) fitPropGltfRoot(cloned, manifestScale, fitHeight);
    return cloned;
  }, [scene, seated, manifestScale, fitHeight, nativeScale, instanceId]);

  if (state === "loading") {
    return (
      <mesh position={[0, 0.55, 0]}>
        <boxGeometry args={[0.45, 1.1, 0.32]} />
        <meshBasicMaterial color="#58a6ff" wireframe transparent opacity={0.4} />
      </mesh>
    );
  }

  if (state === "error" || !model) return null;
  return <primitive object={model} />;
}
