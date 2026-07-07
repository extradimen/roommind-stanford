import type { PlayerCharacter, Scenario } from "./api";
import { resolvePlayerFullName, resolvePlayerLabel } from "./characterNames";

export function resolvePlayerCharacter(scenario: Scenario | null | undefined): PlayerCharacter | null {
  if (!scenario) return null;

  if (scenario.player_character?.character_name || scenario.player_character?.job_title) {
    return scenario.player_character;
  }

  const raw = scenario.scene_config?.player_character;
  if (raw && typeof raw === "object") {
    const pc = raw as Record<string, unknown>;
    const character_name = String(pc.character_name || "").trim();
    const job_title = String(pc.job_title || "").trim();
    if (character_name || job_title) {
      const display_name =
        String(pc.display_name || "").trim() ||
        (character_name && job_title
          ? `${character_name} (${job_title})`
          : character_name || job_title);
      return {
        character_name,
        job_title,
        display_name,
        avatar_manifest: (pc.avatar_manifest as PlayerCharacter["avatar_manifest"]) || {},
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
