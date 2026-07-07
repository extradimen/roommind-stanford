import type { Character } from "./api";

export type CharacterSide = "opponent" | "player_ally";

export function buildCharacterSideMap(
  characters: Character[] | undefined,
): Record<string, CharacterSide> {
  return Object.fromEntries(
    (characters || []).map((c) => [c.character_id, c.side || "opponent"]),
  );
}

export function resolveCharacterSide(
  speakerId: string,
  sideMap: Record<string, CharacterSide>,
): CharacterSide | "user" {
  if (speakerId === "user") return "user";
  return sideMap[speakerId] || "opponent";
}
