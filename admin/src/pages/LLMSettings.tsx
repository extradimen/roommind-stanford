import { useEffect, useState } from "react";
import { api, LLMConfig, LLMKeysStatus, LLMModelCatalogItem } from "../api";
import { useLocale } from "../i18n";

export default function LLMSettings() {
  const { t } = useLocale();
  const [config, setConfig] = useState<LLMConfig | null>(null);
  const [keys, setKeys] = useState<LLMKeysStatus | null>(null);
  const [providers, setProviders] = useState<Record<string, string[]>>({});
  const [catalogs, setCatalogs] = useState<Record<string, LLMModelCatalogItem[]>>({});
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [sfKeyInput, setSfKeyInput] = useState("");
  const [ollamaKeyInput, setOllamaKeyInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [savingKeys, setSavingKeys] = useState(false);
  const [msg, setMsg] = useState("");
  const [msgOk, setMsgOk] = useState(false);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogMeta, setCatalogMeta] = useState<Record<string, unknown> | null>(null);

  const applyProviders = (
    prov: {
      providers: Record<string, string[]>;
      catalogs: Record<string, LLMModelCatalogItem[]>;
      meta?: Record<string, unknown>;
    },
    providerKey: string,
    currentModel?: string,
  ) => {
    setProviders(prov.providers);
    const nextCatalogs = { ...prov.catalogs };
    if (currentModel && providerKey === "ollama") {
      const list = nextCatalogs.ollama || [];
      if (!list.some((m) => m.id === currentModel)) {
        nextCatalogs.ollama = [{ id: currentModel, name: currentModel }, ...list];
      }
    }
    setCatalogs(nextCatalogs);
    if (prov.meta?.ollama) setCatalogMeta(prov.meta.ollama as Record<string, unknown>);
  };

  const refreshOllamaCatalog = async (currentModel?: string, providerKey = "ollama") => {
    if (catalogLoading) return;
    setCatalogLoading(true);
    setMsg("");
    try {
      const prov = await api.getProviders();
      applyProviders(prov, providerKey, currentModel ?? config?.model);
      const meta = prov.meta?.ollama as Record<string, unknown> | undefined;
      if (meta?.error) {
        setMsgOk(false);
        setMsg(`${t.llm.catalogFetchFailed}: ${String(meta.error)}`);
      }
    } catch (e) {
      setMsg(String(e));
      setMsgOk(false);
    } finally {
      setCatalogLoading(false);
    }
  };

  const refreshStatus = async () => {
    const st = await api.getLLMStatus();
    setStatus(st);
    const k = await api.getLLMKeys();
    setKeys(k);
  };

  useEffect(() => {
    Promise.all([api.getLLMConfig(), api.getProviders(), api.getLLMStatus(), api.getLLMKeys()])
      .then(([cfg, prov, st, k]) => {
        if (cfg && cfg.provider === "ollama_cloud") {
          cfg = { ...cfg, provider: "ollama" };
        }
        setConfig(cfg);
        const pk = cfg?.provider === "ollama_cloud" ? "ollama" : (cfg?.provider || "siliconflow");
        applyProviders(prov, pk, cfg?.model);
        setStatus(st);
        setKeys(k);
        if (pk === "ollama") {
          void refreshOllamaCatalog(cfg?.model, pk);
        }
      })
      .catch((e) => {
        setMsg(String(e));
        setMsgOk(false);
      });
  }, []);

  const save = async () => {
    if (!config) return;
    setSaving(true);
    setMsg("");
    try {
      const provider = config.provider === "ollama_cloud" ? "ollama" : config.provider;
      const updated = await api.updateLLMConfig(config.id, {
        provider,
        model: config.model,
        base_url: config.base_url,
        temperature: config.temperature,
        max_tokens: config.max_tokens,
      });
      setConfig(updated);
      setMsg(t.llm.configSaved);
      setMsgOk(true);
      await refreshStatus();
    } catch (e) {
      setMsg(String(e));
      setMsgOk(false);
    } finally {
      setSaving(false);
    }
  };

  const saveKeys = async () => {
    setSavingKeys(true);
    setMsg("");
    try {
      const payload: { siliconflow_api_key?: string; ollama_api_key?: string } = {};
      if (sfKeyInput.trim()) payload.siliconflow_api_key = sfKeyInput.trim();
      if (ollamaKeyInput.trim()) payload.ollama_api_key = ollamaKeyInput.trim();
      if (!payload.siliconflow_api_key && !payload.ollama_api_key) {
        setMsg(t.llm.needOneKey);
        setMsgOk(false);
        return;
      }
      const updated = await api.updateLLMKeys(payload);
      setKeys(updated);
      setSfKeyInput("");
      setOllamaKeyInput("");
      setMsg(t.llm.keySaved);
      setMsgOk(true);
      await refreshStatus();
      if (config?.provider === "ollama" || config?.provider === "ollama_cloud") {
        await refreshOllamaCatalog(config?.model, "ollama");
      }
    } catch (e) {
      setMsg(String(e));
      setMsgOk(false);
    } finally {
      setSavingKeys(false);
    }
  };

  const clearKey = async (provider: "siliconflow" | "ollama") => {
    const confirmMsg = provider === "siliconflow" ? t.llm.confirmClearSf : t.llm.confirmClearOllama;
    if (!window.confirm(confirmMsg)) return;
    setSavingKeys(true);
    setMsg("");
    try {
      const payload = provider === "siliconflow"
        ? { siliconflow_api_key: "" }
        : { ollama_api_key: "" };
      const updated = await api.updateLLMKeys(payload);
      setKeys(updated);
      if (provider === "siliconflow") setSfKeyInput("");
      else setOllamaKeyInput("");
      setMsg(t.llm.keyCleared);
      setMsgOk(true);
      await refreshStatus();
    } catch (e) {
      setMsg(String(e));
      setMsgOk(false);
    } finally {
      setSavingKeys(false);
    }
  };

  if (!config) return <div>{t.common.loading}</div>;

  const provKey = config.provider === "ollama_cloud" ? "ollama" : config.provider;
  const models = providers[provKey] || providers[config.provider] || [];
  const modelCatalog = catalogs[provKey] || models.map((id) => ({ id, name: id }));

  const formatModelLabel = (m: LLMModelCatalogItem) => {
    const kindLabel = m.kind === "reasoning" ? t.llm.kindReasoning : t.llm.kindChat;
    const star = m.recommended ? "★ " : "";
    return `${star}[${kindLabel}] ${m.name} — ${m.id}`;
  };

  const selectedModelMeta = modelCatalog.find((m) => m.id === config.model);

  return (
    <div>
      <h1>{t.llm.title}</h1>
      <p className="muted">{t.llm.subtitle}</p>

      {status && (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h3>{t.llm.runtimeStatus}</h3>
          <ul className="port-list">
            <li>{t.llm.activeProvider}: <code>{String(status.provider)}</code></li>
            <li>{t.llm.activeModel}: <code>{String(status.model)}</code></li>
            <li>{t.llm.sfKey}: {status.siliconflow_key_configured ? "✓" : "✗"}
              {keys?.siliconflow.configured && keys.siliconflow.masked ? ` (${keys.siliconflow.masked})` : ""}
            </li>
            <li>{t.llm.ollamaKey}: {status.ollama_key_configured ? "✓" : "✗"}
              {keys?.ollama.configured && keys.ollama.masked ? ` (${keys.ollama.masked})` : ""}
            </li>
            {Array.isArray(status.env_overrides) && status.env_overrides.length > 0 && (
              <li className="hint">{String(status.env_overrides[0])}</li>
            )}
          </ul>
        </div>
      )}

      <div className="form-panel" style={{ marginBottom: "1.5rem" }}>
        <h2 style={{ marginTop: 0, fontSize: "1.1rem" }}>{t.llm.apiKeySection}</h2>
        <p className="hint">{t.llm.apiKeyHint}</p>

        <label>
          {t.llm.sfKeyLabel}
          <input
            type="password"
            autoComplete="off"
            value={sfKeyInput}
            onChange={(e) => setSfKeyInput(e.target.value)}
            placeholder={keys?.siliconflow.configured
              ? t.llm.sfKeyConfigured.replace("{masked}", keys.siliconflow.masked || "")
              : t.llm.sfKeyPlaceholder}
          />
        </label>
        {keys?.siliconflow.configured && (
          <button type="button" className="btn small danger" style={{ marginBottom: "0.75rem" }}
            disabled={savingKeys} onClick={() => clearKey("siliconflow")}>
            {t.llm.clearSfKey}
          </button>
        )}

        <label>
          {t.llm.ollamaKeyLabel}
          <input
            type="password"
            autoComplete="off"
            value={ollamaKeyInput}
            onChange={(e) => setOllamaKeyInput(e.target.value)}
            placeholder={keys?.ollama.configured
              ? t.llm.sfKeyConfigured.replace("{masked}", keys.ollama.masked || "")
              : t.llm.ollamaKeyPlaceholder}
          />
        </label>
        {keys?.ollama.configured && (
          <button type="button" className="btn small danger" style={{ marginBottom: "0.75rem" }}
            disabled={savingKeys} onClick={() => clearKey("ollama")}>
            {t.llm.clearOllamaKey}
          </button>
        )}

        <button className="btn primary" type="button" onClick={saveKeys} disabled={savingKeys}>
          {savingKeys ? t.common.saving : t.llm.saveApiKey}
        </button>
      </div>

      <div className="form-panel">
        <h2 style={{ marginTop: 0, fontSize: "1.1rem" }}>{t.llm.modelParams}</h2>

        <div className="card" style={{ marginBottom: "1rem", padding: "0.75rem 1rem" }}>
          <strong>{t.llm.modelKindGuideTitle}</strong>
          <p className="hint" style={{ margin: "0.5rem 0 0" }}>{t.llm.modelKindGuide}</p>
          <p className="hint" style={{ margin: "0.35rem 0 0" }}>{t.llm.dropdownLegend}</p>
        </div>

        <label>
          {t.llm.provider}
          <select
            value={provKey}
            onChange={(e) => {
              const p = e.target.value;
              const firstModel = catalogs[p]?.[0]?.id || providers[p]?.[0] || "";
              setConfig({ ...config, provider: p, model: firstModel });
              if (p === "ollama") void refreshOllamaCatalog(firstModel, p);
            }}
          >
            <option value="siliconflow">SiliconFlow</option>
            <option value="ollama">Ollama Cloud</option>
          </select>
        </label>

        <label>
          {t.llm.model}
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
            <select
              value={config.model}
              onMouseDown={() => {
                if (provKey === "ollama") void refreshOllamaCatalog(config.model, provKey);
              }}
              onChange={(e) => setConfig({ ...config, model: e.target.value })}
              style={{ flex: "1 1 16rem" }}
            >
              {modelCatalog.map((m) => (
                <option key={m.id} value={m.id}>
                  {formatModelLabel(m)}
                </option>
              ))}
            </select>
            {provKey === "ollama" && (
              <button
                type="button"
                className="btn small"
                disabled={catalogLoading}
                onClick={() => void refreshOllamaCatalog(config.model, provKey)}
              >
                {catalogLoading ? t.llm.catalogLoading : t.llm.refreshCatalog}
              </button>
            )}
          </div>
          {provKey === "ollama" && catalogMeta?.count ? (
            <p className="hint">
              {t.llm.catalogCount.replace("{count}", String(catalogMeta.count))}
              {catalogMeta.fetched_at ? ` · ${String(catalogMeta.fetched_at).slice(0, 19)}Z` : ""}
            </p>
          ) : null}
          {provKey === "ollama" && catalogMeta?.error ? (
            <p className="error">{t.llm.catalogFetchFailed}: {String(catalogMeta.error)}</p>
          ) : null}
          {selectedModelMeta && (
            <p className="hint">
              {selectedModelMeta.kind === "reasoning" ? t.llm.selectedReasoningHint : t.llm.selectedChatHint}
            </p>
          )}
        </label>

        <div className="row">
          <label>
            {t.llm.temperature}
            <input
              type="number"
              step="0.1"
              min="0"
              max="2"
              value={config.temperature}
              onChange={(e) => setConfig({ ...config, temperature: parseFloat(e.target.value) })}
            />
          </label>
          <label>
            {t.llm.maxTokens}
            <input
              type="number"
              step="256"
              min="256"
              value={config.max_tokens}
              onChange={(e) => setConfig({ ...config, max_tokens: parseInt(e.target.value) })}
            />
          </label>
        </div>

        <button className="btn primary" onClick={save} disabled={saving}>
          {saving ? t.common.saving : t.llm.saveModel}
        </button>
        {msg && <p className={msgOk ? "success" : "error"}>{msg}</p>}
      </div>
    </div>
  );
}
