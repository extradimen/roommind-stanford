import type { Character, Scenario } from "../api";
import { resolveNpcLabel } from "../characterNames";
import { resolvePlayerLegendLabel } from "../playerCharacter";
import { buildCharacterSideMap } from "../characterSide";
import { useLocale } from "../i18n";
import CharacterSideBadge from "./CharacterSideBadge";

type Props = {
  characters: Character[];
  scenario: Scenario | null;
};

export default function CharacterSideLegend({ characters, scenario }: Props) {
  const { t, locale } = useLocale();
  const sideMap = buildCharacterSideMap(characters);

  const allies = characters.filter((c) => sideMap[c.character_id] === "player_ally");
  const opponents = characters.filter((c) => sideMap[c.character_id] !== "player_ally");

  if (allies.length === 0 && opponents.length === 0 && !scenario) return null;

  const renderGroup = (items: Character[], side: "player_ally" | "opponent") => (
    <div className="side-legend-group">
      <CharacterSideBadge side={side} />
      <span className="side-legend-names">
        {items
          .map((c) => resolveNpcLabel(c.character_id, {}, c.display_name, locale))
          .join(locale === "zh" ? "、" : ", ")}
      </span>
    </div>
  );

  const playerLabel = resolvePlayerLegendLabel(scenario, t.game.sideYouHint);

  return (
    <div className="character-side-legend" aria-label={t.game.sideLegend}>
      <span className="side-legend-title">{t.game.sideLegend}</span>
      {allies.length > 0 && renderGroup(allies, "player_ally")}
      {opponents.length > 0 && renderGroup(opponents, "opponent")}
      <div className="side-legend-group side-legend-you">
        <CharacterSideBadge side="user" />
        <span className="side-legend-names">{playerLabel}</span>
      </div>
    </div>
  );
}
