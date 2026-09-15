import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Text } from "@react-three/drei";
import * as THREE from "three";
import type { MinecraftAvatarSpec } from "../minecraftAvatarPresets";
import MinecraftChair from "./MinecraftChair";

type Side = "opponent" | "player_ally" | "user";
type Pose = "stand" | "sit";
/** Head reads oversized on seated avatars — scale down vs. torso */
const HEAD_SCALE = 0.72;

function BlockMat({
  color,
  emissive = "#000000",
  emissiveIntensity = 0,
}: {
  color: string;
  emissive?: string;
  emissiveIntensity?: number;
}) {
  return <meshStandardMaterial color={color} flatShading emissive={emissive} emissiveIntensity={emissiveIntensity} />;
}

function Hair({ spec }: { spec: MinecraftAvatarSpec }) {
  const { hairStyle, hair } = spec;
  if (hairStyle === "bob") {
    return (
      <group position={[0, 0.06, -0.02]}>
        <mesh position={[0, 0.1, 0]}>
          <boxGeometry args={[0.54, 0.24, 0.56]} />
          <BlockMat color={hair} />
        </mesh>
        <mesh position={[0, -0.02, -0.2]}>
          <boxGeometry args={[0.5, 0.3, 0.18]} />
          <BlockMat color={hair} />
        </mesh>
        <mesh position={[-0.28, 0.04, 0.02]}>
          <boxGeometry args={[0.08, 0.2, 0.4]} />
          <BlockMat color={hair} />
        </mesh>
        <mesh position={[0.28, 0.04, 0.02]}>
          <boxGeometry args={[0.08, 0.2, 0.4]} />
          <BlockMat color={hair} />
        </mesh>
      </group>
    );
  }
  if (hairStyle === "ponytail") {
    return (
      <group>
        <mesh position={[0, 0.1, 0]}>
          <boxGeometry args={[0.52, 0.18, 0.54]} />
          <BlockMat color={hair} />
        </mesh>
        <mesh position={[-0.27, 0.04, 0.04]}>
          <boxGeometry args={[0.08, 0.16, 0.38]} />
          <BlockMat color={hair} />
        </mesh>
        <mesh position={[0.27, 0.04, 0.04]}>
          <boxGeometry args={[0.08, 0.16, 0.38]} />
          <BlockMat color={hair} />
        </mesh>
        <mesh position={[0, 0.02, -0.34]}>
          <boxGeometry args={[0.16, 0.16, 0.32]} />
          <BlockMat color={hair} />
        </mesh>
        <mesh position={[0, 0.08, -0.46]}>
          <boxGeometry args={[0.1, 0.1, 0.14]} />
          <BlockMat color={spec.accent} />
        </mesh>
      </group>
    );
  }
  if (hairStyle === "gray") {
    return (
      <group>
        <mesh position={[0, 0.1, 0]}>
          <boxGeometry args={[0.54, 0.18, 0.54]} />
          <BlockMat color={hair} />
        </mesh>
        <mesh position={[-0.28, -0.02, 0.08]}>
          <boxGeometry args={[0.1, 0.14, 0.2]} />
          <BlockMat color={hair} />
        </mesh>
        <mesh position={[0.28, -0.02, 0.08]}>
          <boxGeometry args={[0.1, 0.14, 0.2]} />
          <BlockMat color={hair} />
        </mesh>
        <mesh position={[0, 0.14, -0.06]}>
          <boxGeometry args={[0.42, 0.06, 0.3]} />
          <BlockMat color={hair} />
        </mesh>
      </group>
    );
  }
  return (
    <group>
      <mesh position={[0, 0.1, 0]}>
        <boxGeometry args={[0.54, 0.18, 0.54]} />
        <BlockMat color={hair} />
      </mesh>
      <mesh position={[-0.28, -0.02, 0.08]}>
        <boxGeometry args={[0.1, 0.14, 0.2]} />
        <BlockMat color={hair} />
      </mesh>
      <mesh position={[0.28, -0.02, 0.08]}>
        <boxGeometry args={[0.1, 0.14, 0.2]} />
        <BlockMat color={hair} />
      </mesh>
    </group>
  );
}

