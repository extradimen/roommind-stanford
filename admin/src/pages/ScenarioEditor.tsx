import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, Character, ScenarioDispatchRule, ScenarioInput } from "../api";
import AvatarUpload from "../components/AvatarUpload";
import { useLocale } from "../i18n";

type PlayerCharacterForm = {
  character_name: string;
  job_title: string;
  avatar_manifest: Record<string, unknown>;
};

const emptyPlayerCharacter = (): PlayerCharacterForm => ({
  character_name: "Alex Chen",
  job_title: "Chief Procurement Officer",
  avatar_manifest: {
    suit: "#1e5631",
    accent: "#58a6ff",
    skin: "#e8b896",
    pattern: "global",
    accessory: "none",
    height: 1.72,
  },
});

const emptyCharacter = (): Character => ({
  character_id: "",
  side: "opponent",
  character_name: "",
  job_title: "",
  persona: "",
  responsibility: "",
  tendency: { risk: "medium", aggression: "medium", cooperation: "medium" },
  private_state: {},
  avatar_manifest: { color: "#888888" },
  sort_order: 0,
});

const emptyDispatchRule = (): ScenarioDispatchRule => ({
  name: "",
  description: "",
  trigger_keywords: [],
  priority_character_ids: [],
  min_speakers: 1,
  max_speakers: 2,
  weights: {},
  is_active: true,
});

