import type { PlayerCharacter, Scenario } from "./api";
import { resolvePlayerFullName, resolvePlayerLabel } from "./characterNames";

function pickAvatarManifest(
  primary?: PlayerCharacter["avatar_manifest"],
  fallback?: unknown,
): PlayerCharacter["avatar_manifest"] {
  const a: NonNullable<PlayerCharacter["avatar_manifest"]> =
    primary && typeof primary === "object" ? primary : {};
  const b: NonNullable<PlayerCharacter["avatar_manifest"]> =
    fallback && typeof fallback === "object"
      ? (fallback as NonNullable<PlayerCharacter["avatar_manifest"]>)
      : {};
  const aUrl = typeof a.model_url === "string" ? a.model_url.trim() : "";
  const bUrl = typeof b.model_url === "string" ? b.model_url.trim() : "";
  if (aUrl) return a;
  if (bUrl) return b;
  return Object.keys(a).length ? a : b;
}

export function resolvePlayerCharacter(scenario: Scenario | null | undefined): PlayerCharacter | null {
  if (!scenario) return null;

  const scenePc =
    scenario.scene_config?.player_character && typeof scenario.scene_config.player_character === "object"
      ? (scenario.scene_config.player_character as Record<string, unknown>)
      : null;

  if (scenario.player_character?.character_name || scenario.player_character?.job_title) {
    return {
      ...scenario.player_character,
      avatar_manifest: pickAvatarManifest(
        scenario.player_character.avatar_manifest,
        scenePc?.avatar_manifest,
      ),
    };
  }

  if (scenePc) {
    const character_name = String(scenePc.character_name || "").trim();
    const job_title = String(scenePc.job_title || "").trim();
    if (character_name || job_title) {
      const display_name =
        String(scenePc.display_name || "").trim() ||
        (character_name && job_title
          ? `${character_name} (${job_title})`
          : character_name || job_title);
      return {
        character_name,
        job_title,
        display_name,
        avatar_manifest: pickAvatarManifest(undefined, scenePc.avatar_manifest),
      };
    }
  }

  return null;
}

export function resolvePlayerLegendLabel(
  scenario: Scenario | null | undefined,
  fallback: string,
): string {
  const player = resolvePlayerCharacter(scenario);
  return resolvePlayerFullName(player || undefined) || fallback;
}

export function resolvePlayerChatLabel(
  scenario: Scenario | null | undefined,
  fallback: string,
): string {
  const player = resolvePlayerCharacter(scenario);
  return resolvePlayerLabel(player || undefined) || fallback;
}