function Face({ spec }: { spec: MinecraftAvatarSpec }) {
  const { skin, gender, glasses } = spec;
  return (
    <>
      <mesh position={[-0.26, 0, 0]}>
        <boxGeometry args={[0.06, 0.14, 0.12]} />
        <BlockMat color={skin} />
      </mesh>
      <mesh position={[0.26, 0, 0]}>
        <boxGeometry args={[0.06, 0.14, 0.12]} />
        <BlockMat color={skin} />
      </mesh>
      <mesh position={[-0.1, 0.1, 0.26]}>
        <boxGeometry args={[0.1, 0.04, 0.02]} />
        <BlockMat color="#3d2b1f" />
      </mesh>
      <mesh position={[0.1, 0.1, 0.26]}>
        <boxGeometry args={[0.1, 0.04, 0.02]} />
        <BlockMat color="#3d2b1f" />
      </mesh>
      <mesh position={[-0.1, 0.02, 0.26]}>
        <boxGeometry args={[0.09, 0.09, 0.02]} />
        <BlockMat color="#ffffff" />
      </mesh>
      <mesh position={[0.1, 0.02, 0.26]}>
        <boxGeometry args={[0.09, 0.09, 0.02]} />
        <BlockMat color="#ffffff" />
      </mesh>
      <mesh position={[-0.1, 0.02, 0.27]}>
        <boxGeometry args={[0.045, 0.045, 0.02]} />
        <BlockMat color="#1a1a2e" />
      </mesh>
      <mesh position={[0.1, 0.02, 0.27]}>
        <boxGeometry args={[0.045, 0.045, 0.02]} />
        <BlockMat color="#1a1a2e" />
      </mesh>
      {gender === "female" && (
        <>
          <mesh position={[-0.14, -0.02, 0.25]}>
            <boxGeometry args={[0.05, 0.04, 0.02]} />
            <BlockMat color="#d4a0a0" />
          </mesh>
          <mesh position={[0.14, -0.02, 0.25]}>
            <boxGeometry args={[0.05, 0.04, 0.02]} />
            <BlockMat color="#d4a0a0" />
          </mesh>
        </>
      )}
      <mesh position={[0, -0.1, 0.26]}>
        <boxGeometry args={[0.08, 0.03, 0.02]} />
        <BlockMat color={gender === "female" ? "#c47a7a" : skin} />
      </mesh>
      {glasses && (
        <group position={[0, 0.02, 0.28]}>
          <mesh position={[-0.1, 0, 0]}>
            <boxGeometry args={[0.12, 0.06, 0.02]} />
            <BlockMat color="#1a1a1a" />
          </mesh>
          <mesh position={[0.1, 0, 0]}>
            <boxGeometry args={[0.12, 0.06, 0.02]} />
            <BlockMat color="#1a1a1a" />
          </mesh>
          <mesh position={[0, 0, 0]}>
            <boxGeometry args={[0.06, 0.02, 0.02]} />
            <BlockMat color="#333333" />
          </mesh>
          <mesh position={[-0.18, 0, -0.02]}>
            <boxGeometry args={[0.04, 0.02, 0.04]} />
            <BlockMat color="#333333" />
          </mesh>
          <mesh position={[0.18, 0, -0.02]}>
            <boxGeometry args={[0.04, 0.02, 0.04]} />
            <BlockMat color="#333333" />
          </mesh>
        </group>
      )}
    </>
  );
}

function BusinessAttire({ spec, sitting }: { spec: MinecraftAvatarSpec; sitting: boolean }) {
  const bodyY = sitting ? 0.68 : 0.82;
  const z = sitting ? 0.04 : 0;

  return (
    <>
      <mesh position={[0, bodyY + 0.14, z + 0.13]}>
        <boxGeometry args={[0.14, 0.08, 0.03]} />
        <BlockMat color="#f5f5f5" />
      </mesh>
      <mesh position={[-0.14, bodyY + 0.06, z + 0.12]} rotation={[0, 0.25, 0]}>
        <boxGeometry args={[0.1, 0.22, 0.03]} />
        <BlockMat color={spec.top} />
      </mesh>
      <mesh position={[0.14, bodyY + 0.06, z + 0.12]} rotation={[0, -0.25, 0]}>
        <boxGeometry args={[0.1, 0.22, 0.03]} />
        <BlockMat color={spec.top} />
      </mesh>
      {spec.gender === "male" && (
        <mesh position={[0, bodyY - 0.02, z + 0.13]}>
          <boxGeometry args={[0.1, 0.06, 0.03]} />
          <BlockMat color="#c0c0c0" />
        </mesh>
      )}
      {spec.necklace && (
        <mesh position={[0, bodyY + 0.22, z + 0.12]}>
          <boxGeometry args={[0.12, 0.02, 0.02]} />
          <BlockMat color="#d4af37" emissive="#d4af37" emissiveIntensity={0.15} />
        </mesh>
      )}
      {spec.gender === "male" && (
        <mesh position={[0.18, bodyY + 0.02, z + 0.1]}>
          <boxGeometry args={[0.06, 0.08, 0.02]} />
          <BlockMat color={spec.accent} />
        </mesh>
      )}
    </>
  );
}