const defaultScenario = (): ScenarioInput => ({
  slug: "",
  title: "",
  description: "",
  player_side_goal: "",
  opponent_side_goal: "",
  business_goal: "",
  phases: ["opening", "discovery", "bargaining", "closing"],
  win_conditions: [],
  scene_config: { environment: "meeting_room", camera: "first_person" },
  is_published: false,
  characters: [emptyCharacter()],
  dispatch_rules: [emptyDispatchRule()],
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
  const [ruleKeywords, setRuleKeywords] = useState<string[]>([""]);
  const [ruleChars, setRuleChars] = useState<string[]>([""]);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [msgOk, setMsgOk] = useState(false);
  const [importJson, setImportJson] = useState("");
  const [importing, setImporting] = useState(false);
  const [playerCharacter, setPlayerCharacter] = useState<PlayerCharacterForm>(emptyPlayerCharacter());

  const loadPlayerCharacter = (sceneConfig: Record<string, unknown>) => {
    const raw = sceneConfig.player_character;
    if (raw && typeof raw === "object") {
      const pc = raw as Record<string, unknown>;
      setPlayerCharacter({
        character_name: String(pc.character_name || emptyPlayerCharacter().character_name),
        job_title: String(pc.job_title || emptyPlayerCharacter().job_title),
        avatar_manifest: (pc.avatar_manifest as Record<string, unknown>) || emptyPlayerCharacter().avatar_manifest,
      });
      return;
    }
    setPlayerCharacter(emptyPlayerCharacter());
  };

  const applyScenario = (s: Awaited<ReturnType<typeof api.getScenario>>) => {
    const rules = s.dispatch_rules?.length ? s.dispatch_rules : [emptyDispatchRule()];
    setForm({
      slug: s.slug,
      title: s.title,
      description: s.description || "",
      player_side_goal: s.player_side_goal || s.business_goal || "",
      opponent_side_goal: s.opponent_side_goal || "",
      business_goal: s.business_goal,
      phases: s.phases,
      win_conditions: s.win_conditions,
      scene_config: s.scene_config,
      is_published: s.is_published,
      characters: s.characters.length ? s.characters : [emptyCharacter()],
      dispatch_rules: rules,
    });
    setJsonPhases(JSON.stringify(s.phases, null, 2));
    setJsonWin(JSON.stringify(s.win_conditions, null, 2));
    setJsonScene(JSON.stringify(s.scene_config, null, 2));
    loadPlayerCharacter(s.scene_config || {});
    setRuleKeywords(rules.map((r) => r.trigger_keywords.join(", ")));
    setRuleChars(rules.map((r) => r.priority_character_ids.join(", ")));
  };

  useEffect(() => {
    if (isNew) {
      const d = defaultScenario();
      setForm(d);
      setJsonPhases(JSON.stringify(d.phases, null, 2));
      setJsonWin(JSON.stringify(d.win_conditions, null, 2));
      setJsonScene(JSON.stringify(d.scene_config, null, 2));
      loadPlayerCharacter(d.scene_config || {});
      setRuleKeywords(d.dispatch_rules.map((r) => r.trigger_keywords.join(", ")));
      setRuleChars(d.dispatch_rules.map((r) => r.priority_character_ids.join(", ")));
      return;
    }
    api.getScenario(parseInt(id!)).then(applyScenario);
  }, [id, isNew]);

  const exportJson = async () => {
    if (isNew || !id) return;
    try {
      const data = await api.exportScenario(parseInt(id));
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${String(data.slug || "scenario")}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setMsg(String(err));
      setMsgOk(false);
    }
  };

  const importFromJson = async () => {
    setImporting(true);
    setMsg("");
    try {
      const parsed = JSON.parse(importJson) as Record<string, unknown>;
      if (!isNew && id && !window.confirm(t.scenarioEditor.importConfirmReplace)) {
        setImporting(false);
        return;
      }
      if (isNew) {
        const created = await api.importScenarioNew(parsed);
        navigate(`/scenarios/${created.id}`);
        return;
      }
      const updated = await api.importScenarioReplace(parseInt(id!), parsed);
      applyScenario(updated);
      setImportJson("");
      setMsg(`${t.scenarioEditor.importJson} — ${t.common.saved}`);
      setMsgOk(true);
    } catch (err) {
      setMsg(String(err));
      setMsgOk(false);
    } finally {
      setImporting(false);
    }
  };

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

  const updateRule = (idx: number, patch: Partial<ScenarioDispatchRule>) => {
    const rules = [...form.dispatch_rules];
    rules[idx] = { ...rules[idx], ...patch };
    setForm({ ...form, dispatch_rules: rules });
  };

  const addRule = () => {
    setForm({ ...form, dispatch_rules: [...form.dispatch_rules, emptyDispatchRule()] });
    setRuleKeywords([...ruleKeywords, ""]);
    setRuleChars([...ruleChars, ""]);
  };

  const removeRule = (idx: number) => {
    setForm({ ...form, dispatch_rules: form.dispatch_rules.filter((_, i) => i !== idx) });
    setRuleKeywords(ruleKeywords.filter((_, i) => i !== idx));
    setRuleChars(ruleChars.filter((_, i) => i !== idx));
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMsg("");
    try {
      const dispatch_rules = form.dispatch_rules.map((rule, idx) => ({
        ...rule,
        trigger_keywords: (ruleKeywords[idx] || "")
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        priority_character_ids: (ruleChars[idx] || "")
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      }));
      const sceneConfig = JSON.parse(jsonScene) as Record<string, unknown>;
      sceneConfig.player_character = playerCharacter;
      const payload: ScenarioInput = {
        ...form,
        phases: JSON.parse(jsonPhases),
        win_conditions: JSON.parse(jsonWin),
        scene_config: sceneConfig,
        dispatch_rules,
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

      <section className="form-panel wide" style={{ marginBottom: "1rem" }}>
        <h2>{t.scenarioEditor.jsonSection}</h2>
        <p className="muted">{t.scenarioEditor.jsonHint}</p>
        <div className="row" style={{ alignItems: "flex-start", gap: "0.75rem" }}>
          {!isNew && (
            <button type="button" className="btn" onClick={exportJson}>{t.scenarioEditor.exportJson}</button>
          )}
          <label style={{ flex: 1 }}>
            <textarea
              className="mono"
              rows={6}
              value={importJson}
              onChange={(e) => setImportJson(e.target.value)}
              placeholder={t.scenarioEditor.importPlaceholder}
            />
          </label>
        </div>
        <button
          type="button"
          className="btn primary"
          disabled={importing || !importJson.trim()}
          onClick={importFromJson}
        >
          {importing ? t.common.saving : t.scenarioEditor.importJson}
        </button>
      </section>

      <form onSubmit={submit} className="form-panel wide">
        <section>
          <h2>{t.scenarioEditor.basicInfo}</h2>
          <div className="row">
            <label>{t.scenarioEditor.slug}<input required value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} /></label>
            <label>{t.scenarioEditor.title}<input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
          </div>
          <label>{t.scenarioEditor.description}<textarea value={form.description || ""} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} /></label>
          <label>{t.scenarioEditor.playerSideGoal}<textarea required value={form.player_side_goal} onChange={(e) => setForm({ ...form, player_side_goal: e.target.value })} rows={3} /></label>
          <label>{t.scenarioEditor.opponentSideGoal}<textarea value={form.opponent_side_goal} onChange={(e) => setForm({ ...form, opponent_side_goal: e.target.value })} rows={3} /></label>
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
          <h2>{t.scenarioEditor.playerCharacterSection}</h2>
          <p className="muted">{t.scenarioEditor.playerCharacterHint}</p>
          <div className="row">
            <label>{t.scenarioEditor.characterName}<input required value={playerCharacter.character_name} onChange={(e) => setPlayerCharacter({ ...playerCharacter, character_name: e.target.value })} /></label>
            <label>{t.scenarioEditor.jobTitle}<input required value={playerCharacter.job_title} onChange={(e) => setPlayerCharacter({ ...playerCharacter, job_title: e.target.value })} /></label>
          </div>
          <AvatarUpload
            manifest={playerCharacter.avatar_manifest}
            onChange={(avatar_manifest) => setPlayerCharacter({ ...playerCharacter, avatar_manifest })}
          />
          <label>{t.scenarioEditor.avatarManifestJson}<textarea value={JSON.stringify(playerCharacter.avatar_manifest || {}, null, 2)} onChange={(e) => { try { setPlayerCharacter({ ...playerCharacter, avatar_manifest: JSON.parse(e.target.value) }); } catch { /* ignore */ } }} rows={4} className="mono" /></label>
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
                <label>{t.scenarioEditor.characterName}<input required value={c.character_name} onChange={(e) => updateChar(idx, { character_name: e.target.value })} /></label>
                <label>{t.scenarioEditor.jobTitle}<input required value={c.job_title} onChange={(e) => updateChar(idx, { job_title: e.target.value })} /></label>
                <label>
                  {t.scenarioEditor.side}
                  <select value={c.side || "opponent"} onChange={(e) => updateChar(idx, { side: e.target.value as Character["side"] })}>
                    <option value="opponent">{t.scenarioEditor.sideOpponent}</option>
                    <option value="player_ally">{t.scenarioEditor.sidePlayerAlly}</option>
                  </select>
                </label>
                <label>{t.scenarioEditor.spawnPoint}<input value={c.spawn_point || ""} onChange={(e) => updateChar(idx, { spawn_point: e.target.value })} /></label>
              </div>
              <label>{t.scenarioEditor.persona}<textarea required value={c.persona} onChange={(e) => updateChar(idx, { persona: e.target.value })} rows={2} /></label>
              <label>{t.scenarioEditor.responsibility}<textarea required value={c.responsibility} onChange={(e) => updateChar(idx, { responsibility: e.target.value })} rows={2} /></label>
              <div className="row">
                <label>{t.scenarioEditor.tendencyJson}<textarea value={JSON.stringify(c.tendency)} onChange={(e) => updateChar(idx, { tendency: JSON.parse(e.target.value) })} rows={2} className="mono" /></label>
                <label>{t.scenarioEditor.privateStateJson}<textarea value={JSON.stringify(c.private_state)} onChange={(e) => updateChar(idx, { private_state: JSON.parse(e.target.value) })} rows={2} className="mono" /></label>
              </div>
              <label>{t.scenarioEditor.avatarManifestJson}<textarea value={JSON.stringify(c.avatar_manifest || {})} onChange={(e) => { try { updateChar(idx, { avatar_manifest: JSON.parse(e.target.value) }); } catch { /* ignore */ } }} rows={2} className="mono" /></label>
              <AvatarUpload
                manifest={c.avatar_manifest || {}}
                onChange={(avatar_manifest) => updateChar(idx, { avatar_manifest })}
              />
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

        <section>
          <div className="section-header">
            <h2>{t.scenarioEditor.dispatchRules}</h2>
            <button type="button" className="btn" onClick={addRule}>{t.scenarioEditor.addDispatchRule}</button>
          </div>
          <p className="muted">{t.scenarioEditor.dispatchHint}</p>
          {form.dispatch_rules.map((rule, idx) => (
            <div key={idx} className="char-card">
              <div className="char-header">
                <strong>{t.scenarioEditor.dispatchRuleN.replace("{n}", String(idx + 1))}</strong>
                {form.dispatch_rules.length > 1 && (
                  <button type="button" className="btn small danger" onClick={() => removeRule(idx)}>{t.common.delete}</button>
                )}
              </div>
              <div className="row">
                <label>{t.scenarioEditor.ruleName}<input required value={rule.name} onChange={(e) => updateRule(idx, { name: e.target.value })} /></label>
                <label>{t.scenarioEditor.minSpeakers}<input type="number" min={0} value={rule.min_speakers} onChange={(e) => updateRule(idx, { min_speakers: parseInt(e.target.value) || 0 })} /></label>
                <label>{t.scenarioEditor.maxSpeakers}<input type="number" min={1} value={rule.max_speakers} onChange={(e) => updateRule(idx, { max_speakers: parseInt(e.target.value) || 1 })} /></label>
                <label className="checkbox">
                  <input type="checkbox" checked={rule.is_active} onChange={(e) => updateRule(idx, { is_active: e.target.checked })} />
                  {t.scenarioEditor.ruleActive}
                </label>
              </div>
              <label>{t.scenarioEditor.ruleDescription}<textarea value={rule.description || ""} onChange={(e) => updateRule(idx, { description: e.target.value })} rows={2} /></label>
              <label>{t.scenarioEditor.triggerKeywords}<input value={ruleKeywords[idx] || ""} onChange={(e) => { const next = [...ruleKeywords]; next[idx] = e.target.value; setRuleKeywords(next); }} placeholder={t.scenarioEditor.keywordsPlaceholder} /></label>
              <label>{t.scenarioEditor.priorityCharacters}<input value={ruleChars[idx] || ""} onChange={(e) => { const next = [...ruleChars]; next[idx] = e.target.value; setRuleChars(next); }} placeholder={t.scenarioEditor.charsPlaceholder} /></label>
            </div>
          ))}
        </section>

        <button type="submit" className="btn primary" disabled={saving}>{saving ? t.common.saving : t.scenarioEditor.saveScenario}</button>
        {msg && <p className={msgOk ? "success" : "error"}>{msg}</p>}
      </form>
    </div>
  );
}
