import { useLocale, type Locale } from "../i18n";

export default function LanguageSwitcher({ className = "" }: { className?: string }) {
  const { locale, setLocale, t } = useLocale();

  return (
    <div className={`lang-switcher ${className}`.trim()} role="group" aria-label="Language">
      {(["zh", "en"] as Locale[]).map((l) => (
        <button
          key={l}
          type="button"
          className={locale === l ? "active" : ""}
          onClick={() => setLocale(l)}
        >
          {t.lang[l]}
        </button>
      ))}
    </div>
  );
}
