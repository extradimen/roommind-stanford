import type { CulturalProfile } from "./components/AnimatedAvatar";
import { CULTURAL_PROFILES } from "./components/AnimatedAvatar";

export type AvatarManifest = {
  suit?: string;
  skin?: string;
  accent?: string;
  pattern?: "east" | "west" | "global";
  accessory?: "fan" | "briefcase" | "globe" | "none";
  height?: number;
  image_url?: string;
  model_url?: string;
  label?: string;
  /** GLB-only avatars in 3D meeting scene */
  avatar_style?: "gltf";
  hair?: string;
  top?: string;
  bottom?: string;
  hair_style?: "short" | "gray" | "bob" | "ponytail";
  gender?: "male" | "female";
};

const DEFAULT_PROFILE: CulturalProfile = {
  skin: "#e8b896",
  suit: "#444",
  accent: "#58a6ff",
  accessory: "none",
  pattern: "global",
  label: "Guest",
};

export function resolveAssetUrl(url?: string): string | undefined {
  const trimmed = (url || "").trim();
  if (!trimmed) return undefined;
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  if (trimmed.startsWith("/")) return trimmed;
  return `/${trimmed.replace(/^\/+/, "")}`;
}

/** Strip empty import URLs so cleared avatars fall back to procedural models. */
export function normalizeAvatarManifest(manifest?: AvatarManifest): AvatarManifest | undefined {
  if (!manifest) return undefined;
  const next: AvatarManifest = { ...manifest };
  if (!resolveAssetUrl(next.model_url)) delete next.model_url;
  if (!resolveAssetUrl(next.image_url)) delete next.image_url;
  return next;
}

export function manifestToProfile(
  characterId: string,
  manifest: AvatarManifest | undefined,
  patternLabels: Record<CulturalProfile["pattern"], string>,
): CulturalProfile {
  const base = CULTURAL_PROFILES[characterId] || DEFAULT_PROFILE;
  const m = manifest || {};
  const pattern = (m.pattern as CulturalProfile["pattern"]) || base.pattern;
  const accessory = (m.accessory as CulturalProfile["accessory"]) || base.accessory;

  return {
    skin: String(m.skin || base.skin),
    suit: String(m.suit || base.suit),
    accent: String(m.accent || base.accent),
    accessory,
    pattern,
    label: m.label || patternLabels[pattern] || base.label,
  };
}

export function avatarScaleFromManifest(manifest?: AvatarManifest): number {
  const height = Number(manifest?.height);
  if (!Number.isFinite(height) || height <= 0) return 1;
  return Math.min(1.35, Math.max(0.75, height / 1.72));
}

export function isImportedAvatar(manifest?: AvatarManifest): "model" | "image" | null {
  const m = normalizeAvatarManifest(manifest);
  if (resolveAssetUrl(m?.model_url)) return "model";
  if (resolveAssetUrl(m?.image_url)) return "image";
  return null;
}
