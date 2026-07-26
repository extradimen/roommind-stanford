import type { AvatarManifest } from "./avatarManifest";

export type MinecraftHairStyle = "short" | "gray" | "bob" | "ponytail";
export type MinecraftGender = "male" | "female";

export type MinecraftAvatarSpec = {
  skin: string;
  hair: string;
  top: string;
  bottom: string;
  accent: string;
  hairStyle: MinecraftHairStyle;
  gender: MinecraftGender;
  label: string;
  glasses?: boolean;
  necklace?: boolean;
};

const PRESETS: Record<string, MinecraftAvatarSpec> = {
  user: {
    skin: "#e8c4a8",
    hair: "#5c4033",
    top: "#1e3a5f",
    bottom: "#2a2a2a",
    accent: "#c8d4e8",
    hairStyle: "short",
    gender: "male",
    label: "Strategic procurement",
    glasses: false,
  },
  supplier_ceo: {
    skin: "#f0d0b0",
    hair: "#9e9e9e",
    top: "#2f2f2f",
    bottom: "#1a1a1a",
    accent: "#8b2635",
    hairStyle: "gray",
    gender: "male",
    label: "Supplier CEO",
  },
  supplier_ceo_global: {
    skin: "#f0d0b0",
    hair: "#9e9e9e",
    top: "#2f2f2f",
    bottom: "#1a1a1a",
    accent: "#8b2635",
    hairStyle: "gray",
    gender: "male",
    label: "Supplier CEO",
    glasses: true,
  },
  legal_counsel: {
    skin: "#fdd5b8",
    hair: "#e6c547",
    top: "#1c1c1c",
    bottom: "#3d3d3d",
    accent: "#f5f5f5",
    hairStyle: "bob",
    gender: "female",
    label: "Legal counsel",
  },
  legal_counsel_global: {
    skin: "#fdd5b8",
    hair: "#e6c547",
    top: "#1c1c1c",
    bottom: "#3d3d3d",
    accent: "#f5f5f5",
    hairStyle: "bob",
    gender: "female",
    label: "Legal counsel",
  },
  procurement_ally: {
    skin: "#eecfb0",
    hair: "#8b4513",
    top: "#2d6a6a",
    bottom: "#4a5568",
    accent: "#48cae4",
    hairStyle: "ponytail",
    gender: "female",
    label: "Procurement ally",
  },
  procurement_ally_global: {
    skin: "#eecfb0",
    hair: "#8b4513",
    top: "#2d6a6a",
    bottom: "#4a5568",
    accent: "#48cae4",
    hairStyle: "ponytail",
    gender: "female",
    label: "Procurement ally",
  },
  procurement_strategy_manager: {
    skin: "#eecfb0",
    hair: "#8b4513",
    top: "#2d6a6a",
    bottom: "#4a5568",
    accent: "#48cae4",
    hairStyle: "ponytail",
    gender: "female",
    label: "Strategy manager",
    necklace: true,
  },
  supplier_quality_manager: {
    skin: "#f0d0b0",
    hair: "#4a4a4a",
    top: "#3a4a5c",
    bottom: "#2a2a2a",
    accent: "#7a8fa6",
    hairStyle: "bob",
    gender: "female",
    label: "Quality manager",
    glasses: true,
  },
};

const FALLBACK: MinecraftAvatarSpec = {
  skin: "#e8c4a8",
  hair: "#4a3728",
  top: "#444444",
  bottom: "#2a2a2a",
  accent: "#58a6ff",
  hairStyle: "short",
  gender: "male",
  label: "Guest",
};

export function resolveMinecraftSpec(
  characterId: string,
  manifest: AvatarManifest | undefined,
  patternLabel?: string,
): MinecraftAvatarSpec {
  const base = PRESETS[characterId] || FALLBACK;
  const m = manifest || {};

  return {
    skin: String(m.skin || base.skin),
    hair: String(m.hair || base.hair),
    top: String(m.top || m.suit || base.top),
    bottom: String(m.bottom || base.bottom),
    accent: String(m.accent || base.accent),
    hairStyle: (m.hair_style as MinecraftHairStyle) || base.hairStyle,
    gender: (m.gender as MinecraftGender) || base.gender,
    label: String(m.label || patternLabel || base.label),
    glasses: m.glasses !== undefined ? Boolean(m.glasses) : base.glasses,
    necklace: m.necklace !== undefined ? Boolean(m.necklace) : base.necklace,
  };
}

export function isMinecraftStyle(manifest?: AvatarManifest): boolean {
  return (manifest?.avatar_style || "minecraft") === "minecraft";
}
