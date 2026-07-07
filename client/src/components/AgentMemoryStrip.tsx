import { useMemo, useState } from "react";
import { resolveNpcFullName, resolveNpcLabel, resolvePlayerFullName, resolvePlayerLabel } from "../characterNames";
import { resolveCharacterSide, type CharacterSide } from "../characterSide";
import type { PlayerCharacter } from "../api";
import { downloadJsonFile, exportSessionBundle } from "../api";
import { useLocale } from "../i18n";
import CharacterSideBadge from "./CharacterSideBadge";
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
  characterSideMap?: Record<string, CharacterSide>;
  playerCharacter?: PlayerCharacter | null;
  sessionUuid?: string | null;
  onRefresh?: () => void;
  onOpenBrowser?: () => void;
};

function countByType(nodes: AgentMemoryNode[], type: string) {
  return nodes.filter((n) => n.node_type === type).length;
}

function userSpeechForTurn(
  timeline: Array<Record<string, unknown>> | undefined,
  turnId: number | null | undefined,
): string | null {
  if (turnId == null || !timeline?.length) return null;
  const events = timeline.filter(
    (e) => e.event_type === "user_speech" && Number(e.turn_id) === turnId,
  );
  const last = events[events.length - 1];
  return last ? String(last.content || "").trim() || null : null;
}

function userTimelineEntries(
  timeline: Array<Record<string, unknown>> | undefined,
  turnId: number | null | undefined,
): Array<Record<string, unknown>> {
  if (!timeline?.length) return [];
  return timeline.filter((e) => {
    if (e.event_type !== "user_speech") return false;
    if (turnId == null) return true;
    return Number(e.turn_id) === turnId;
  });
}

export default function AgentMemoryStrip({
  data,
  loading,
  turnLoading = false,
  error,
  characterOrder = [],
  characterNames = {},
  characterSideMap = {},
  playerCharacter = null,
  sessionUuid = null,
  onRefresh,
  onOpenBrowser,
}: Props) {
  const { t, locale } = useLocale();
  const [filter, setFilter] = useState<FilterType>("all");
  const [exportMsg, setExportMsg] = useState("");

  const exportSession = async () => {
    if (!sessionUuid) return;
    try {
      setExportMsg("");
      const data = await exportSessionBundle(sessionUuid);
      downloadJsonFile(`session-${sessionUuid.slice(0, 8)}.json`, data);
    } catch (e) {
      setExportMsg(String(e));
    }
  };

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
    if (!data) return [...characterOrder, "user"];
    const ids = new Set([
      ...characterOrder,
      ...Object.keys(data.character_names || {}),
      ...Object.keys(data.agents || {}),
    ]);
    const ordered = characterOrder.filter((id) => ids.has(id));
    for (const id of ids) {
      if (id === "user") continue;
      if (!ordered.includes(id)) ordered.push(id);
    }
    if (!ordered.includes("user")) ordered.push("user");
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
        {sessionUuid && (
          <button type="button" className="btn-debug strip-open-browser" onClick={exportSession}>
            {t.agent.exportSession}
          </button>
        )}
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
      {exportMsg && <div className="agent-memory-error strip-error">{exportMsg}</div>}

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

          const isUserColumn = id === "user";
          const userSpeech = isUserColumn
            ? userSpeechForTurn(data?.world_timeline, currentTurnId)
            : null;
          const userEntries = isUserColumn
            ? userTimelineEntries(data?.world_timeline, currentTurnId)
            : [];

          const side = resolveCharacterSide(id, characterSideMap);
          const columnTitle = isUserColumn
            ? resolvePlayerFullName(playerCharacter || undefined) || t.game.you
            : name;
          const columnLabel = isUserColumn
            ? resolvePlayerLabel(playerCharacter || undefined) || t.game.you
            : resolveNpcLabel(id, { ...characterNames, ...(data?.character_names || {}) }, name, locale);

          return (
            <section key={id} className={`agent-column${isUserColumn ? " agent-column-user" : ""}`}>
              <header className="agent-column-head">
                <h3 title={columnTitle}>
                  <CharacterSideBadge side={side} compact />
                  {columnLabel}
                </h3>
                {!isUserColumn && (
                <div className="agent-column-stats">
                  <span title={t.agent.filters.observation}>👁 {countByType(nodes, "observation")}</span>
                  <span title={t.agent.filters.plan}>📋 {countByType(nodes, "plan")}</span>
                  <span title={t.agent.filters.action} className="stat-action">⚡ {countByType(nodes, "action")}</span>
                </div>
                )}
                {isUserColumn && playerCharacter?.job_title && (
                  <span className="agent-column-role">{playerCharacter.job_title}</span>
                )}
              </header>

              <div className="agent-column-status">
                {currentTurnId != null && (
                  <div className="status-line muted">
                    <span className="status-label">{t.agent.turn}</span>
                    <code>T{currentTurnId}</code>
                  </div>
                )}
                {isUserColumn ? (
                  userSpeech ? (
                    <>
                      <div className="status-line">
                        <span className="status-label">{t.agent.action}</span>
                        <code>{t.agent.actions.speak}</code>
                      </div>
                      <p className="status-spoke">「{userSpeech}」</p>
                    </>
                  ) : turnLoading ? (
                    <p className="status-idle muted">{t.agent.waiting}</p>
                  ) : (
                    <p className="status-idle muted">{t.agent.userIdle}</p>
                  )
                ) : isProcessing ? (
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
                {isUserColumn ? (
                  userEntries.length === 0 ? (
                    <div className="agent-memory-empty">
                      {turnLoading ? t.agent.thinking : currentTurnId != null ? t.agent.userIdle : t.agent.empty}
                    </div>
                  ) : (
                    [...userEntries].reverse().map((evt, i) => (
                      <article key={`user-${evt.event_id || i}`} className="agent-memory-item compact type-action">
                        <header>
                          <span className="node-badge action">{t.agent.filters.action}</span>
                          <span className="node-action-kind">{t.agent.actions.speak}</span>
                          <span className="node-turn">T{Number(evt.turn_id || 0)}</span>
                        </header>
                        <p className="node-content">{String(evt.content || "")}</p>
                      </article>
                    ))
                  )
                ) : filtered.length === 0 ? (
                  <div className="agent-memory-empty">
                    {turnLoading ? t.agent.thinking : currentTurnId != null ? t.agent.emptyRound : t.agent.empty}
                  </div>
                ) : null}
                {!isUserColumn && filtered.slice(-8).reverse().map((node, i) => {
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
