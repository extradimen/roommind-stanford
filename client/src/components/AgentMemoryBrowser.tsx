import { useCallback, useEffect, useMemo, useState } from "react";
import { resolveNpcLabel } from "../characterNames";
import { useLocale } from "../i18n";
import { localizeMemoryContent } from "../memoryDisplay";
import type { AgentMemoriesData, AgentMemoryNode } from "./AgentMemoryPanel";

type FilterType = "all" | "observation" | "reflection" | "plan" | "action";

type Props = {
  open: boolean;
  onClose: () => void;
  sessionUuid: string | null;
  data: AgentMemoriesData | null;
  loading?: boolean;
  error?: string;
  characterOrder?: string[];
  onRefresh?: () => void;
  onSaveNode?: (
    nodeId: number,
    patch: { content?: string; importance?: number; is_active?: boolean },
  ) => Promise<void>;
  standalone?: boolean;
};

function nodeKey(node: AgentMemoryNode, index: number) {
  return node.id != null
    ? `id-${node.id}`
    : `${node.turn_id}-${node.tick}-${node.node_type}-${index}`;
}

export default function AgentMemoryBrowser({
  open,
  onClose,
  sessionUuid,
  data,
  loading,
  error,
  characterOrder = [],
  onRefresh,
  onSaveNode,
  standalone = false,
}: Props) {
  const { t, locale } = useLocale();
  const b = t.browser;
  const nodeLabels: Record<string, string> = {
    observation: t.agent.filters.observation,
    reflection: t.agent.filters.reflection,
    plan: t.agent.filters.plan,
    action: t.agent.filters.action,
  };
  const actionKindLabel = (kind: string) => {
    const key = kind as keyof typeof t.agent.actions;
    return t.agent.actions[key] || kind;
  };
  const agentIds = useMemo(() => {
    const ids = new Set([
      ...characterOrder,
      ...Object.keys(data?.character_names || {}),
      ...Object.keys(data?.agents || {}),
    ]);
    const ordered = characterOrder.filter((id) => ids.has(id));
    for (const id of ids) {
      if (!ordered.includes(id)) ordered.push(id);
    }
    return ordered;
  }, [data, characterOrder]);

  const [activeTab, setActiveTab] = useState("");
  const [filter, setFilter] = useState<FilterType>("all");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [editImportance, setEditImportance] = useState(5);
  const [editActivePlan, setEditActivePlan] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");

  const tabId = activeTab && agentIds.includes(activeTab) ? activeTab : agentIds[0] || "";

  const nodes = useMemo(() => {
    if (!data || !tabId) return [];
    const list = data.agents[tabId] || [];
    if (filter === "all") return list;
    return list.filter((n) => n.node_type === filter);
  }, [data, tabId, filter]);

  const selectedNode = useMemo(() => {
    if (!selectedKey) return null;
    return nodes.find((n, i) => nodeKey(n, i) === selectedKey) || null;
  }, [nodes, selectedKey]);

  const readonly = selectedNode?.id == null || Boolean(selectedNode?.meta?.from_timeline);

  useEffect(() => {
    if (!open) return;
    if (!activeTab && agentIds.length) setActiveTab(agentIds[0]);
  }, [open, activeTab, agentIds]);

  useEffect(() => {
    if (!selectedNode) {
      setEditContent("");
      return;
    }
    setEditContent(selectedNode.content);
    setEditImportance(selectedNode.importance);
    setEditActivePlan(selectedNode.is_active);
    setSaveMsg("");
  }, [selectedNode]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const openInNewWindow = useCallback(() => {
    if (!sessionUuid) return;
    const url = `${window.location.origin}/memory/${sessionUuid}`;
    window.open(url, "_blank", "noopener,noreferrer,width=960,height=720");
  }, [sessionUuid]);

  const handleSave = async () => {
    if (!selectedNode?.id || !onSaveNode || readonly) return;
    setSaving(true);
    setSaveMsg("");
    try {
      await onSaveNode(selectedNode.id, {
        content: editContent,
        importance: editImportance,
        ...(selectedNode.node_type === "plan" ? { is_active: editActivePlan } : {}),
      });
      setSaveMsg(b.saved);
      onRefresh?.();
    } catch (e) {
      setSaveMsg(String(e));
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  const filters: FilterType[] = ["all", "observation", "reflection", "plan", "action"];

  return (
    <div
      className={`memory-browser-overlay${standalone ? " standalone" : ""}`}
      role="dialog"
      aria-modal={!standalone}
      aria-label={b.title}
    >
      <div className="memory-browser-window">
        <header className="memory-browser-chrome">
          <div className="memory-browser-dots">
            <button type="button" className="mb-dot close" onClick={onClose} title={b.close} aria-label={b.close} />
            <span className="mb-dot min" />
            <span className="mb-dot max" />
          </div>
          <div className="memory-browser-title">{b.title}</div>
          <div className="memory-browser-actions">
            {sessionUuid && (
              <button type="button" className="btn-debug" onClick={openInNewWindow} title={b.newWindow}>
                {b.newWindow}
              </button>
            )}
            {onRefresh && (
              <button type="button" className="btn-debug" onClick={onRefresh} disabled={loading}>
                {loading ? b.refreshing : b.refresh}
              </button>
            )}
          </div>
        </header>

        <nav className="memory-browser-tabs">
          {agentIds.map((id) => {
            const name = resolveNpcLabel(id, data?.character_names || {}, id, locale);
            const count = data?.agents[id]?.length ?? 0;
            return (
              <button
                key={id}
                type="button"
                className={`memory-tab${tabId === id ? " active" : ""}`}
                onClick={() => {
                  setActiveTab(id);
                  setSelectedKey(null);
                }}
              >
                {name}
                <span className="memory-tab-count">{count}</span>
              </button>
            );
          })}
          {agentIds.length === 0 && (
            <span className="memory-tab empty-tab">{b.noAgent}</span>
          )}
        </nav>

        <div className="memory-browser-toolbar">
          {filters.map((f) => (
            <button
              key={f}
              type="button"
              className={`agent-filter${filter === f ? " active" : ""}${f === "action" ? " action-filter" : ""}`}
              onClick={() => setFilter(f)}
            >
              {f === "all" ? b.all : nodeLabels[f]}
            </button>
          ))}
        </div>

        {error && <div className="agent-memory-error">{error}</div>}

        <div className="memory-browser-body">
          <aside className="memory-browser-list">
            {nodes.length === 0 && (
              <p className="muted memory-list-empty">{b.emptyList}</p>
            )}
            {nodes.map((node, i) => {
              const key = nodeKey(node, i);
              const actionKind = node.meta?.action_kind as string | undefined;
              return (
                <button
                  key={key}
                  type="button"
                  className={`memory-list-item type-${node.node_type}${selectedKey === key ? " selected" : ""}${node.is_active ? " active-plan" : ""}`}
                  onClick={() => setSelectedKey(key)}
                >
                  <div className="memory-list-item-head">
                    <span className={`node-badge ${node.node_type}`}>
                      {nodeLabels[node.node_type] || node.node_type}
                    </span>
                    {node.node_type === "action" && actionKind && (
                      <span className="node-action-kind">
                        {actionKindLabel(actionKind)}
                      </span>
                    )}
                    <span className="node-turn">T{node.turn_id}</span>
                    {node.id == null && <span className="node-readonly">{b.readonly}</span>}
                  </div>
                  <p className="memory-list-preview">{localizeMemoryContent(node.content, locale)}</p>
                </button>
              );
            })}
          </aside>

          <main className="memory-browser-editor">
            {!selectedNode && (
              <div className="memory-editor-empty">
                <p>{b.selectHint}</p>
                <p className="muted">{b.selectHint2}</p>
              </div>
            )}
            {selectedNode && (
              <>
                <div className="memory-editor-meta">
                  <span className={`node-badge ${selectedNode.node_type}`}>
                    {nodeLabels[selectedNode.node_type]}
                  </span>
                  <span>{b.turn} T{selectedNode.turn_id}</span>
                  {readonly && <span className="readonly-badge">{b.readonlyReplay}</span>}
                  {Boolean(selectedNode.meta?.edited) && <span className="edited-badge">{b.edited}</span>}
                </div>
                <label className="memory-editor-field">
                  {b.content}
                  <textarea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    readOnly={readonly}
                    rows={10}
                    className="memory-editor-textarea"
                  />
                </label>
                <div className="memory-editor-row">
                  <label>
                    {b.importance}
                    <input
                      type="number"
                      min={1}
                      max={10}
                      step={0.5}
                      value={editImportance}
                      disabled={readonly}
                      onChange={(e) => setEditImportance(parseFloat(e.target.value) || 5)}
                    />
                  </label>
                  {selectedNode.node_type === "plan" && (
                    <label className="checkbox-inline">
                      <input
                        type="checkbox"
                        checked={editActivePlan}
                        disabled={readonly}
                        onChange={(e) => setEditActivePlan(e.target.checked)}
                      />
                      {b.currentPlan}
                    </label>
                  )}
                </div>
                {!readonly && onSaveNode && (
                  <div className="memory-editor-actions">
                    <button
                      type="button"
                      className="btn-primary-sm"
                      onClick={handleSave}
                      disabled={saving || !editContent.trim()}
                    >
                      {saving ? b.saving : b.save}
                    </button>
                    <button
                      type="button"
                      className="btn-debug"
                      onClick={() => {
                        setEditContent(selectedNode.content);
                        setEditImportance(selectedNode.importance);
                        setEditActivePlan(selectedNode.is_active);
                        setSaveMsg("");
                      }}
                    >
                      {b.undo}
                    </button>
                    {saveMsg && <span className={`save-msg${saveMsg === b.saved ? " ok" : " err"}`}>{saveMsg}</span>}
                  </div>
                )}
              </>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
