import { OrbitControls } from "@react-three/drei";
import { useEffect, useRef } from "react";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import * as THREE from "three";

const TARGET: [number, number, number] = [0, 1, -0.5];

function applyDistance(controls: OrbitControlsImpl, distance: number) {
  const offset = new THREE.Vector3().subVectors(controls.object.position, controls.target);
  if (offset.lengthSq() < 1e-6) {
    offset.set(0, 0.25, 1);
  }
  offset.setLength(distance);
  controls.object.position.copy(controls.target).add(offset);
  controls.update();
}

type Props = {
  compact?: boolean;
  distance: number;
  minDistance: number;
  maxDistance: number;
  onDistanceChange: (d: number) => void;
};

export default function MeetingOrbitControls({
  compact,
  distance,
  minDistance,
  maxDistance,
  onDistanceChange,
}: Props) {
  const controlsRef = useRef<OrbitControlsImpl>(null);
  const syncingRef = useRef(false);
  const lastDistanceRef = useRef(distance);

  useEffect(() => {
    const controls = controlsRef.current;
    if (!controls) return;
    if (Math.abs(lastDistanceRef.current - distance) < 0.01) return;
    syncingRef.current = true;
    applyDistance(controls, distance);
    lastDistanceRef.current = distance;
    syncingRef.current = false;
  }, [distance]);

  return (
    <OrbitControls
      ref={controlsRef}
      enablePan={false}
      enableZoom
      zoomSpeed={compact ? 0.85 : 1}
      minPolarAngle={Math.PI / 6}
      maxPolarAngle={Math.PI / 2.2}
      minDistance={minDistance}
      maxDistance={maxDistance}
      target={TARGET}
      onChange={() => {
        if (syncingRef.current) return;
        const d = controlsRef.current?.getDistance();
        if (d == null) return;
        lastDistanceRef.current = d;
        onDistanceChange(d);
      }}
    />
  );
}

export { TARGET as MEETING_CAMERA_TARGET };
