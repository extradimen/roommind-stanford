import { Text } from "@react-three/drei";
import { useLocale } from "../i18n";

type Side = "opponent" | "player_ally" | "user";

type Props = {
  position: [number, number, number];
  rotationY?: number;
  name: string;
  sideLabel?: string;
  side?: Side;
  pose?: "stand" | "sit";
  reason?: "missing" | "error";
};

export default function GlbMissingAvatar({
  position,
  rotationY = 0,
  pose = "sit",
  reason = "missing",
  sideLabel,
}: Props) {
  const { t } = useLocale();
  const sitting = pose === "sit";
  const bodyY = sitting ? 0.55 : 0.85;
  const statusY = sitting ? (sideLabel ? 1.22 : 1.28) : sideLabel ? 1.72 : 1.8;
  const statusText = reason === "error" ? t.game.avatarGlbFailed : t.game.avatarGlbRequired;
  const statusColor = reason === "error" ? "#f85149" : "#d29922";

  return (
    <group position={position} rotation={[0, rotationY, 0]}>
      <mesh position={[0, bodyY, 0]}>
        <boxGeometry args={[0.42, sitting ? 1.0 : 1.6, 0.28]} />
        <meshBasicMaterial color="#58a6ff" wireframe transparent opacity={0.5} />
      </mesh>
      <Text position={[0, statusY, 0]} fontSize={0.085} color={statusColor} anchorX="center" maxWidth={1.4}>
        {statusText}
      </Text>
    </group>
  );
}