function SittingLegs({ spec }: { spec: MinecraftAvatarSpec }) {
  const shoe = "#1a1a1a";
  return (
    <>
      {([-0.13, 0.13] as const).map((x) => (
        <group key={x} position={[x, 0.46, 0.08]} rotation={[1.05, 0, 0]}>
          <mesh position={[0, -0.12, 0.12]} castShadow>
            <boxGeometry args={[0.14, 0.28, 0.14]} />
            <BlockMat color={spec.bottom} />
          </mesh>
          <mesh position={[0, -0.02, 0.28]} rotation={[-0.85, 0, 0]} castShadow>
            <boxGeometry args={[0.14, 0.28, 0.14]} />
            <BlockMat color={spec.bottom} />
          </mesh>
          <mesh position={[0, -0.06, 0.42]} rotation={[-0.2, 0, 0]} castShadow>
            <boxGeometry args={[0.15, 0.08, 0.22]} />
            <BlockMat color={shoe} />
          </mesh>
        </group>
      ))}
    </>
  );
}

function ArmMeshes({ spec, side, sitting }: { spec: MinecraftAvatarSpec; side: "left" | "right"; sitting: boolean }) {
  const sign = side === "left" ? -1 : 1;
  const armLen = sitting ? 0.28 : 0.36;
  const handZ = sitting ? 0.04 : 0;

  return (
    <>
      <mesh position={[0, -0.18, 0]} castShadow>
        <boxGeometry args={[0.12, armLen, 0.12]} />
        <BlockMat color={spec.top} />
      </mesh>
      <mesh position={[sign * 0.02, sitting ? -0.32 : -0.36, 0.02]} castShadow>
        <boxGeometry args={[0.1, 0.06, 0.1]} />
        <BlockMat color="#f0f0f0" />
      </mesh>
      <mesh position={[0, sitting ? -0.34 : -0.4, handZ]} castShadow>
        <boxGeometry args={[0.12, 0.12, 0.12]} />
        <BlockMat color={spec.skin} />
      </mesh>
      {side === "left" && spec.gender === "male" && (
        <mesh position={[0.04, sitting ? -0.3 : -0.36, handZ + 0.08]}>
          <boxGeometry args={[0.04, 0.04, 0.02]} />
          <BlockMat color="#c0c0c0" />
        </mesh>
      )}
    </>
  );
}

