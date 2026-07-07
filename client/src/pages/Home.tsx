import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AppShell from "../components/AppShell";
import { listScenarios, resolveServiceUrls, Scenario } from "../api";
import { resolveScenarioText } from "../characterNames";
import { useLocale } from "../i18n";

export default function Home() {
  const { t } = useLocale();
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [error, setError] = useState("");
  const [adminUrl, setAdminUrl] = useState("");

  useEffect(() => {
    listScenarios()
      .then(setScenarios)
      .catch((e) => setError(String(e)));
    resolveServiceUrls()
      .then((u) => setAdminUrl(u.admin))
      .catch(() => {});
  }, []);

  return (
    <AppShell>
      <div className="home">
        <header>
          <h1>{t.home.title}</h1>
          <p>{t.home.subtitle}</p>
        </header>

        <Link to="/system" className="system-banner">
          <div className="system-banner-text">
            <strong>{t.home.systemBannerTitle}</strong>
            <span>{t.home.systemBannerDesc}</span>
          </div>
          <span className="system-banner-btn">{t.home.systemBannerBtn} →</span>
        </Link>

        {error && <div className="error-banner">{error}</div>}

        <div className="scenario-grid">
          {scenarios.map((s) => {
            const title = resolveScenarioText(
              s.slug,
              "title",
              s.title,
              t.scenarios as Record<string, Record<string, string>>,
            );
            const description = resolveScenarioText(
              s.slug,
              "description",
              s.description || "",
              t.scenarios as Record<string, Record<string, string>>,
            );
            return (
            <div key={s.id} className="scenario-card">
              <h2>{title}</h2>
              <p>{description}</p>
              <Link to={`/play/${s.id}`} className="play-btn">
                {t.home.enter}
              </Link>
            </div>
            );
          })}
          {scenarios.length === 0 && !error && (
            <p className="empty">{t.home.empty}</p>
          )}
        </div>

        <footer>
          {adminUrl ? (
            <a href={adminUrl} target="_blank" rel="noreferrer">
              {t.nav.admin}
            </a>
          ) : (
            <span className="muted">{t.nav.admin}</span>
          )}
        </footer>
      </div>
    </AppShell>
  );
}
