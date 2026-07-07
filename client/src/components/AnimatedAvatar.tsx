import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Text } from "@react-three/drei";
import * as THREE from "three";

export type CulturalProfile = {
  skin: string;
  suit: string;
  accent: string;
  accessory: "fan" | "briefcase" | "globe" | "none";
  pattern: "east" | "west" | "global";
  label: string;
};

export const CULTURAL_PROFILES: Record<string, CulturalProfile> = {
  supplier_ceo: {
    skin: "#e8b896",
    suit: "#1a1a2e",
    accent: "#c41e3a",
    accessory: "fan",
    pattern: "east",
    label: "East Asian business",
  },
  legal_counsel: {
    skin: "#f0d5b8",
    suit: "#2c3e6b",
    accent: "#c9a227",
    accessory: "briefcase",
    pattern: "west",
    label: "Western legal",
  },
  procurement_ally: {
    skin: "#d4a574",
    suit: "#1e5631",
    accent: "#00a896",
    accessory: "globe",
    pattern: "global",
    label: "Global collaboration",
  },
};

function Accessory({ type, accent }: { type: CulturalProfile["accessory"]; accent: string }) {
  if (type === "fan") {
    return (
      <mesh position={[0.42, 1.08, 0.18]} rotation={[0, 0.3, 0.5]}>
        <circleGeometry args={[0.14, 16]} />
        <meshStandardMaterial color={accent} side={THREE.DoubleSide} />
      </mesh>
    );
  }
  if (type === "briefcase") {
    return (
      <mesh position={[0.45, 0.52, 0.22]}>
        <boxGeometry args={[0.2, 0.15, 0.07]} />
        <meshStandardMaterial color="#4a3728" />
      </mesh>
    );
  }
  if (type === "globe") {
    return (
      <mesh position={[-0.38, 1.02, 0.14]}>
        <sphereGeometry args={[0.11, 12, 12]} />
        <meshStandardMaterial color={accent} wireframe />
      </mesh>
    );
  }
  return null;
}

function PatternBadge({ pattern, accent }: { pattern: CulturalProfile["pattern"]; accent: string }) {
  const colors =
    pattern === "east"
      ? [accent, "#f5f5dc", accent]
      : pattern === "west"
        ? [accent, "#fff", accent]
        : [accent, "#7fdbda", "#e8f4f8"];
  return (
    <group position={[0, 1.38, 0.28]}>
      {colors.map((c, i) => (
        <mesh key={i} position={[(i - 1) * 0.07, 0, 0]}>
          <boxGeometry args={[0.06, 0.09, 0.02]} />
          <meshStandardMaterial color={c} />
        </mesh>
      ))}
    </group>
  );
}

