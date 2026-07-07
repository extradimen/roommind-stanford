import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, PlatformConfig, ScenarioListItem } from "../api";
import { useLocale } from "../i18n";

export default function Dashboard() {
  const { t } = useLocale();
  const [scenarios, setScenarios] = useState<ScenarioListItem[]>([]);
  const [platform, setPlatform] = useState<PlatformConfig | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.listScenarios(), api.getPlatformConfig()])
      .then(([s, p]) => {
        setScenarios(s);
        setPlatform(p);
      })
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <div>
      <h1>{t.dashboard.title}</h1>
      <p className="muted">{t.dashboard.subtitle}</p>

      {error && <div className="alert error">{error}</div>}

      <div className="cards">
        <div className="card">
          <h3>{t.dashboard.servicePorts}</h3>
          {platform ? (
            <ul className="port-list">
              <li>{t.dashboard.api}: <code>{platform.ports.api}</code></li>
              <li>{t.dashboard.admin}: <code>{platform.ports.admin}</code></li>
              <li>{t.dashboard.client}: <code>{platform.ports.client}</code></li>
              <li>{t.dashboard.postgres}: <code>{platform.ports.postgres}</code></li>
              <li>{t.dashboard.redis}: <code>{platform.ports.redis}</code></li>
            </ul>
          ) : (
            <p className="muted">{t.common.loading}</p>
          )}
          <Link to="/platform" className="btn">{t.dashboard.editPorts}</Link>
        </div>
        <div className="card">
          <h3>{t.dashboard.devPhase}</h3>
          <ol className="phase-list">
            <li className="active">{t.dashboard.phase1}</li>
            <li>{t.dashboard.phase2}</li>
            <li>{t.dashboard.phase3}</li>
          </ol>
        </div>
        <div className="card">
          <h3>{t.dashboard.scenarios}</h3>
          <p>{t.dashboard.scenarioCount.replace("{count}", String(scenarios.length))}</p>
          <Link to="/scenarios" className="btn">{t.dashboard.manageScenarios}</Link>
        </div>
      </div>
    </div>
  );
}
