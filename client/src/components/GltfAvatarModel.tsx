import { Suspense, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Text, useGLTF } from "@react-three/drei";
import * as THREE from "three";

type Props = {
  url: string;
  position: [number, number, number];
  scale?: number;
  active?: boolean;
  name: string;
  sideLabel?: string;
  side?: "opponent" | "player_ally" | "user";
};

function GltfAvatarBody({ url, position, scale = 1, active = false }: Pick<Props, "url" | "position" | "scale" | "active">) {
  const group = useRef<THREE.Group>(null);
  const { scene } = useGLTF(url);
  const model = useMemo(() => scene.clone(true), [scene]);

  useFrame((state) => {
    if (!group.current) return;
    const t = state.clock.elapsedTime;
    const bob = Math.sin(t * 1.4 + position[0]) * 0.03;
    group.current.position.y = position[1] + bob;
    if (active) {
      group.current.rotation.y = Math.sin(t * 2) * 0.08;
    }
  });

  return (
    <group ref={group} position={position}>
      <primitive object={model} scale={scale} />
      {active && (
        <mesh position={[0.5, 1.8 * scale, 0]}>
          <sphereGeometry args={[0.07, 8, 8]} />
          <meshStandardMaterial color="#3fb950" emissive="#3fb950" emissiveIntensity={0.9} />
        </mesh>
      )}
    </group>
  );
}

export default function GltfAvatarModel(props: Props) {
  const labelY = props.sideLabel ? 1.84 : 1.92;
  return (
    <>
      <Suspense fallback={null}>
        <GltfAvatarBody url={props.url} position={props.position} scale={props.scale} active={props.active} />
      </Suspense>
      <Text position={[props.position[0], props.position[1] + 2.12, props.position[2]]} fontSize={0.15} color="#ffffff" anchorX="center" maxWidth={1.4}>
        {props.name}
      </Text>
      {props.sideLabel && (
        <Text
          position={[props.position[0], props.position[1] + 1.98, props.position[2]]}
          fontSize={0.075}
          color={props.side === "player_ally" || props.side === "user" ? "#3fb950" : "#f85149"}
          anchorX="center"
          maxWidth={1.4}
        >
          [{props.sideLabel}]
        </Text>
      )}
      <Text position={[props.position[0], props.position[1] + labelY, props.position[2]]} fontSize={0.085} color="#58a6ff" anchorX="center" maxWidth={1.4}>
        3D model
      </Text>
    </>
  );
}
