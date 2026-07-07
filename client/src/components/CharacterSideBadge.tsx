import { useLocale } from "../i18n";
import type { CharacterSide } from "../characterSide";

type Props = {
  side: CharacterSide | "user";
  compact?: boolean;
};

export default function CharacterSideBadge({ side, compact }: Props) {
  const { t } = useLocale();
  const label =
    side === "user"
      ? t.game.sideYou
      : side === "player_ally"
        ? t.game.sideAlly
        : t.game.sideOpponent;

  return (
    <span className={`char-side-badge side-${side}${compact ? " compact" : ""}`} title={label}>
      {label}
    </span>
  );
}
