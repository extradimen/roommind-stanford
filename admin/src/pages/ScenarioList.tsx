import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ScenarioListItem } from "../api";
import { useLocale } from "../i18n";

export default function ScenarioList() {
  const { t } = useLocale();
  const [items, setItems] = useState<ScenarioListItem[]>([]);
  const [error, setError] = useState("");

  const load = () => {
    api.listScenarios().then(setItems).catch((e) => setError(String(e)));
  };

  useEffect(load, []);

  const remove = async (id: number) => {
    if (!confirm(t.scenarios.confirmDelete)) return;
    await api.deleteScenario(id);
    load();
  };

  return (
    <div>
      <div className="page-header">
        <h1>{t.scenarios.title}</h1>
        <Link to="/scenarios/new" className="btn primary">{t.scenarios.newScenario}</Link>
      </div>

      {error && <div className="alert error">{error}</div>}

      <table className="data-table">
        <thead>
          <tr>
            <th>{t.common.id}</th>
            <th>{t.scenarios.slug}</th>
            <th>{t.scenarios.tableTitle}</th>
            <th>{t.scenarios.characterCount}</th>
            <th>{t.scenarios.published}</th>
            <th>{t.common.actions}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((s) => (
            <tr key={s.id}>
              <td>{s.id}</td>
              <td><code>{s.slug}</code></td>
              <td>{s.title}</td>
              <td>{s.character_count}</td>
              <td>{s.is_published ? "✓" : t.common.none}</td>
              <td>
                <Link to={`/scenarios/${s.id}`} className="btn small">{t.common.edit}</Link>
                <Link to={`/scenarios/${s.id}/orchestration`} className="btn small">{t.scenarios.agent}</Link>
                <button className="btn small danger" onClick={() => remove(s.id)}>{t.common.delete}</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
