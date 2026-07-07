import { Link } from "react-router-dom";
import AppShell from "../components/AppShell";
import RoomMindArchitecture from "../components/system/RoomMindArchitecture";
import { useLocale } from "../i18n";

export default function SystemPage() {
  const { t } = useLocale();
  const s = t.system.sections;

  return (
    <AppShell>
      <div className="system-page">
        <header className="system-hero">
          <h1>{t.system.title}</h1>
          <p>{t.system.subtitle}</p>
          <Link to="/play/1" className="play-btn system-cta">
            {t.system.playCta}
          </Link>
        </header>

        <section className="system-card system-overview-card">
          <h2>{s.overview.title}</h2>
          <p>{s.overview.body}</p>
        </section>

        <section className="system-card system-arch-card">
          <RoomMindArchitecture />
        </section>

        <section className="system-card">
          <h2>{s.scoring.title}</h2>
          <div className="system-formula">score = α·recency + β·importance + γ·relevance</div>
          <table className="system-table">
            <thead>
              <tr>
                {s.scoring.cols.map((c) => (
                  <th key={c}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {s.scoring.rows.map((row, i) => (
                <tr key={i}>
                  {row.map((cell, j) => (
                    <td key={j}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="system-card system-grid-2">
          <div>
            <h2>{s.world.title}</h2>
            <ul className="system-bullet-list">
              {s.world.items.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
          <div>
            <h2>{s.culture.title}</h2>
            <p>{s.culture.body}</p>
            <div className="culture-badges">
              <span className="badge east">{s.culture.badges.east}</span>
              <span className="badge west">{s.culture.badges.west}</span>
              <span className="badge global">{s.culture.badges.global}</span>
            </div>
          </div>
        </section>

        <section className="system-card">
          <h2>{s.stack.title}</h2>
          <ul className="stack-list">
            {s.stack.items.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </section>

        <footer className="system-footer">
          <Link to="/">{t.nav.home}</Link>
          <Link to="/play/1">{t.nav.play}</Link>
        </footer>
      </div>
    </AppShell>
  );
}
