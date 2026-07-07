import { Suspense, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Text, useTexture } from "@react-three/drei";
import * as THREE from "three";

type Props = {
  url: string;
  position: [number, number, number];
  active?: boolean;
  name: string;
  sideLabel?: string;
  side?: "opponent" | "player_ally" | "user";
  accent?: string;
};

function PortraitBody({ url, position, active = false, accent = "#58a6ff" }: Pick<Props, "url" | "position" | "active" | "accent">) {
  const group = useRef<THREE.Group>(null);
  const texture = useTexture(url);

  useFrame((state) => {
    if (!group.current) return;
    const t = state.clock.elapsedTime;
    group.current.position.y = position[1] + Math.sin(t * 1.2 + position[0]) * 0.03;
  });

  return (
    <group ref={group} position={position}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]}>
        <circleGeometry args={[0.42, 24]} />
        <meshBasicMaterial color="#000000" transparent opacity={0.28} />
      </mesh>
      <mesh position={[0, 0.18, 0]} castShadow>
        <cylinderGeometry args={[0.34, 0.4, 0.24, 20]} />
        <meshStandardMaterial color="#3a3f47" />
      </mesh>
      <mesh position={[0, 1.05, 0.02]} castShadow>
        <planeGeometry args={[0.92, 1.35]} />
        <meshStandardMaterial map={texture} transparent toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.42, 0.02]}>
        <boxGeometry args={[0.08, 0.55, 0.03]} />
        <meshStandardMaterial color={accent} />
      </mesh>
      {active && (
        <mesh position={[0.48, 1.55, 0]}>
          <sphereGeometry args={[0.07, 8, 8]} />
          <meshStandardMaterial color="#3fb950" emissive="#3fb950" emissiveIntensity={0.9} />
        </mesh>
      )}
    </group>
  );
}

export default function PortraitAvatarModel(props: Props) {
  const labelY = props.sideLabel ? 1.84 : 1.92;
  return (
    <>
      <Suspense fallback={null}>
        <PortraitBody url={props.url} position={props.position} active={props.active} accent={props.accent} />
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
      <Text position={[props.position[0], props.position[1] + labelY, props.position[2]]} fontSize={0.085} color={props.accent || "#58a6ff"} anchorX="center" maxWidth={1.4}>
        Portrait
      </Text>
    </>
  );
}