export default function MinecraftAvatar({
  position,
  spec,
  name,
  sideLabel,
  side,
  active,
  scale = 1,
  pose = "sit",
  rotationY = 0,
}: {
  position: [number, number, number];
  spec: MinecraftAvatarSpec;
  name: string;
  sideLabel?: string;
  side?: Side;
  active: boolean;
  scale?: number;
  pose?: Pose;
  rotationY?: number;
}) {
  const group = useRef<THREE.Group>(null);
  const head = useRef<THREE.Group>(null);
  const leftArm = useRef<THREE.Group>(null);
  const rightArm = useRef<THREE.Group>(null);
  const body = useRef<THREE.Mesh>(null);

  const bodyW = spec.gender === "female" ? 0.44 : 0.5;
  const shoulder = spec.gender === "female" ? 0.3 : 0.34;
  const sitting = pose === "sit";
  const labelHeight = sitting ? 1.58 : 1.95;
  const sideLabelHeight = sitting ? 1.46 : 1.82;
  const tagHeight = sitting ? (sideLabel ? 1.34 : 1.4) : sideLabel ? 1.68 : 1.76;

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    const phase = position[0] * 0.7 + position[2];

    if (group.current && !sitting) {
      group.current.position.y = Math.sin(t * 1.4 + phase) * 0.03;
    }
    if (head.current) {
      head.current.rotation.x = active
        ? Math.sin(t * 6) * (sitting ? 0.08 : 0.1)
        : Math.sin(t * 0.8 + phase) * 0.03;
      if (sitting && active) {
        head.current.rotation.y = Math.sin(t * 3) * 0.04;
      }
    }
    if (leftArm.current) {
      leftArm.current.rotation.x = active
        ? (sitting ? -0.85 : -0.55) + Math.sin(t * 5) * (sitting ? 0.18 : 0.45)
        : sitting
          ? -0.75
          : 0.08 + Math.sin(t * 1.2 + phase) * 0.04;
    }
    if (rightArm.current) {
      rightArm.current.rotation.x = active
        ? (sitting ? -0.95 : -0.65) + Math.sin(t * 5 + 0.5) * (sitting ? 0.2 : 0.5)
        : sitting
          ? -0.78
          : 0.05 + Math.sin(t * 1.2 + phase + 1) * 0.04;
    }
    if (body.current && active) {
      const pulse = 1 + Math.sin(t * 8) * 0.015;
      body.current.scale.set(pulse, pulse, pulse);
    }
    if (group.current && active && !sitting) {
      group.current.rotation.y = Math.sin(t * 2) * 0.08;
    }
  });

  const bodyY = sitting ? 0.68 : 0.82;
  const headY = sitting ? 1.02 : 1.24;
  const armY = sitting ? 0.78 : 0.98;
  const tieY = sitting ? 0.58 : 0.72;
  const skirtY = sitting ? 0.46 : 0.52;
  const activeDotY = sitting ? 1.18 : 1.42;
  const z = sitting ? 0.04 : 0;
  return (
    <group position={position} rotation={[0, rotationY, 0]}>
      {sitting && <MinecraftChair />}

      <group ref={group} scale={[scale, scale, scale]}>
        {!sitting && (
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]}>
            <circleGeometry args={[0.38, 16]} />
            <meshBasicMaterial color="#000000" transparent opacity={0.25} />
          </mesh>
        )}

        {sitting ? <SittingLegs spec={spec} /> : (
          <>
            <mesh position={[-0.1, 0.26, 0]} castShadow>
              <boxGeometry args={[0.14, 0.52, 0.14]} />
              <BlockMat color={spec.bottom} />
            </mesh>
            <mesh position={[0.1, 0.26, 0]} castShadow>
              <boxGeometry args={[0.14, 0.52, 0.14]} />
              <BlockMat color={spec.bottom} />
            </mesh>
            <mesh position={[-0.1, 0.02, 0.06]} castShadow>
              <boxGeometry args={[0.15, 0.08, 0.22]} />
              <BlockMat color="#1a1a1a" />
            </mesh>
            <mesh position={[0.1, 0.02, 0.06]} castShadow>
              <boxGeometry args={[0.15, 0.08, 0.22]} />
              <BlockMat color="#1a1a1a" />
            </mesh>
          </>
        )}

        <mesh ref={body} position={[0, bodyY, z]} castShadow>
          <boxGeometry args={[bodyW, sitting ? 0.48 : 0.56, 0.24]} />
          <BlockMat color={spec.top} emissive={active ? spec.accent : "#000000"} emissiveIntensity={active ? 0.12 : 0} />
        </mesh>

        {spec.gender === "female" && (
          <>
            <mesh position={[0, skirtY, z]} castShadow>
              <boxGeometry args={[0.46, sitting ? 0.22 : 0.32, 0.26]} />
              <BlockMat color={spec.bottom} />
            </mesh>
            <mesh position={[0, bodyY + 0.1, z + 0.12]}>
              <boxGeometry args={[0.1, 0.14, 0.03]} />
              <BlockMat color="#f8f8f8" />
            </mesh>
          </>
        )}

        <BusinessAttire spec={spec} sitting={sitting} />

        <mesh position={[0, tieY, z + 0.16]}>
          <boxGeometry args={[0.07, sitting ? 0.22 : 0.34, 0.03]} />
          <BlockMat color={spec.accent} />
        </mesh>
        <mesh position={[0, tieY - (sitting ? 0.08 : 0.12), z + 0.17]}>
          <boxGeometry args={[0.1, 0.06, 0.02]} />
          <BlockMat color={spec.accent} />
        </mesh>

        <group ref={leftArm} position={[-shoulder, armY, sitting ? 0.06 : 0]}>
          <ArmMeshes spec={spec} side="left" sitting={sitting} />
        </group>
        <group ref={rightArm} position={[shoulder, armY, sitting ? 0.06 : 0]}>
          <ArmMeshes spec={spec} side="right" sitting={sitting} />
        </group>

        <group ref={head} position={[0, headY, z]} scale={[HEAD_SCALE, HEAD_SCALE, HEAD_SCALE]}>
          <mesh position={[0, -0.12, 0]} castShadow>
            <boxGeometry args={[0.18, 0.1, 0.16]} />
            <BlockMat color={spec.skin} />
          </mesh>
          <mesh castShadow>
            <boxGeometry args={[0.5, 0.5, 0.5]} />
            <BlockMat color={spec.skin} />
          </mesh>
          <Hair spec={spec} />
          <Face spec={spec} />
        </group>

        {active && (
          <mesh position={[0.48, activeDotY, z]}>
            <boxGeometry args={[0.1, 0.1, 0.1]} />
            <BlockMat color="#3fb950" emissive="#3fb950" emissiveIntensity={0.8} />
          </mesh>
        )}

        <Text position={[0, labelHeight, 0]} fontSize={0.15} color="#ffffff" anchorX="center" maxWidth={1.4}>
          {name}
        </Text>
        {sideLabel && (
          <Text
            position={[0, sideLabelHeight, 0]}
            fontSize={0.075}
            color={side === "player_ally" || side === "user" ? "#3fb950" : "#f85149"}
            anchorX="center"
            maxWidth={1.4}
          >
            [{sideLabel}]
          </Text>
        )}
        <Text position={[0, tagHeight, 0]} fontSize={0.085} color={spec.accent} anchorX="center" maxWidth={1.4}>
          {spec.label}
        </Text>
      </group>
    </group>
  );
}
