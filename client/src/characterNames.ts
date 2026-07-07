/** Shared NPC display-name helpers — keep chat, 3D scene & agent panels consistent. */

import type { Locale } from "./i18n";

const CHARACTER_I18N: Record<
  string,
  { zh: { full: string; short: string }; en: { full: string; short: string } }
> = {
  supplier_ceo: {
    zh: { full: "王总（供应商 CEO）", short: "王总" },
    en: { full: "Mr. Wang (Supplier CEO)", short: "Mr. Wang" },
  },
  legal_counsel: {
    zh: { full: "李律师（法务）", short: "李律师" },
    en: { full: "Attorney Li (Legal)", short: "Attorney Li" },
  },
  procurement_ally: {
    zh: { full: "张经理（内部采购同事）", short: "张经理" },
    en: { full: "Manager Zhang (Procurement Ally)", short: "Mgr. Zhang" },
  },
};

export function buildCharacterNameMap(
  characters: Array<{ character_id: string; display_name: string; character_name?: string; job_title?: string }> | undefined,
  locale: Locale = "zh",
): Record<string, string> {
  return Object.fromEntries(
    (characters || []).map((c) => {
      const fromApi =
        c.character_name && c.job_title
          ? `${c.character_name} (${c.job_title})`
          : c.character_name || c.display_name;
      return [
        c.character_id,
        CHARACTER_I18N[c.character_id]?.[locale]?.full || fromApi || c.character_id,
      ];
    }),
  );
}

/** Short label shown in UI, e.g. 王总（供应商 CEO） → 王总 */
export function npcShortName(name: string): string {
  const m = name.match(/^(.+?)（/);
  if (m) return m[1];
  const en = name.match(/^(.+?) \(/);
  if (en) return en[1];
  return name.length > 12 ? `${name.slice(0, 12)}…` : name;
}

export function resolvePlayerFullName(
  player: { character_name?: string; job_title?: string; display_name?: string } | undefined,
): string {
  if (!player) return "";
  if (player.display_name?.trim()) return player.display_name.trim();
  const name = (player.character_name || "").trim();
  const title = (player.job_title || "").trim();
  if (name && title) return `${name} (${title})`;
  return name || title;
}

export function resolvePlayerLabel(
  player: { character_name?: string; job_title?: string; display_name?: string } | undefined,
): string {
  const full = resolvePlayerFullName(player);
  if (!full) return "";
  return npcShortName(full);
}

export function resolveNpcFullName(
  speakerId: string,
  nameMap: Record<string, string>,
  fallback?: string,
  locale: Locale = "zh",
): string {
  const mapped = CHARACTER_I18N[speakerId]?.[locale];
  if (mapped) return mapped.full;
  return nameMap[speakerId] || fallback || speakerId;
}

export function resolveNpcLabel(
  speakerId: string,
  nameMap: Record<string, string>,
  fallback?: string,
  locale: Locale = "zh",
): string {
  const mapped = CHARACTER_I18N[speakerId]?.[locale];
  if (mapped) return mapped.short;
  return npcShortName(resolveNpcFullName(speakerId, nameMap, fallback, locale));
}

export function resolveScenarioText(
  slug: string | undefined,
  field: "title" | "description" | "goal",
  fallback: string,
  scenarios: Record<string, Record<string, string>> | undefined,
): string {
  if (!slug || !scenarios?.[slug]) return fallback;
  const entry = scenarios[slug] as Record<string, string>;
  return entry[field] || fallback;
}
