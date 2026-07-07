import { FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { useLocale } from "../i18n";

type LlmRoleConfig = {
  provider?: string;
  model?: string;
  temperature?: number;
  max_tokens?: number;
};

type AgentConfig = {
  max_speakers_per_turn?: number;
  retrieval_k?: number;
  reflection_importance_threshold?: number;
  working_message_limit?: number;
  retrieval_alpha?: number;
  retrieval_beta?: number;
  retrieval_gamma?: number;
};

type OrchestrationConfig = {
  llm_roles?: Record<string, LlmRoleConfig>;
  agent?: AgentConfig;
};

const LLM_ROLE_IDS = ["npc_default", "decision", "reflection"] as const;

export default function OrchestrationSettings() {
  const { t } = useLocale();
  const { id } = useParams();
  const scenarioId = parseInt(id || "0");
  const [scenarioTitle, setScenarioTitle] = useState("");
  const [config, setConfig] = useState<OrchestrationConfig | null>(null);
  const [catalogs, setCatalogs] = useState<Record<string, { id: string; name: string }[]>>({});
  const [globalLlm, setGlobalLlm] = useState<{ provider?: string; model?: string }>({});
  const [msg, setMsg] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!scenarioId) return;
    Promise.all([api.getScenario(scenarioId), api.getOrchestration(scenarioId), api.getProviders(), api.getLLMStatus()])
      .then(([scenario, orch, prov, status]) => {
        setScenarioTitle(scenario.title);
        setConfig(orch.orchestration_config as OrchestrationConfig);
        setCatalogs(prov.catalogs || {});
        setGlobalLlm({
          provider: String(status.provider || ""),
          model: String(status.model || ""),
        });
      })
      .catch((e) => setMsg(String(e)));
  }, [scenarioId]);

  const updateLlmRole = (roleId: string, patch: Partial<LlmRoleConfig>, removeKeys: string[] = []) => {
    if (!config) return;
    const current = { ...(config.llm_roles?.[roleId] || {}) };
    Object.assign(current, patch);
    for (const key of removeKeys) {
      delete current[key as keyof LlmRoleConfig];
    }
    setConfig({
      ...config,
      llm_roles: { ...config.llm_roles, [roleId]: current },
    });
  };

  const sanitizeForSave = (cfg: OrchestrationConfig): OrchestrationConfig => {
    const llm_roles: Record<string, LlmRoleConfig> = {};
    for (const roleId of LLM_ROLE_IDS) {
      const r = cfg.llm_roles?.[roleId] || {};
      const next: LlmRoleConfig = {};
      if (r.provider?.trim()) next.provider = r.provider.trim();
      if (r.model?.trim()) next.model = r.model.trim();
      if (r.temperature != null) next.temperature = r.temperature;
      if (r.max_tokens != null) next.max_tokens = r.max_tokens;
      llm_roles[roleId] = next;
    }
    return { ...cfg, llm_roles };
  };

  const updateAgent = (patch: Partial<AgentConfig>) => {
    if (!config) return;
    setConfig({ ...config, agent: { ...config.agent, ...patch } });
  };

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (!scenarioId || !config) return;
    setSaving(true);
    setMsg("");
    try {
      await api.updateOrchestration(scenarioId, sanitizeForSave(config));
      setMsg(t.orchestration.configSaved);
    } catch (err) {
      setMsg(String(err));
    } finally {
      setSaving(false);
    }
  };

  if (!config) return <div>{msg || t.common.loading}</div>;

  const agent = config.agent || {};

  return (
    <div>
      <div className="page-header">
        <h1>{t.orchestration.title.replace("{title}", scenarioTitle)}</h1>
        <Link to={`/scenarios/${scenarioId}`} className="btn small">{t.orchestration.backToScenario}</Link>
      </div>

      <p className="muted">{t.orchestration.subtitle}</p>

      {msg && <div className="alert">{msg}</div>}

      <form onSubmit={save} className="form-panel wide">
        <div className="card">
          <h3>{t.orchestration.modelBinding}</h3>
          {LLM_ROLE_IDS.map((roleId) => {
            const r = config.llm_roles?.[roleId] || {};
            const effectiveProvider = r.provider?.trim() || globalLlm.provider || "ollama";
            const provKey = effectiveProvider === "ollama_cloud" ? "ollama" : effectiveProvider;
            const models = catalogs[provKey] || [];
            const roleLabel = t.orchestration.roles[roleId as keyof typeof t.orchestration.roles];
            const globalLabel = globalLlm.provider && globalLlm.model
              ? `${globalLlm.provider}/${globalLlm.model}`
              : t.orchestration.followGlobal;
            return (
              <div key={roleId} style={{ marginBottom: "1rem", borderTop: "1px solid #30363d", paddingTop: "0.75rem" }}>
                <strong>{roleLabel}</strong>
                <div className="row" style={{ marginTop: "0.5rem" }}>
                  <label>
                    Provider
                    <select
                      value={r.provider || ""}
                      onChange={(e) => {
                        const v = e.target.value;
                        if (!v) {
                          updateLlmRole(roleId, {}, ["provider", "model"]);
                        } else {
                          updateLlmRole(roleId, { provider: v }, ["model"]);
                        }
                      }}
                    >
                      <option value="">{globalLabel}</option>
                      <option value="siliconflow">siliconflow</option>
                      <option value="ollama">ollama</option>
                    </select>
                  </label>
                  <label>
                    Model
                    <select
                      value={r.model || ""}
                      disabled={!r.provider}
                      onChange={(e) => {
                        const v = e.target.value;
                        if (!v) updateLlmRole(roleId, {}, ["model"]);
                        else updateLlmRole(roleId, { model: v });
                      }}
                    >
                      <option value="">{t.orchestration.followGlobal}</option>
                      {models.map((m) => (
                        <option key={m.id} value={m.id}>{m.name || m.id}</option>
                      ))}
                    </select>
                  </label>
                </div>
              </div>
            );
          })}
        </div>

        <div className="card" style={{ marginTop: "1rem" }}>
          <h3>{t.orchestration.agentParams}</h3>
          <div className="row">
            <label>
              {t.orchestration.maxSpeakers}
              <input
                type="number"
                min={0}
                max={5}
                value={agent.max_speakers_per_turn ?? 2}
                onChange={(e) => updateAgent({ max_speakers_per_turn: parseInt(e.target.value) || 2 })}
              />
            </label>
            <label>
              {t.orchestration.retrievalK}
              <input
                type="number"
                min={3}
                max={30}
                value={agent.retrieval_k ?? 10}
                onChange={(e) => updateAgent({ retrieval_k: parseInt(e.target.value) || 10 })}
              />
            </label>
            <label>
              {t.orchestration.reflectionThreshold}
              <input
                type="number"
                min={5}
                value={agent.reflection_importance_threshold ?? 18}
                onChange={(e) =>
                  updateAgent({ reflection_importance_threshold: parseFloat(e.target.value) || 18 })
                }
              />
            </label>
            <label>
              {t.orchestration.workingLimit}
              <input
                type="number"
                min={10}
                max={80}
                value={agent.working_message_limit ?? 30}
                onChange={(e) => updateAgent({ working_message_limit: parseInt(e.target.value) || 30 })}
              />
            </label>
          </div>
        </div>

        <button type="submit" className="btn primary" disabled={saving} style={{ marginTop: "1rem" }}>
          {saving ? t.common.saving : t.common.save}
        </button>
      </form>
    </div>
  );
}
