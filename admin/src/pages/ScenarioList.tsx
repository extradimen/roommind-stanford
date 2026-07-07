import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ScenarioListItem } from "../api";
import { useLocale } from "../i18n";

async function copyTextToClipboard(text: string): Promise<void> {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  const ok = document.execCommand("copy");
  document.body.removeChild(textarea);
  if (!ok) {
    throw new Error("Copy failed");
  }
}

export default function ScenarioList() {
  const { t } = useLocale();
  const [items, setItems] = useState<ScenarioListItem[]>([]);
  const [error, setError] = useState("");
  const [copyMsg, setCopyMsg] = useState("");

  const load = () => {
    api.listScenarios().then(setItems).catch((e) => setError(String(e)));
  };

  useEffect(load, []);

  const remove = async (id: number) => {
    if (!confirm(t.scenarios.confirmDelete)) return;
    await api.deleteScenario(id);
    load();
  };

  const exampleScenarioId = () => {
    const preferred = items.find((s) => s.slug === "supply-chain-negotiation");
    return preferred?.id ?? items[0]?.id;
  };

  const downloadExample = async () => {
    const id = exampleScenarioId();
    if (!id) {
      setError(t.scenarios.downloadExampleFailed);
      return;
    }
    try {
      const data = await api.exportScenario(id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "roommind-scenario-example.json";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(String(e));
    }
  };

  const copyPrompt = async () => {
    try {
      setError("");
      await copyTextToClipboard(t.scenarios.aiGuidePrompt);
      setCopyMsg(t.scenarios.copiedPrompt);
      setTimeout(() => setCopyMsg(""), 2000);
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1>{t.scenarios.title}</h1>
        <Link to="/scenarios/new" className="btn primary">{t.scenarios.newScenario}</Link>
      </div>

      {error && <div className="alert error">{error}</div>}

      <section className="form-panel wide" style={{ marginBottom: "1.5rem" }}>
        <h2>{t.scenarios.aiGuideTitle}</h2>
        <p className="muted">{t.scenarios.aiGuideIntro}</p>

        <div className="row" style={{ margin: "0.75rem 0", gap: "0.5rem" }}>
          <button type="button" className="btn" onClick={downloadExample} disabled={!items.length}>
            {t.scenarios.downloadExample}
          </button>
          <button type="button" className="btn" onClick={copyPrompt}>
            {copyMsg || t.scenarios.copyPrompt}
          </button>
        </div>

        <div className="card" style={{ marginTop: "0.75rem" }}>
          <h3>{t.scenarios.aiGuideWorkflowTitle}</h3>
          <ol style={{ margin: "0.5rem 0 0 1.25rem", lineHeight: 1.6 }}>
            {t.scenarios.aiGuideWorkflow.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        </div>

        <div className="row" style={{ marginTop: "0.75rem", alignItems: "flex-start", gap: "1rem" }}>
          <div className="card" style={{ flex: 1 }}>
            <h3>{t.scenarios.aiGuideIncludesTitle}</h3>
            <ul style={{ margin: "0.5rem 0 0 1rem", lineHeight: 1.6 }}>
              {t.scenarios.aiGuideIncludes.map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ul>
          </div>
          <div className="card" style={{ flex: 1 }}>
            <h3>{t.scenarios.aiGuideExcludesTitle}</h3>
            <ul style={{ margin: "0.5rem 0 0 1rem", lineHeight: 1.6 }}>
              {t.scenarios.aiGuideExcludes.map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ul>
          </div>
        </div>

        <div className="card" style={{ marginTop: "0.75rem" }}>
          <h3>{t.scenarios.aiGuidePromptTitle}</h3>
          <pre className="code-block" style={{ maxHeight: "16rem", overflow: "auto", whiteSpace: "pre-wrap" }}>
            {t.scenarios.aiGuidePrompt}
          </pre>
        </div>
      </section>

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
