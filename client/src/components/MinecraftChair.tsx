/** Blocky meeting-room chair (Minecraft style). */

export default function MinecraftChair() {
  const wood = "#5c4033";
  const woodDark = "#4a3728";
  const cushion = "#3a3a3a";
  const metal = "#8a8a8a";

  return (
    <group>
      <mesh position={[0, 0.42, 0]} castShadow receiveShadow>
        <boxGeometry args={[0.54, 0.09, 0.54]} />
        <meshStandardMaterial color={cushion} flatShading roughness={0.9} />
      </mesh>
      <mesh position={[0, 0.47, 0]} castShadow>
        <boxGeometry args={[0.5, 0.02, 0.5]} />
        <meshStandardMaterial color="#2a2a2a" flatShading />
      </mesh>
      <mesh position={[0, 0.74, -0.24]} castShadow>
        <boxGeometry args={[0.54, 0.54, 0.09]} />
        <meshStandardMaterial color={wood} flatShading />
      </mesh>
      <mesh position={[0, 0.58, -0.28]}>
        <boxGeometry args={[0.38, 0.22, 0.04]} />
        <meshStandardMaterial color={cushion} flatShading />
      </mesh>
      {([-0.26, 0.26] as const).map((x) => (
        <group key={x} position={[x, 0.5, 0.02]}>
          <mesh position={[0, 0, 0.06]} castShadow>
            <boxGeometry args={[0.1, 0.1, 0.28]} />
            <meshStandardMaterial color={woodDark} flatShading />
          </mesh>
          <mesh position={[0, 0.06, 0.2]} castShadow>
            <boxGeometry args={[0.1, 0.04, 0.1]} />
            <meshStandardMaterial color={wood} flatShading />
          </mesh>
        </group>
      ))}
      {(
        [
          [-0.22, 0.2, 0.22],
          [0.22, 0.2, 0.22],
          [-0.22, 0.2, -0.22],
          [0.22, 0.2, -0.22],
        ] as [number, number, number][]
      ).map((p, i) => (
        <mesh key={i} position={p} castShadow>
          <boxGeometry args={[0.07, 0.4, 0.07]} />
          <meshStandardMaterial color={woodDark} flatShading />
        </mesh>
      ))}
      <mesh position={[0, 0.08, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.2, 0.025, 6, 12]} />
        <meshStandardMaterial color={metal} metalness={0.6} roughness={0.35} flatShading />
      </mesh>
    </group>
  );
}
