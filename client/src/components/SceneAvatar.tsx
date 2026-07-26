import type { AvatarManifest } from "../avatarManifest";
import {
  avatarScaleFromManifest,
  isImportedAvatar,
  manifestToProfile,
  normalizeAvatarManifest,
  resolveAssetUrl,
} from "../avatarManifest";
import { type CulturalProfile } from "./AnimatedAvatar";
import GlbMissingAvatar from "./GlbMissingAvatar";
import GltfAvatarModel from "./GltfAvatarModel";

type Side = "opponent" | "player_ally" | "user";

type Props = {
  characterId: string;
  name: string;
  position: [number, number, number];
  profile: CulturalProfile;
  manifest?: AvatarManifest;
  sideLabel?: string;
  side?: Side;
  active?: boolean;
  pose?: "stand" | "sit";
  rotationY?: number;
  seatScale?: number;
};

export default function SceneAvatar({
  characterId,
  name,
  position,
  manifest,
  sideLabel,
  side,
  active = false,
  pose = "sit",
  rotationY = 0,
  seatScale = 1,
}: Props) {
  const manifestNorm = normalizeAvatarManifest(manifest);
  const importKind = isImportedAvatar(manifestNorm);
  const manifestScale = avatarScaleFromManifest(manifestNorm);
  const modelUrl = resolveAssetUrl(manifestNorm?.model_url);

  const missing = (
    <GlbMissingAvatar
      position={position}
      rotationY={rotationY}
      name={name}
      sideLabel={sideLabel}
      side={side}
      pose={pose}
      reason="missing"
    />
  );

  if (importKind === "model" && modelUrl) {
    return (
      <GltfAvatarModel
        key={`${characterId}:${modelUrl}`}
        instanceId={characterId}
        url={modelUrl}
        position={position}
        manifestScale={manifestScale}
        seatScale={seatScale}
        name={name}
        sideLabel={sideLabel}
        side={side}
        active={active}
        pose={pose}
        rotationY={rotationY}
        fallback={
          <GlbMissingAvatar
            position={position}
            rotationY={rotationY}
            name={name}
            sideLabel={sideLabel}
            side={side}
            pose={pose}
            reason="error"
          />
        }
      />
    );
  }

  return missing;
}

export function buildSceneAvatarProfile(
  characterId: string,
  manifest: AvatarManifest | undefined,
  patternLabels: Record<CulturalProfile["pattern"], string>,
) {
  return manifestToProfile(characterId, manifest, patternLabels);
}
