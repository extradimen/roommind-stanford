import { useCallback, useEffect, useState } from "react";
import { api, SessionDebug, SessionListItem } from "../api";
import AgentMemoryPanel, { type AgentMemoriesData } from "../components/AgentMemoryPanel";
import { useLocale } from "../i18n";

export default function SessionDebugPage() {
  const { t } = useLocale();
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [selectedUuid, setSelectedUuid] = useState("");
  const [debug, setDebug] = useState<SessionDebug | null>(null);
  const [scenarioFilter, setScenarioFilter] = useState("");
  const [msg, setMsg] = useState("");
  const [memoryLoading, setMemoryLoading] = useState(false);

  const loadSessions = () => {
    const sid = scenarioFilter ? parseInt(scenarioFilter) : undefined;
    api.listSessions(sid)
      .then((list) => {
        setSessions(list);
        if (!selectedUuid && list.length) setSelectedUuid(list[0].session_uuid);
      })
      .catch((e) => setMsg(String(e)));
  };

  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    if (!selectedUuid) {
      setDebug(null);
      return;
    }
    setMemoryLoading(true);
    api.getSessionDebug(selectedUuid)
      .then(setDebug)
      .catch((e) => setMsg(String(e)))
      .finally(() => setMemoryLoading(false));
  }, [selectedUuid]);

  const reloadDebug = useCallback(() => {
    if (!selectedUuid) return;
    setMemoryLoading(true);
    api.getSessionDebug(selectedUuid)
      .then(setDebug)
      .catch((e) => setMsg(String(e)))
      .finally(() => setMemoryLoading(false));
  }, [selectedUuid]);

  const memoryData: AgentMemoriesData | null = debug
    ? {
        orchestration_mode: debug.orchestration_mode,
        character_names: debug.character_names || {},
        agents: (debug.agent_memories || {}) as AgentMemoriesData["agents"],
        last_agent_debug: (debug.last_debug?.agents as Record<string, Record<string, unknown>>) || {},
      }
    : null;

  return (
    <div>
      <div className="page-header">
        <h1>{t.sessionDebug.title}</h1>
        <button type="button" className="btn small" onClick={loadSessions}>{t.sessionDebug.refreshList}</button>
      </div>

      <p className="muted">{t.sessionDebug.subtitle}</p>

      {msg && <div className="alert error">{msg}</div>}

      <div className="form-panel" style={{ marginBottom: "1rem" }}>
        <label>
          {t.sessionDebug.filterByScenario}
          <input
            value={scenarioFilter}
            onChange={(e) => setScenarioFilter(e.target.value)}
            placeholder={t.sessionDebug.filterPlaceholder}
          />
        </label>
        <button type="button" className="btn small" onClick={loadSessions}>{t.common.apply}</button>
        <label>
          {t.sessionDebug.selectSession}
          <select value={selectedUuid} onChange={(e) => setSelectedUuid(e.target.value)}>
            <option value="">{t.common.none}</option>
            {sessions.map((s) => (
              <option key={s.session_uuid} value={s.session_uuid}>
                {t.sessionDebug.sessionOption
                  .replace("{uuid}", s.session_uuid.slice(0, 8))
                  .replace("{scenarioId}", String(s.scenario_id))
                  .replace("{mode}", s.orchestration_mode)
                  .replace("{phase}", s.current_phase)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {!debug && <div>{t.sessionDebug.noData}</div>}

      {debug && (
        <div className="debug-grid">
          <AgentMemoryPanel
            data={memoryData}
            loading={memoryLoading}
            onRefresh={reloadDebug}
          />

          <div className="card">
            <h3>{t.sessionDebug.sessionOverview}</h3>
            <ul className="port-list">
              <li>{t.sessionDebug.uuid}: <code>{debug.session_uuid}</code></li>
              <li>{t.sessionDebug.scenarioId}: {debug.scenario_id}</li>
              <li>{t.sessionDebug.orchestration}: {t.sessionDebug.orchestrationValue}</li>
              <li>{t.sessionDebug.currentPhase}: {debug.current_phase}</li>
            </ul>
          </div>

          <div className="card">
            <h3>{t.sessionDebug.worldTimeline}</h3>
            <pre className="code-block">
              {JSON.stringify(
                (debug.shared_state?.world_timeline as unknown[]) || [],
                null,
                2,
              )}
            </pre>
          </div>

          <div className="card">
            <h3>{t.sessionDebug.lastDebug}</h3>
            <pre className="code-block">{JSON.stringify(debug.last_debug, null, 2)}</pre>
          </div>

          <div className="card">
            <h3>{t.sessionDebug.sharedState}</h3>
            <pre className="code-block">{JSON.stringify(debug.shared_state, null, 2)}</pre>
          </div>

          <div className="card">
            <h3>{t.sessionDebug.orchConfig}</h3>
            <pre className="code-block">{JSON.stringify(debug.orchestration_config, null, 2)}</pre>
          </div>

          <div className="card full-width">
            <h3>{t.sessionDebug.messages.replace("{count}", String(debug.messages.length))}</h3>
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t.sessionDebug.speaker}</th>
                  <th>{t.sessionDebug.speakerType}</th>
                  <th>{t.sessionDebug.content}</th>
                  <th>{t.sessionDebug.emotionGesture}</th>
                </tr>
              </thead>
              <tbody>
                {debug.messages.map((m, i) => (
                  <tr key={i}>
                    <td><code>{m.speaker_id}</code></td>
                    <td>{m.speaker_type}</td>
                    <td>{m.content}</td>
                    <td>{m.emotion || t.common.none} · {m.gesture || t.common.none}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
