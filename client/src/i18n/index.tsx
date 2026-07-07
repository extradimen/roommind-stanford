import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { en } from "./locales/en";
import { zh } from "./locales/zh";
import type { Messages } from "./types";

export type Locale = "zh" | "en";

const STORAGE_KEY = "roommind-stanford:locale";
const COOKIE_KEY = "roommind-stanford-locale";

const locales: Record<Locale, Messages> = { zh, en };

type LocaleContextValue = {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: Messages;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

function readCookieLocale(): Locale | null {
  try {
    const match = document.cookie.match(new RegExp(`(?:^|; )${COOKIE_KEY}=(zh|en)(?:;|$)`));
    if (match) return match[1] as Locale;
  } catch {
    /* ignore */
  }
  return null;
}

function readBrowserLocale(): Locale {
  if (typeof navigator !== "undefined") {
    const langs = [navigator.language, ...(navigator.languages || [])];
    for (const l of langs) {
      if (l?.toLowerCase().startsWith("en")) return "en";
      if (l?.toLowerCase().startsWith("zh")) return "zh";
    }
  }
  return "zh";
}

function readStoredLocale(): Locale {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === "en" || v === "zh") return v;
  } catch {
    /* ignore */
  }
  const fromCookie = readCookieLocale();
  if (fromCookie) return fromCookie;
  return readBrowserLocale();
}

function persistLocale(l: Locale) {
  try {
    localStorage.setItem(STORAGE_KEY, l);
  } catch {
    /* ignore */
  }
  try {
    document.cookie = `${COOKIE_KEY}=${l}; path=/; max-age=31536000; SameSite=Lax`;
  } catch {
    /* ignore */
  }
  document.documentElement.lang = l === "zh" ? "zh-CN" : "en";
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(readStoredLocale);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    persistLocale(l);
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
  }, [locale]);

  const value = useMemo(
    () => ({ locale, setLocale, t: locales[locale] }),
    [locale, setLocale],
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useLocale must be used within LocaleProvider");
  return ctx;
}
