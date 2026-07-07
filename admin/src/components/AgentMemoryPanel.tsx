import { useMemo, useState } from "react";
import { useLocale } from "../i18n";

export type AgentMemoryNode = {
  node_type: string;
  content: string;
  importance: number;
  turn_id: number;
  tick: number;
  is_active: boolean;
  source_event_ids?: string[];
  meta?: Record<string, unknown>;
  created_at?: string | null;
};

export type AgentMemoriesData = {
  orchestration_mode: string;
  character_names: Record<string, string>;
  agents: Record<string, AgentMemoryNode[]>;
  last_agent_debug?: Record<string, Record<string, unknown>>;
};

type FilterType = "all" | "observation" | "reflection" | "plan" | "action";

type Props = {
  data: AgentMemoriesData | null;
  loading?: boolean;
  error?: string;
  onRefresh?: () => void;
};

function countByType(nodes: AgentMemoryNode[], type: string) {
  return nodes.filter((n) => n.node_type === type).length;
}

export default function AgentMemoryPanel({
  data,
  loading,
  error,
  onRefresh,
}: Props) {
  const { t } = useLocale();
  const agentIds = useMemo(() => {
    if (!data) return [];
    const ids = new Set([
      ...Object.keys(data.character_names || {}),
      ...Object.keys(data.agents || {}),
    ]);
    return Array.from(ids);
  }, [data]);

  const [activeAgent, setActiveAgent] = useState("");
  const [filter, setFilter] = useState<FilterType>("all");

  const selectedId = activeAgent && agentIds.includes(activeAgent) ? activeAgent : agentIds[0] || "";

  const agentNodes = useMemo(() => {
    if (!data || !selectedId) return [];
    return data.agents[selectedId] || [];
  }, [data, selectedId]);

  const nodes = useMemo(() => {
    if (filter === "all") return agentNodes;
    return agentNodes.filter((n) => n.node_type === filter);
  }, [agentNodes, filter]);

  const agentDebug = selectedId && data?.last_agent_debug?.[selectedId];
  const filters: FilterType[] = ["all", "observation", "reflection", "plan", "action"];

  const nodeLabel = (type: string) => {
    const labels = t.agentMemory.filters as Record<string, string>;
    return labels[type] || type;
  };

  const actionLabel = (kind: string) => {
    const labels = t.agentMemory.actions as Record<string, string>;
    return labels[kind] || kind;
  };

  return (
    <div className="agent-memory-panel card full-width">
      <div className="agent-memory-header">
        <h3>{t.agentMemory.title}</h3>
        {onRefresh && (
          <button type="button" className="btn small" onClick={onRefresh} disabled={loading}>
            {loading ? t.common.refreshing : t.common.refresh}
          </button>
        )}
      </div>

      {error && <div className="alert error">{error}</div>}

      {!data && !loading && (
        <p className="muted">{t.agentMemory.selectHint}</p>
      )}

      {data && agentIds.length === 0 && (
        <p className="hint">{t.agentMemory.emptyHint}</p>
      )}

      {agentIds.length > 0 && (
        <>
          <div className="agent-tabs">
            {agentIds.map((id) => {
              const name = data?.character_names[id] || id;
              const list = data?.agents[id] ?? [];
              return (
                <button
                  key={id}
                  type="button"
                  className={`agent-tab${selectedId === id ? " active" : ""}`}
                  onClick={() => setActiveAgent(id)}
                >
                  {name}
                  <span className="agent-tab-count">{list.length}</span>
                </button>
              );
            })}
          </div>

          <div className="agent-filter-row">
            {filters.map((f) => {
              const count = f === "all" ? agentNodes.length : countByType(agentNodes, f);
              return (
                <button
                  key={f}
                  type="button"
                  className={`agent-filter${filter === f ? " active" : ""}`}
                  onClick={() => setFilter(f)}
                >
                  {nodeLabel(f)}
                  {count > 0 && ` (${count})`}
                </button>
              );
            })}
          </div>

          {agentDebug && (
            <div className="agent-last-decision">
              <strong>{t.agentMemory.lastAction}</strong>
              <code>{String(agentDebug.action || t.common.none)}</code>
              {agentDebug.spoke_content != null && (
                <span className="reason"> — 「{String(agentDebug.spoke_content)}」</span>
              )}
              {agentDebug.reasoning != null && !agentDebug.spoke_content && (
                <span className="reason"> — {String(agentDebug.reasoning)}</span>
              )}
            </div>
          )}

          <div className="agent-memory-list">
            {nodes.length === 0 && <p className="muted">{t.agentMemory.emptyFilter}</p>}
            {nodes.map((node, i) => {
              const actionKind = node.meta?.action_kind as string | undefined;
              return (
              <article
                key={`${node.turn_id}-${node.tick}-${node.node_type}-${i}`}
                className={`agent-memory-item type-${node.node_type}${node.is_active ? " active-plan" : ""}`}
              >
                <header>
                  <span className={`node-badge ${node.node_type}`}>
                    {nodeLabel(node.node_type)}
                  </span>
                  {node.node_type === "action" && actionKind && (
                    <span className="node-action-kind">
                      {actionLabel(actionKind)}
                    </span>
                  )}
                  <span className="node-importance">★ {node.importance.toFixed(1)}</span>
                  <span className="node-turn">{t.common.turn} {node.turn_id}</span>
                  {node.node_type === "plan" && node.is_active && (
                    <span className="node-active">{t.common.current}</span>
                  )}
                </header>
                <p className="node-content">{node.content}</p>
                {node.created_at && (
                  <footer className="node-meta">{node.created_at.slice(0, 19).replace("T", " ")}</footer>
                )}
              </article>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
