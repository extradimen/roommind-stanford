import { useMemo, useState } from "react";

export type AgentMemoryNode = {
  id?: number | null;
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
  world_timeline?: Array<Record<string, unknown>>;
  last_agent_debug?: Record<string, Record<string, unknown>>;
  last_turn_id?: number;
};

type FilterType = "all" | "observation" | "reflection" | "plan" | "action";

const NODE_LABELS: Record<string, string> = {
  observation: "观察",
  reflection: "反思",
  plan: "计划",
  action: "行动",
};

const ACTION_KIND_LABELS: Record<string, string> = {
  speak: "发言",
  wait: "观望",
  update_plan: "更新计划",
  internal_note: "内心整理",
  agent_action: "行动",
  plan_fallback_speak: "按计划发言",
};

type Props = {
  data: AgentMemoriesData | null;
  loading?: boolean;
  error?: string;
  compact?: boolean;
  collapsible?: boolean;
  defaultOpen?: boolean;
  onRefresh?: () => void;
};

function countByType(nodes: AgentMemoryNode[], type: string) {
  return nodes.filter((n) => n.node_type === type).length;
}

export default function AgentMemoryPanel({
  data,
  loading,
  error,
  compact,
  collapsible = false,
  defaultOpen = true,
  onRefresh,
}: Props) {
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
  const [open, setOpen] = useState(defaultOpen);

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

  if (!data && !loading && !error) {
    return (
      <div className="agent-memory-panel empty">
        <p className="muted">发送消息后，可在此查看观察 / 反思 / 计划 / 行动。</p>
      </div>
    );
  }

  const filters: FilterType[] = ["all", "observation", "reflection", "plan", "action"];

  return (
    <div className={`agent-memory-panel${compact ? " compact" : ""}`}>
      {collapsible ? (
        <button
          type="button"
          className="agent-memory-toggle"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "▼" : "▶"} Agent 记忆与行动
          {loading && " · 加载中…"}
        </button>
      ) : (
        <div className="agent-memory-header">
          <strong>Agent 记忆与行动</strong>
          {onRefresh && (
            <button type="button" className="btn-debug" onClick={onRefresh} disabled={loading}>
              {loading ? "刷新中…" : "刷新"}
            </button>
          )}
        </div>
      )}

      {(!collapsible || open) && (
        <>
          {collapsible && onRefresh && (
            <div className="agent-memory-toolbar">
              <button type="button" className="btn-debug" onClick={onRefresh} disabled={loading}>
                {loading ? "刷新中…" : "刷新"}
              </button>
            </div>
          )}

      {error && <div className="agent-memory-error">{error}</div>}

      {data && agentIds.length === 0 && (
        <div className="agent-memory-hint">暂无记录，发送一条消息后将自动生成观察、计划与行动。</div>
      )}

      {agentIds.length > 0 && (
        <>
          <div className="agent-tabs">
            {agentIds.map((id) => {
              const name = data?.character_names[id] || id;
              const list = data?.agents[id] ?? [];
              const actionCount = countByType(list, "action");
              return (
                <button
                  key={id}
                  type="button"
                  className={`agent-tab${selectedId === id ? " active" : ""}`}
                  onClick={() => setActiveAgent(id)}
                >
                  {name}
                  <span className="agent-tab-count">{list.length}</span>
                  {actionCount > 0 && (
                    <span className="agent-tab-actions" title="行动次数">⚡{actionCount}</span>
                  )}
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
                  className={`agent-filter${filter === f ? " active" : ""}${f === "action" ? " action-filter" : ""}`}
                  onClick={() => setFilter(f)}
                >
                  {f === "all" ? "全部" : NODE_LABELS[f]}
                  {count > 0 && <span className="filter-count">{count}</span>}
                </button>
              );
            })}
          </div>

          {agentDebug && (
            <div className="agent-last-action">
              <div className="agent-last-action-head">
                <span className="label">上轮行动</span>
                <code>{String(agentDebug.action || "—")}</code>
                {agentDebug.emotion != null && (
                  <span className="action-meta">{String(agentDebug.emotion)} · {String(agentDebug.gesture || "—")}</span>
                )}
              </div>
              {agentDebug.spoke_content != null && (
                <p className="agent-last-spoke">「{String(agentDebug.spoke_content)}」</p>
              )}
              {agentDebug.reasoning != null && (
                <p className="agent-last-reason">{String(agentDebug.reasoning)}</p>
              )}
            </div>
          )}

          <div className="agent-memory-list">
            {nodes.length === 0 && (
              <div className="agent-memory-empty">该分类下暂无记录</div>
            )}
            {nodes.map((node, i) => {
              const actionKind = node.meta?.action_kind as string | undefined;
              return (
              <article
                key={`${node.turn_id}-${node.tick}-${node.node_type}-${i}`}
                className={`agent-memory-item type-${node.node_type}${node.is_active ? " active-plan" : ""}`}
              >
                <header>
                  <span className={`node-badge ${node.node_type}`}>
                    {NODE_LABELS[node.node_type] || node.node_type}
                  </span>
                  {node.node_type === "action" && actionKind && (
                    <span className="node-action-kind">
                      {ACTION_KIND_LABELS[actionKind] || actionKind}
                    </span>
                  )}
                  <span className="node-importance" title="重要性">★ {node.importance.toFixed(1)}</span>
                  <span className="node-turn">T{node.turn_id}</span>
                  {node.node_type === "plan" && node.is_active && (
                    <span className="node-active">当前计划</span>
                  )}
                </header>
                <p className="node-content">{node.content}</p>
                {node.node_type === "action" && node.meta?.display_text != null && (
                  <p className="node-action-quote">「{String(node.meta.display_text)}」</p>
                )}
                {node.created_at && (
                  <footer className="node-meta">{node.created_at.slice(0, 19).replace("T", " ")}</footer>
                )}
              </article>
              );
            })}
          </div>
        </>
      )}
        </>
      )}
    </div>
  );
}
