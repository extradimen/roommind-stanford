/** Localize server-generated agent memory text for English UI. */

import type { Locale } from "./i18n";

const CHARACTER_NAMES: Record<string, { zh: { full: string; short: string }; en: { full: string; short: string } }> = {
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

function replaceCharacterNames(text: string): string {
  let out = text;
  for (const c of Object.values(CHARACTER_NAMES)) {
    out = out.split(c.zh.full).join(c.en.full);
    out = out.split(c.zh.short).join(c.en.short);
  }
  return out;
}

type Pattern = { re: RegExp; format: (...groups: string[]) => string };

const EN_PATTERNS: Pattern[] = [
  { re: /^采购方说：「([\s\S]*)」$/, format: (c) => `Buyer said: "${c}"` },
  { re: /^我刚才说：「([\s\S]*)」$/, format: (c) => `I just said: "${c}"` },
  { re: /^发言：「([\s\S]*)」$/, format: (c) => `Spoke: "${c}"` },
  { re: /^(.+) 说：「([\s\S]*)」$/, format: (n, c) => `${n} said: "${c}"` },
  { re: /^(.+) 选择观望，暂不发言$/, format: (n) => `${n} chose to wait and did not speak this turn` },
  { re: /^更新计划：([\s\S]*)$/, format: (p) => `Updated plan: ${p}` },
  { re: /^（内心）([\s\S]*)$/, format: (n) => `(Inner note) ${n}` },
  { re: /^内心整理：([\s\S]*)$/, format: (n) => `Inner note: ${n}` },
  { re: /^环境变化：([\s\S]*)$/, format: (c) => `Environment change: ${c}` },
];

export function localizeMemoryContent(content: string, locale: Locale): string {
  if (locale === "zh" || !content?.trim()) return content;
  const named = replaceCharacterNames(content.trim());
  for (const { re, format } of EN_PATTERNS) {
    const m = named.match(re);
    if (m) return format(...m.slice(1));
  }
  return named;
}
