import { useMemo, useState } from "react";
import { resolveNpcFullName, resolveNpcLabel } from "../characterNames";
import { useLocale } from "../i18n";
import { localizeMemoryContent } from "../memoryDisplay";
import type { AgentMemoriesData, AgentMemoryNode } from "./AgentMemoryPanel";

type FilterType = "all" | "observation" | "reflection" | "plan" | "action";

type Props = {
  data: AgentMemoriesData | null;
  loading?: boolean;
  turnLoading?: boolean;
  error?: string;
  characterOrder?: string[];
  characterNames?: Record<string, string>;
  onRefresh?: () => void;
  onOpenBrowser?: () => void;
};

function countByType(nodes: AgentMemoryNode[], type: string) {
  return nodes.filter((n) => n.node_type === type).length;
}

export default function AgentMemoryStrip({
  data,
  loading,
  turnLoading = false,
  error,
  characterOrder = [],
  characterNames = {},
  onRefresh,
  onOpenBrowser,
}: Props) {
  const { t, locale } = useLocale();
  const [filter, setFilter] = useState<FilterType>("all");

  const nodeLabels: Record<string, string> = {
    observation: t.agent.filters.observation,
    reflection: t.agent.filters.reflection,
    plan: t.agent.filters.plan,
    action: t.agent.filters.action,
  };

  const actionLabel = (action: unknown) => {
    const key = String(action || "") as keyof typeof t.agent.actions;
    return t.agent.actions[key] || String(action || "—");
  };

  const sourceLabel = (meta?: Record<string, unknown>) => {
    const src = meta?.source;
    if (typeof src !== "string") return null;
    const key = src as keyof typeof t.agent.sources;
    return t.agent.sources[key] || src;
  };

  const agentIds = useMemo(() => {
    if (!data) return characterOrder;
    const ids = new Set([
      ...characterOrder,
      ...Object.keys(data.character_names || {}),
      ...Object.keys(data.agents || {}),
    ]);
    const ordered = characterOrder.filter((id) => ids.has(id));
    for (const id of ids) {
      if (!ordered.includes(id)) ordered.push(id);
    }
    return ordered;
  }, [data, characterOrder]);

  const filters: FilterType[] = ["all", "observation", "reflection", "plan", "action"];
  const currentTurnId = data?.last_turn_id;

  if (!data && !loading && !error && agentIds.length === 0) {
    return (
      <footer className="agent-memory-strip empty">
        <p className="muted">{t.agent.emptyHint}</p>
      </footer>
    );
  }

  return (
    <footer className="agent-memory-strip">
      <div className="strip-toolbar">
        <strong>{t.agent.title}</strong>
        <div className="strip-filters">
          {filters.map((f) => (
            <button
              key={f}
              type="button"
              className={`agent-filter${filter === f ? " active" : ""}${f === "action" ? " action-filter" : ""}`}
              onClick={() => setFilter(f)}
            >
              {f === "all" ? t.agent.filters.all : nodeLabels[f]}
            </button>
          ))}
        </div>
        {onOpenBrowser && (
          <button type="button" className="btn-debug strip-open-browser" onClick={onOpenBrowser}>
            {t.agent.openBrowser}
          </button>
        )}
        {onRefresh && (
          <button type="button" className="btn-debug strip-refresh" onClick={onRefresh} disabled={loading}>
            {loading ? t.agent.syncing : t.agent.refresh}
          </button>
        )}
      </div>

      {error && <div className="agent-memory-error strip-error">{error}</div>}

      <div className="agent-columns">
        {agentIds.map((id) => {
          const name = resolveNpcFullName(
            id,
            { ...characterNames, ...(data?.character_names || {}) },
            undefined,
            locale,
          );
          const nodes = data?.agents[id] || [];
          const turnNodes =
            currentTurnId != null
              ? nodes.filter((n) => n.turn_id === currentTurnId)
              : nodes;
          const filtered =
            filter === "all"
              ? turnNodes
              : turnNodes.filter((n) => n.node_type === filter);
          const debug = data?.last_agent_debug?.[id];
          const activePlan = nodes.find((n) => n.node_type === "plan" && n.is_active);
          const latestAction = [...turnNodes].reverse().find((n) => n.node_type === "action");
          const latestActionKind = latestAction?.meta?.action_kind as string | undefined;
          const latestActionLabel =
            (latestAction?.meta?.action_label as string | undefined) || latestActionKind;
          const isProcessing = turnLoading && debug?.action === "processing";

          return (
            <section key={id} className="agent-column">
              <header className="agent-column-head">
                <h3 title={name}>{resolveNpcLabel(id, { ...characterNames, ...(data?.character_names || {}) }, name, locale)}</h3>
                <div className="agent-column-stats">
                  <span title={t.agent.filters.observation}>👁 {countByType(nodes, "observation")}</span>
                  <span title={t.agent.filters.plan}>📋 {countByType(nodes, "plan")}</span>
                  <span title={t.agent.filters.action} className="stat-action">⚡ {countByType(nodes, "action")}</span>
                </div>
              </header>

              <div className="agent-column-status">
                {currentTurnId != null && (
                  <div className="status-line muted">
                    <span className="status-label">{t.agent.turn}</span>
                    <code>T{currentTurnId}</code>
                  </div>
                )}
                {isProcessing ? (
                  <p className="status-idle muted">{t.agent.thinking}</p>
                ) : debug ? (
                  <>
                    <div className="status-line">
                      <span className="status-label">{t.agent.action}</span>
                      <code>{actionLabel(debug.action)}</code>
                    </div>
                    {debug.spoke_content != null && String(debug.spoke_content).trim() !== "" ? (
                      <>
                        {(debug.action === "plan_fallback_speak" || debug.fallback_speak) && (
                          <p className="status-reason muted">{t.agent.fallbackHint}</p>
                        )}
                        <p className="status-spoke">「{String(debug.spoke_content)}」</p>
                      </>
                    ) : debug.action === "wait" ? (
                      <p className="status-reason muted">{t.agent.waitRound}</p>
                    ) : debug.reasoning != null ? (
                      <p className="status-reason">{String(debug.reasoning)}</p>
                    ) : null}
                  </>
                ) : latestAction ? (
                  <>
                    <div className="status-line">
                      <span className="status-label">{t.agent.action}</span>
                      <code>{actionLabel(latestActionLabel)}</code>
                    </div>
                    <p className="status-reason">{localizeMemoryContent(latestAction.content, locale)}</p>
                  </>
                ) : turnLoading ? (
                  <p className="status-idle muted">{t.agent.thinking}</p>
                ) : activePlan ? (
                  <p className="status-plan">
                    <span className="status-label">{t.agent.plan}</span>
                    {localizeMemoryContent(activePlan.content, locale).slice(0, 80)}
                    {activePlan.content.length > 80 ? "…" : ""}
                  </p>
                ) : (
                  <p className="status-idle muted">{t.agent.waiting}</p>
                )}
              </div>

              <div className="agent-column-list">
                {filtered.length === 0 && (
                  <div className="agent-memory-empty">
                    {turnLoading ? t.agent.thinking : currentTurnId != null ? t.agent.emptyRound : t.agent.empty}
                  </div>
                )}
                {filtered.slice(-8).reverse().map((node, i) => {
                  const actionKind =
                    (node.meta?.action_label as string | undefined) ||
                    (node.meta?.action_kind as string | undefined);
                  const src = sourceLabel(node.meta);
                  return (
                    <article
                      key={`${node.turn_id}-${node.tick}-${node.node_type}-${i}`}
                      className={`agent-memory-item compact type-${node.node_type}${node.is_active ? " active-plan" : ""}`}
                    >
                      <header>
                        <span className={`node-badge ${node.node_type}`}>
                          {nodeLabels[node.node_type] || node.node_type}
                        </span>
                        {node.node_type === "action" && actionKind && (
                          <span className="node-action-kind">{actionLabel(actionKind)}</span>
                        )}
                        {src && <span className="node-source-kind">{src}</span>}
                        <span className="node-turn">T{node.turn_id}</span>
                      </header>
                      <p className="node-content">{localizeMemoryContent(node.content, locale)}</p>
                    </article>
                  );
                })}
              </div>
            </section>
          );
        })}
      </div>
    </footer>
  );
}
