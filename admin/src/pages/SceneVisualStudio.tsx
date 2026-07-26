import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, Character, Scenario } from "../api";
import PlotCastBindingPanel from "../components/PlotCastBinding";
import SceneGraphEditor from "../components/SceneGraphEditor";
import { useLocale } from "../i18n";
import {
  createEmptySceneGraph,
  resolveSceneGraph,
  sanitizePlotCastBinding,
  sanitizeSceneGraph,
  type PlotCastBinding,
  type SceneGraph,
} from "../sceneGraph";
import { pageHostname, serviceUrl } from "../serviceUrls";

const VISUAL_SCENE_KEYS = ["environment", "lighting", "camera", "spawn"] as const;

function pickVisualSceneConfig(sceneConfig: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const key of VISUAL_SCENE_KEYS) {
    if (key in sceneConfig) out[key] = sceneConfig[key];
  }
  return out;
}

function resolveInitialGraph(scene: Record<string, unknown>): SceneGraph {
  const existing = resolveSceneGraph(scene);
  if (existing) return existing;
  return createEmptySceneGraph();
}

export default function SceneVisualStudio() {
  const { t } = useLocale();
  const { id } = useParams();
  const scenarioId = parseInt(id || "0", 10);

  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [jsonVisual, setJsonVisual] = useState("{}");
  const [sceneGraph, setSceneGraph] = useState<SceneGraph>(() => createEmptySceneGraph());
  const [plotBindings, setPlotBindings] = useState<PlotCastBinding[]>([]);
  const [graphJson, setGraphJson] = useState("{}");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [msgOk, setMsgOk] = useState(false);
  const [clientUrl, setClientUrl] = useState("");
  const [importJson, setImportJson] = useState("");
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    api.getPlatformConfig()
      .then((c) => setClientUrl(serviceUrl(c.ports.client, pageHostname(c.hosts.public_host))))
      .catch(() => setClientUrl(serviceUrl(5183)));
  }, []);

  const playerCharacter = useMemo(() => {
    const raw = scenario?.scene_config?.player_character;
    return raw && typeof raw === "object" ? (raw as Record<string, unknown>) : null;
  }, [scenario]);

  const reloadScenario = (s: Scenario) => {
    setScenario(s);
    setCharacters(s.characters.length ? [...s.characters] : []);
    const scene = (s.scene_config || {}) as Record<string, unknown>;
    setJsonVisual(JSON.stringify(pickVisualSceneConfig(scene), null, 2));
    const graph = resolveInitialGraph(scene);
    setSceneGraph(graph);
    setGraphJson(JSON.stringify(graph, null, 2));
    setPlotBindings(sanitizePlotCastBinding(scene.plot_cast_binding));
  };

  useEffect(() => {
    if (!scenarioId) return;
    api.getScenario(scenarioId).then(reloadScenario);
  }, [scenarioId]);

  useEffect(() => {
    setGraphJson(JSON.stringify(sceneGraph, null, 2));
  }, [sceneGraph]);

  const exportVisualJson = async () => {
    try {
      const data = await api.exportSceneVisual(scenarioId);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${scenario?.slug || "scenario"}-scene-visual.json`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setMsg(String(err));
      setMsgOk(false);
    }
  };

  const importVisualJson = async () => {
    setImporting(true);
    setMsg("");
    try {
      if (!window.confirm(t.sceneVisual.importConfirmReplace)) {
        setImporting(false);
        return;
      }
      const parsed = JSON.parse(importJson) as Record<string, unknown>;
      const updated = await api.importSceneVisual(scenarioId, parsed);
      reloadScenario(updated);
      setImportJson("");
      setMsg(t.sceneVisual.imported);
      setMsgOk(true);
    } catch (err) {
      setMsg(String(err));
      setMsgOk(false);
    } finally {
      setImporting(false);
    }
  };

  const applyGraphJson = () => {
    try {
      const parsed = JSON.parse(graphJson);
      setSceneGraph(sanitizeSceneGraph(parsed));
      setMsg(t.sceneVisual.graphJsonApplied);
      setMsgOk(true);
    } catch (err) {
      setMsg(String(err));
      setMsgOk(false);
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!scenario) return;
    setSaving(true);
    setMsg("");
    try {
      const visual = JSON.parse(jsonVisual) as Record<string, unknown>;
      const prevScene = { ...(scenario.scene_config || {}) };

      const payload = {
        ...scenario,
        scene_config: {
          ...prevScene,
          ...visual,
          scene_graph: sceneGraph,
          plot_cast_binding: plotBindings,
        },
        characters: [...characters],
      };

      const updated = await api.updateScenario(scenarioId, payload);
      reloadScenario(updated);
      setMsg(t.sceneVisual.saved);
      setMsgOk(true);
    } catch (err) {
      setMsg(String(err));
      setMsgOk(false);
    } finally {
      setSaving(false);
    }
  };

  if (!scenario) {
    return <p className="muted">{t.common.loading}</p>;
  }

  return (
    <div>
      <h1>{t.sceneVisual.title}</h1>
      <p className="muted">
        <Link to={`/scenarios/${scenarioId}`}>{t.sceneVisual.backToScenario}</Link>
        {" · "}
        <Link to={`/scenarios/${scenarioId}/orchestration`}>{t.scenarioEditor.orchestrationLink}</Link>
        {" · "}
        {clientUrl ? (
          <a href={`${clientUrl}/play/${scenarioId}`} target="_blank" rel="noreferrer">
            {t.sceneVisual.openGamePreview}
          </a>
        ) : (
          <span>{t.sceneVisual.openGamePreview}</span>
        )}
      </p>

      <p className="muted">{t.sceneVisual.stageSeparationHint}</p>

      <section className="form-panel wide" style={{ marginBottom: "1rem" }}>
        <h2>{t.sceneVisual.jsonSection}</h2>
        <p className="muted">{t.sceneVisual.jsonHint}</p>
        <div className="row" style={{ alignItems: "flex-start", gap: "0.75rem" }}>
          <button type="button" className="btn" onClick={exportVisualJson}>
            {t.sceneVisual.exportJson}
          </button>
          <label style={{ flex: 1 }}>
            <textarea
              className="mono"
              rows={6}
              value={importJson}
              onChange={(e) => setImportJson(e.target.value)}
              placeholder={t.sceneVisual.importPlaceholder}
            />
          </label>
        </div>
        <button
          type="button"
          className="btn primary"
          disabled={importing || !importJson.trim()}
          onClick={importVisualJson}
        >
          {importing ? t.common.saving : t.sceneVisual.importJson}
        </button>
      </section>

      <form onSubmit={submit} className="form-panel wide">
        <section>
          <h2>{t.sceneVisual.environmentSection}</h2>
          <p className="muted">{t.sceneVisual.environmentHint}</p>
          <label>
            {t.sceneVisual.visualConfigJson}
            <textarea className="mono" rows={4} value={jsonVisual} onChange={(e) => setJsonVisual(e.target.value)} />
          </label>
        </section>

        <SceneGraphEditor
          graph={sceneGraph}
          onChange={setSceneGraph}
          plotBindings={plotBindings}
          onPlotBindingsChange={setPlotBindings}
          characters={characters}
          playerCharacter={playerCharacter}
        />

        <section>
          <h3>{t.sceneVisual.graphJsonSection}</h3>
          <p className="muted">{t.sceneVisual.graphJsonHint}</p>
          <textarea className="mono" rows={10} value={graphJson} onChange={(e) => setGraphJson(e.target.value)} />
          <button type="button" className="btn" onClick={applyGraphJson}>
            {t.sceneVisual.applyGraphJson}
          </button>
        </section>

        <PlotCastBindingPanel
          graph={sceneGraph}
          characters={characters}
          playerCharacter={playerCharacter}
          bindings={plotBindings}
          onChange={setPlotBindings}
        />

        <button type="submit" className="btn primary" disabled={saving}>
          {saving ? t.common.saving : t.sceneVisual.saveVisual}
        </button>
        {msg && <p className={msgOk ? "success" : "error"}>{msg}</p>}
      </form>
    </div>
  );
}
