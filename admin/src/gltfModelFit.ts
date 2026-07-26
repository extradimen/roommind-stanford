import * as THREE from "three";

export function worldBounds(root: THREE.Object3D) {
  const box = new THREE.Box3();
  let hasMesh = false;
  root.updateMatrixWorld(true);
  root.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (!mesh.isMesh || !mesh.geometry) return;
    if (!mesh.geometry.boundingBox) mesh.geometry.computeBoundingBox();
    const geomBox = mesh.geometry.boundingBox;
    if (!geomBox) return;
    const wb = geomBox.clone().applyMatrix4(mesh.matrixWorld);
    box.union(wb);
    hasMesh = true;
  });
  if (!hasMesh || box.isEmpty()) return new THREE.Box3().setFromObject(root);
  return box;
}

/** Seated Meshy/GLB exports often measure ~1.9m bbox; target ~1.45m reads well at the meeting table. */
export const SEATED_TARGET_HEIGHT = 1.45;

/** Scale seated GLB, then align feet to local y=0 and center on xz. */
export function fitSeatedGltfRoot(root: THREE.Object3D, manifestScale = 1, targetHeight = SEATED_TARGET_HEIGHT) {
  root.position.set(0, 0, 0);
  root.rotation.set(0, 0, 0);
  root.scale.setScalar(1);
  root.updateMatrixWorld(true);

  const raw = worldBounds(root);
  const rawHeight = Math.max(raw.getSize(new THREE.Vector3()).y, 0.001);
  const fitScale = (targetHeight / rawHeight) * manifestScale;
  root.scale.setScalar(fitScale);
  root.updateMatrixWorld(true);

  const fitted = worldBounds(root);
  const center = fitted.getCenter(new THREE.Vector3());
  root.position.set(-center.x, -fitted.min.y, -center.z);
}

/** Office-chair / furniture GLB exports use the same micro-scale pattern as Meshy avatars. */
export const PROP_TARGET_HEIGHT = 0.95;

/** Scale prop GLB to target height, align bottom center to local origin. */
export function fitPropGltfRoot(root: THREE.Object3D, manifestScale = 1, targetHeight = PROP_TARGET_HEIGHT) {
  root.position.set(0, 0, 0);
  root.rotation.set(0, 0, 0);
  root.scale.setScalar(1);
  root.updateMatrixWorld(true);

  const raw = worldBounds(root);
  const rawHeight = Math.max(raw.getSize(new THREE.Vector3()).y, 0.001);
  const fitScale = (targetHeight / rawHeight) * manifestScale;
  root.scale.setScalar(fitScale);
  root.updateMatrixWorld(true);

  const fitted = worldBounds(root);
  const center = fitted.getCenter(new THREE.Vector3());
  root.position.set(-center.x, -fitted.min.y, -center.z);
}
