import { FormEvent, useEffect, useState } from "react";
import { api, DispatchRule, DispatchRuleInput, ScenarioListItem } from "../api";
import { useLocale } from "../i18n";

const emptyRule = (scenarioId: number | null = null): DispatchRuleInput => ({
  scenario_id: scenarioId,
  name: "",
  description: "",
  trigger_keywords: [],
  priority_character_ids: [],
  min_speakers: 1,
  max_speakers: 2,
  weights: {},
  is_active: true,
});

export default function DispatchRules() {
  const { t } = useLocale();
  const [rules, setRules] = useState<DispatchRule[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioListItem[]>([]);
  const [filterScenario, setFilterScenario] = useState<number | "">("");
  const [editing, setEditing] = useState<DispatchRuleInput & { id?: number } | null>(null);
  const [keywordsText, setKeywordsText] = useState("");
  const [charsText, setCharsText] = useState("");
  const [msg, setMsg] = useState("");
  const [msgOk, setMsgOk] = useState(false);

  const load = () => {
    const sid = filterScenario === "" ? undefined : filterScenario;
    api.listDispatchRules(sid).then(setRules).catch((e) => {
      setMsg(String(e));
      setMsgOk(false);
    });
  };

  useEffect(() => {
    api.listScenarios().then(setScenarios);
  }, []);

  useEffect(load, [filterScenario]);

  const startNew = () => {
    const sid = filterScenario === "" ? null : filterScenario;
    setEditing(emptyRule(sid));
    setKeywordsText("");
    setCharsText("");
  };

  const startEdit = (r: DispatchRule) => {
    setEditing({ ...r });
    setKeywordsText(r.trigger_keywords.join(", "));
    setCharsText(r.priority_character_ids.join(", "));
  };

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (!editing) return;
    const payload: DispatchRuleInput = {
      ...editing,
      trigger_keywords: keywordsText.split(",").map((s) => s.trim()).filter(Boolean),
      priority_character_ids: charsText.split(",").map((s) => s.trim()).filter(Boolean),
    };
    try {
      if (editing.id) {
        await api.updateDispatchRule(editing.id, payload);
      } else {
        await api.createDispatchRule(payload);
      }
      setEditing(null);
      load();
      setMsg(t.common.saved);
      setMsgOk(true);
    } catch (err) {
      setMsg(String(err));
      setMsgOk(false);
    }
  };

  const remove = async (id: number) => {
    if (!confirm(t.common.confirmDelete)) return;
    await api.deleteDispatchRule(id);
    load();
  };

  return (
    <div>
      <div className="page-header">
        <h1>{t.dispatch.title}</h1>
        <button className="btn primary" onClick={startNew}>{t.dispatch.newRule}</button>
      </div>

      <p className="muted">{t.dispatch.subtitle}</p>

      <label>
        {t.dispatch.filterScenario}
        <select value={filterScenario} onChange={(e) => setFilterScenario(e.target.value ? parseInt(e.target.value) : "")}>
          <option value="">{t.common.all}</option>
          {scenarios.map((s) => (
            <option key={s.id} value={s.id}>{s.title}</option>
          ))}
        </select>
      </label>

      {msg && <p className={msgOk ? "success" : "error"}>{msg}</p>}

      {editing && (
        <form onSubmit={save} className="form-panel">
          <h2>{editing.id ? t.dispatch.editRule : t.dispatch.newRule}</h2>
          <label>{t.dispatch.name}<input required value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></label>
          <label>{t.dispatch.description}<textarea value={editing.description || ""} onChange={(e) => setEditing({ ...editing, description: e.target.value })} /></label>
          <label>{t.dispatch.linkedScenario}
            <select
              value={editing.scenario_id ?? ""}
              onChange={(e) => setEditing({ ...editing, scenario_id: e.target.value ? parseInt(e.target.value) : null })}
            >
              <option value="">{t.common.global}</option>
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>{s.title}</option>
              ))}
            </select>
          </label>
          <label>{t.dispatch.triggerKeywords}<input value={keywordsText} onChange={(e) => setKeywordsText(e.target.value)} placeholder={t.dispatch.keywordsPlaceholder} /></label>
          <label>{t.dispatch.priorityChars}<input value={charsText} onChange={(e) => setCharsText(e.target.value)} placeholder={t.dispatch.charsPlaceholder} /></label>
          <div className="row">
            <label>{t.dispatch.minSpeakers}<input type="number" min={1} value={editing.min_speakers} onChange={(e) => setEditing({ ...editing, min_speakers: parseInt(e.target.value) })} /></label>
            <label>{t.dispatch.maxSpeakers}<input type="number" min={1} value={editing.max_speakers} onChange={(e) => setEditing({ ...editing, max_speakers: parseInt(e.target.value) })} /></label>
          </div>
          <label className="checkbox">
            <input type="checkbox" checked={editing.is_active} onChange={(e) => setEditing({ ...editing, is_active: e.target.checked })} />
            {t.common.enabled}
          </label>
          <div className="row">
            <button type="submit" className="btn primary">{t.common.save}</button>
            <button type="button" className="btn" onClick={() => setEditing(null)}>{t.common.cancel}</button>
          </div>
        </form>
      )}

      <table className="data-table">
        <thead>
          <tr>
            <th>{t.dispatch.tableName}</th>
            <th>{t.dispatch.tableKeywords}</th>
            <th>{t.dispatch.tablePriority}</th>
            <th>{t.dispatch.tableScenario}</th>
            <th>{t.dispatch.tableStatus}</th>
            <th>{t.common.actions}</th>
          </tr>
        </thead>
        <tbody>
          {rules.map((r) => (
            <tr key={r.id}>
              <td>{r.name}</td>
              <td>{r.trigger_keywords.join(", ")}</td>
              <td>{r.priority_character_ids.join(", ")}</td>
              <td>{r.scenario_id ?? t.common.global}</td>
              <td>{r.is_active ? t.common.enabled : t.common.disabled}</td>
              <td>
                <button className="btn small" onClick={() => startEdit(r)}>{t.common.edit}</button>
                <button className="btn small danger" onClick={() => remove(r.id)}>{t.common.delete}</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
