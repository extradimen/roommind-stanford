import type { AvatarManifest } from "../avatarManifest";
import {
  avatarScaleFromManifest,
  isImportedAvatar,
  manifestToProfile,
  resolveAssetUrl,
} from "../avatarManifest";
import AnimatedAvatar, { type CulturalProfile } from "./AnimatedAvatar";
import GltfAvatarModel from "./GltfAvatarModel";
import PortraitAvatarModel from "./PortraitAvatarModel";

type Side = "opponent" | "player_ally" | "user";

type Props = {
  name: string;
  position: [number, number, number];
  profile: CulturalProfile;
  manifest?: AvatarManifest;
  sideLabel?: string;
  side?: Side;
  active?: boolean;
};

export default function SceneAvatar({
  name,
  position,
  profile,
  manifest,
  sideLabel,
  side,
  active = false,
}: Props) {
  const importKind = isImportedAvatar(manifest);
  const modelUrl = resolveAssetUrl(manifest?.model_url);
  const imageUrl = resolveAssetUrl(manifest?.image_url);
  const scale = avatarScaleFromManifest(manifest);

  if (importKind === "model" && modelUrl) {
    return (
      <GltfAvatarModel
        url={modelUrl}
        position={position}
        scale={scale}
        name={name}
        sideLabel={sideLabel}
        side={side}
        active={active}
      />
    );
  }

  if (importKind === "image" && imageUrl) {
    return (
      <PortraitAvatarModel
        url={imageUrl}
        position={position}
        name={name}
        sideLabel={sideLabel}
        side={side}
        active={active}
        accent={profile.accent}
      />
    );
  }

  return (
    <AnimatedAvatar
      position={position}
      profile={profile}
      name={name}
      sideLabel={sideLabel}
      side={side}
      active={active}
      scale={scale}
    />
  );
}

export function buildSceneAvatarProfile(
  characterId: string,
  manifest: AvatarManifest | undefined,
  patternLabels: Record<CulturalProfile["pattern"], string>,
) {
  return manifestToProfile(characterId, manifest, patternLabels);
}
