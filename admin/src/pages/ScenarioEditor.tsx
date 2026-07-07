import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, Character, ScenarioInput } from "../api";
import { useLocale } from "../i18n";

const emptyCharacter = (): Character => ({
  character_id: "",
  display_name: "",
  persona: "",
  responsibility: "",
  tendency: { risk: "medium", aggression: "medium", cooperation: "medium" },
  private_state: {},
  avatar_manifest: { color: "#888888" },
  sort_order: 0,
});

const defaultScenario = (): ScenarioInput => ({
  slug: "",
  title: "",
  description: "",
  business_goal: "",
  phases: ["opening", "discovery", "bargaining", "closing"],
  win_conditions: [],
  scene_config: { environment: "meeting_room", camera: "first_person" },
  is_published: false,
  characters: [emptyCharacter()],
});

export default function ScenarioEditor() {
  const { t } = useLocale();
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = id === "new" || !id;

  const [form, setForm] = useState<ScenarioInput>(defaultScenario());
  const [jsonPhases, setJsonPhases] = useState("");
  const [jsonWin, setJsonWin] = useState("[]");
  const [jsonScene, setJsonScene] = useState("{}");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [msgOk, setMsgOk] = useState(false);

  useEffect(() => {
    if (isNew) {
      const d = defaultScenario();
      setForm(d);
      setJsonPhases(JSON.stringify(d.phases, null, 2));
      setJsonWin(JSON.stringify(d.win_conditions, null, 2));
      setJsonScene(JSON.stringify(d.scene_config, null, 2));
      return;
    }
    api.getScenario(parseInt(id!)).then((s) => {
      setForm({
        slug: s.slug,
        title: s.title,
        description: s.description || "",
        business_goal: s.business_goal,
        phases: s.phases,
        win_conditions: s.win_conditions,
        scene_config: s.scene_config,
        is_published: s.is_published,
        characters: s.characters.length ? s.characters : [emptyCharacter()],
      });
      setJsonPhases(JSON.stringify(s.phases, null, 2));
      setJsonWin(JSON.stringify(s.win_conditions, null, 2));
      setJsonScene(JSON.stringify(s.scene_config, null, 2));
    });
  }, [id, isNew]);

  const updateChar = (idx: number, patch: Partial<Character>) => {
    const chars = [...form.characters];
    chars[idx] = { ...chars[idx], ...patch };
    setForm({ ...form, characters: chars });
  };

  const addChar = () => {
    setForm({ ...form, characters: [...form.characters, emptyCharacter()] });
  };

  const removeChar = (idx: number) => {
    setForm({ ...form, characters: form.characters.filter((_, i) => i !== idx) });
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMsg("");
    try {
      const payload: ScenarioInput = {
        ...form,
        phases: JSON.parse(jsonPhases),
        win_conditions: JSON.parse(jsonWin),
        scene_config: JSON.parse(jsonScene),
      };
      if (isNew) {
        const created = await api.createScenario(payload);
        navigate(`/scenarios/${created.id}`);
      } else {
        await api.updateScenario(parseInt(id!), payload);
      }
      setMsg(t.common.saved);
      setMsgOk(true);
    } catch (err) {
      setMsg(String(err));
      setMsgOk(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <h1>{isNew ? t.scenarioEditor.newTitle : t.scenarioEditor.editTitle}</h1>
      {!isNew && id && (
        <p className="muted">
          <Link to={`/scenarios/${id}/orchestration`}>{t.scenarioEditor.orchestrationLink}</Link>
        </p>
      )}

      <form onSubmit={submit} className="form-panel wide">
        <section>
          <h2>{t.scenarioEditor.basicInfo}</h2>
          <div className="row">
            <label>{t.scenarioEditor.slug}<input required value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} /></label>
            <label>{t.scenarioEditor.title}<input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
          </div>
          <label>{t.scenarioEditor.description}<textarea value={form.description || ""} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} /></label>
          <label>{t.scenarioEditor.businessGoal}<textarea required value={form.business_goal} onChange={(e) => setForm({ ...form, business_goal: e.target.value })} rows={3} /></label>
          <label className="checkbox">
            <input type="checkbox" checked={form.is_published} onChange={(e) => setForm({ ...form, is_published: e.target.checked })} />
            {t.scenarioEditor.publish}
          </label>
        </section>

        <section>
          <h2>{t.scenarioEditor.phasesSection}</h2>
          <label>{t.scenarioEditor.phasesJson}<textarea value={jsonPhases} onChange={(e) => setJsonPhases(e.target.value)} rows={4} className="mono" /></label>
          <label>{t.scenarioEditor.winConditionsJson}<textarea value={jsonWin} onChange={(e) => setJsonWin(e.target.value)} rows={5} className="mono" /></label>
          <label>{t.scenarioEditor.sceneConfigJson}<textarea value={jsonScene} onChange={(e) => setJsonScene(e.target.value)} rows={5} className="mono" /></label>
        </section>

        <section>
          <div className="section-header">
            <h2>{t.scenarioEditor.characters}</h2>
            <button type="button" className="btn" onClick={addChar}>{t.scenarioEditor.addCharacter}</button>
          </div>
          {form.characters.map((c, idx) => (
            <div key={idx} className="char-card">
              <div className="char-header">
                <strong>{t.scenarioEditor.characterN.replace("{n}", String(idx + 1))}</strong>
                {form.characters.length > 1 && (
                  <button type="button" className="btn small danger" onClick={() => removeChar(idx)}>{t.common.delete}</button>
                )}
              </div>
              <div className="row">
                <label>{t.scenarioEditor.characterId}<input required value={c.character_id} onChange={(e) => updateChar(idx, { character_id: e.target.value })} /></label>
                <label>{t.scenarioEditor.displayName}<input required value={c.display_name} onChange={(e) => updateChar(idx, { display_name: e.target.value })} /></label>
                <label>{t.scenarioEditor.spawnPoint}<input value={c.spawn_point || ""} onChange={(e) => updateChar(idx, { spawn_point: e.target.value })} /></label>
              </div>
              <label>{t.scenarioEditor.persona}<textarea required value={c.persona} onChange={(e) => updateChar(idx, { persona: e.target.value })} rows={2} /></label>
              <label>{t.scenarioEditor.responsibility}<textarea required value={c.responsibility} onChange={(e) => updateChar(idx, { responsibility: e.target.value })} rows={2} /></label>
              <div className="row">
                <label>{t.scenarioEditor.tendencyJson}<textarea value={JSON.stringify(c.tendency)} onChange={(e) => updateChar(idx, { tendency: JSON.parse(e.target.value) })} rows={2} className="mono" /></label>
                <label>{t.scenarioEditor.privateStateJson}<textarea value={JSON.stringify(c.private_state)} onChange={(e) => updateChar(idx, { private_state: JSON.parse(e.target.value) })} rows={2} className="mono" /></label>
              </div>
              <label>{t.scenarioEditor.systemPrompt}<textarea value={c.system_prompt || ""} onChange={(e) => updateChar(idx, { system_prompt: e.target.value })} rows={2} /></label>
              <label>
                {t.scenarioEditor.llmConfigJson}
                <textarea
                  rows={2}
                  className="mono"
                  value={JSON.stringify(c.llm_config || {})}
                  onChange={(e) => {
                    try {
                      updateChar(idx, { llm_config: JSON.parse(e.target.value || "{}") });
                    } catch {
                      /* ignore */
                    }
                  }}
                />
              </label>
            </div>
          ))}
        </section>

        <button type="submit" className="btn primary" disabled={saving}>{saving ? t.common.saving : t.scenarioEditor.saveScenario}</button>
        {msg && <p className={msgOk ? "success" : "error"}>{msg}</p>}
      </form>
    </div>
  );
}