export default function AnimatedAvatar({
  position,
  profile,
  name,
  sideLabel,
  side,
  active,
  scale = 1,
}: {
  position: [number, number, number];
  profile: CulturalProfile;
  name: string;
  sideLabel?: string;
  side?: "opponent" | "player_ally" | "user";
  active: boolean;
  scale?: number;
}) {
  const group = useRef<THREE.Group>(null);
  const torso = useRef<THREE.Mesh>(null);
  const head = useRef<THREE.Group>(null);
  const leftArm = useRef<THREE.Group>(null);
  const rightArm = useRef<THREE.Group>(null);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    const phase = position[0] * 0.7 + position[2];

    if (group.current) {
      const bob = Math.sin(t * 1.4 + phase) * 0.04;
      group.current.position.y = position[1] + bob;
    }

    if (head.current) {
      const nod = active ? Math.sin(t * 6) * 0.12 : Math.sin(t * 0.8 + phase) * 0.03;
      head.current.rotation.x = nod;
    }

    if (leftArm.current) {
      leftArm.current.rotation.x = active
        ? -0.4 + Math.sin(t * 5) * 0.35
        : 0.15 + Math.sin(t * 1.2 + phase) * 0.05;
    }
    if (rightArm.current) {
      rightArm.current.rotation.x = active
        ? -0.5 + Math.sin(t * 5 + 0.5) * 0.4
        : 0.1 + Math.sin(t * 1.2 + phase + 1) * 0.05;
    }

    if (torso.current && active) {
      const pulse = 1 + Math.sin(t * 8) * 0.03;
      torso.current.scale.set(pulse, pulse, pulse);
    }

    if (group.current && active) {
      group.current.rotation.y = Math.sin(t * 2) * 0.1;
    }
  });

  return (
    <group ref={group} position={position} scale={[scale, scale, scale]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]}>
        <circleGeometry args={[0.4, 24]} />
        <meshBasicMaterial color="#000000" transparent opacity={0.28} />
      </mesh>

      {/* Legs */}
      <mesh position={[-0.1, 0.28, 0]} castShadow>
        <boxGeometry args={[0.14, 0.52, 0.16]} />
        <meshStandardMaterial color="#2a2a2a" />
      </mesh>
      <mesh position={[0.1, 0.28, 0]} castShadow>
        <boxGeometry args={[0.14, 0.52, 0.16]} />
        <meshStandardMaterial color="#2a2a2a" />
      </mesh>

      {/* Torso */}
      <mesh ref={torso} position={[0, 0.88, 0]} castShadow>
        <boxGeometry args={[0.46, 0.58, 0.26]} />
        <meshStandardMaterial
          color={profile.suit}
          emissive={active ? profile.accent : "#000000"}
          emissiveIntensity={active ? 0.3 : 0}
        />
      </mesh>

      {/* Shoulders */}
      <mesh position={[0, 1.15, 0]} castShadow>
        <boxGeometry args={[0.58, 0.12, 0.28]} />
        <meshStandardMaterial color={profile.suit} />
      </mesh>

      {/* Tie / scarf */}
      <mesh position={[0, 0.82, 0.14]}>
        <boxGeometry args={[0.09, 0.38, 0.03]} />
        <meshStandardMaterial color={profile.accent} />
      </mesh>

      <PatternBadge pattern={profile.pattern} accent={profile.accent} />

      {/* Left arm */}
      <group ref={leftArm} position={[-0.34, 1.05, 0]}>
        <mesh position={[0, -0.18, 0]} castShadow>
          <boxGeometry args={[0.12, 0.38, 0.12]} />
          <meshStandardMaterial color={profile.suit} />
        </mesh>
        <mesh position={[0, -0.42, 0]} castShadow>
          <sphereGeometry args={[0.07, 10, 10]} />
          <meshStandardMaterial color={profile.skin} />
        </mesh>
      </group>

      {/* Right arm */}
      <group ref={rightArm} position={[0.34, 1.05, 0]}>
        <mesh position={[0, -0.18, 0]} castShadow>
          <boxGeometry args={[0.12, 0.38, 0.12]} />
          <meshStandardMaterial color={profile.suit} />
        </mesh>
        <mesh position={[0, -0.42, 0]} castShadow>
          <sphereGeometry args={[0.07, 10, 10]} />
          <meshStandardMaterial color={profile.skin} />
        </mesh>
      </group>

      {/* Head group */}
      <group ref={head} position={[0, 1.48, 0]}>
        <mesh castShadow>
          <sphereGeometry args={[0.22, 20, 20]} />
          <meshStandardMaterial color={profile.skin} />
        </mesh>
        <mesh position={[0, 0.14, -0.02]}>
          <sphereGeometry args={[0.19, 16, 16, 0, Math.PI * 2, 0, Math.PI * 0.55]} />
          <meshStandardMaterial color="#2a2a2a" />
        </mesh>
        {/* Eyes */}
        <mesh position={[-0.07, 0.02, 0.18]}>
          <sphereGeometry args={[0.025, 8, 8]} />
          <meshStandardMaterial color="#1a1a1a" />
        </mesh>
        <mesh position={[0.07, 0.02, 0.18]}>
          <sphereGeometry args={[0.025, 8, 8]} />
          <meshStandardMaterial color="#1a1a1a" />
        </mesh>
      </group>

      <Accessory type={profile.accessory} accent={profile.accent} />

      {active && (
        <>
          <mesh position={[0.5, 1.62, 0]}>
            <sphereGeometry args={[0.07, 8, 8]} />
            <meshStandardMaterial color="#3fb950" emissive="#3fb950" emissiveIntensity={0.9} />
          </mesh>
          <mesh position={[0, 2.05, 0]} rotation={[0, 0, 0]}>
            <boxGeometry args={[0.02, 0.12, 0.02]} />
            <meshStandardMaterial color="#3fb950" emissive="#3fb950" emissiveIntensity={0.5} />
          </mesh>
        </>
      )}

      <Text position={[0, 2.12, 0]} fontSize={0.15} color="#ffffff" anchorX="center" maxWidth={1.4}>
        {name}
      </Text>
      {sideLabel && (
        <Text
          position={[0, 1.98, 0]}
          fontSize={0.075}
          color={side === "player_ally" || side === "user" ? "#3fb950" : "#f85149"}
          anchorX="center"
          maxWidth={1.4}
        >
          [{sideLabel}]
        </Text>
      )}
      <Text position={[0, sideLabel ? 1.84 : 1.92, 0]} fontSize={0.085} color={profile.accent} anchorX="center" maxWidth={1.4}>
        {profile.label}
      </Text>
    </group>
  );
}
