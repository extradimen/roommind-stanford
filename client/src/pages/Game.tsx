import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ChatMessage,
  connectGameWSWithRetry,
  createSession,
  getScenario,
  getSessionAgentMemories,
  getSessionMessages,
  NPCReply,
  resolveServiceUrls,
  Scenario,
  sendMessageREST,
  SessionAgentMemories,
  updateAgentMemoryNode,
} from "../api";
import AgentMemoryBrowser from "../components/AgentMemoryBrowser";
import AgentMemoryStrip from "../components/AgentMemoryStrip";
import type { AgentMemoriesData } from "../components/AgentMemoryPanel";
import GameDebugPanel, { type DebugLine } from "../components/GameDebugPanel";
import CharacterSideLegend from "../components/CharacterSideLegend";
import CharacterSideBadge from "../components/CharacterSideBadge";
import MeetingScene from "../components/MeetingScene";
import ResizeHandle from "../components/ResizeHandle";
import { buildCharacterNameMap, resolveNpcFullName, resolveNpcLabel, resolveScenarioText } from "../characterNames";
import { buildCharacterSideMap, resolveCharacterSide } from "../characterSide";
import { resolvePlayerCharacter, resolvePlayerChatLabel } from "../playerCharacter";
import LanguageSwitcher from "../components/LanguageSwitcher";
import { useLocale, type Locale } from "../i18n";
import { bindDragResize, usePersistedRatio } from "../hooks/usePersistedRatio";
import { useNpcTypewriter } from "../hooks/useNpcTypewriter";

const MAX_DEBUG_LINES = 60;

/** StrictMode 双挂载时避免重复 createSession */
const sessionCreateInflight = new Map<
  number,
  Promise<{ session_uuid: string; current_phase: string }>
>();

function sessionCacheKey(scenarioId: number) {
  return `roommind-stanford:v1:session:${scenarioId}`;
}

function ts(locale: Locale) {
  return new Date().toLocaleTimeString(locale === "zh" ? "zh-CN" : "en-US", { hour12: false });
}

function fill(template: string, vars: Record<string, string | number>) {
  return template.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ""));
}

export default function Game() {
  const { t, locale } = useLocale();
  const { scenarioId } = useParams();
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [sessionUuid, setSessionUuid] = useState<string | null>(null);
  const [phase, setPhase] = useState("opening");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeSpeaker, setActiveSpeaker] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [wsMode, setWsMode] = useState<"connecting" | "connected" | "rest">("connecting");
  const [loadingHint, setLoadingHint] = useState("");
  const [adminUrl, setAdminUrl] = useState("");
  const [debugLines, setDebugLines] = useState<DebugLine[]>([]);
  const [wsUrl, setWsUrl] = useState("");
  const [lastSendPath, setLastSendPath] = useState("—");
  const [serverNpcCount, setServerNpcCount] = useState<number | null>(null);
  const [agentMemories, setAgentMemories] = useState<AgentMemoriesData | null>(null);
  const [agentMemoryLoading, setAgentMemoryLoading] = useState(false);
  const [agentMemoryError, setAgentMemoryError] = useState("");
  const [memoryBrowserOpen, setMemoryBrowserOpen] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const gameMainRef = useRef<HTMLDivElement>(null);
  const sceneChatRef = useRef<HTMLDivElement>(null);
  const [sceneRatio, setSceneRatio] = usePersistedRatio("roommind-stanford:layout:scene-ratio", 0.28, 0.14, 0.52);
  const [agentRatio, setAgentRatio] = usePersistedRatio("roommind-stanford:layout:agent-ratio", 0.32, 0.16, 0.52);
  const loadingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const loadingWatchdogRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const turnWatchdogRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const npcStreamedRef = useRef(false);
  const sessionUuidRef = useRef<string | null>(null);
  const scenarioRef = useRef<Scenario | null>(null);
  const localeRef = useRef(locale);
  const { onNpcStart, onNpcDelta, onNpcDone, forceCompleteStreaming } = useNpcTypewriter(setMessages);

  useEffect(() => {
    localeRef.current = locale;
  }, [locale]);

  const wsHandlersRef = useRef({
    onNpcStart,
    onNpcDelta,
    onNpcDone,
    forceCompleteStreaming,
    syncNpcMessagesFromServer: async (_uuid: string) => {},
    refreshServerNpcCount: async (_uuid: string) => [] as ChatMessage[],
    refreshAgentMemories: async (_uuid: string) => {},
  });

  const pushDebug = useCallback((tag: string, detail: string) => {
    setDebugLines((prev) => {
      const next = [...prev, { ts: ts(locale), tag, detail }];
      return next.length > MAX_DEBUG_LINES ? next.slice(-MAX_DEBUG_LINES) : next;
    });
  }, [locale]);

  const clearLoadingTimer = () => {
    if (loadingTimerRef.current) {
      clearInterval(loadingTimerRef.current);
      loadingTimerRef.current = null;
    }
    if (loadingWatchdogRef.current) {
      clearTimeout(loadingWatchdogRef.current);
      loadingWatchdogRef.current = null;
    }
    if (turnWatchdogRef.current) {
      clearTimeout(turnWatchdogRef.current);
      turnWatchdogRef.current = null;
    }
    setLoadingHint("");
  };

  const startLoadingTimer = () => {
    clearLoadingTimer();
    const start = Date.now();
    loadingTimerRef.current = setInterval(() => {
      const sec = Math.floor((Date.now() - start) / 1000);
      if (sec < 15) {
        setLoadingHint(t.game.thinking);
      } else if (sec < 45) {
        setLoadingHint(fill(t.game.thinkingSec, { sec }));
      } else {
        setLoadingHint(fill(t.game.thinkingSlow, { sec }));
      }
    }, 1000);

    loadingWatchdogRef.current = setTimeout(() => {
      pushDebug("watchdog", "超过 180 秒无 turn_result，尝试从服务端拉取消息");
      if (sessionUuidRef.current) {
        syncNpcMessagesFromServer(sessionUuidRef.current).catch((e) => setError(String(e)));
      }
      setLoading(false);
      clearLoadingTimer();
    }, 180000);
  };

  const refreshServerNpcCount = useCallback(async (uuid: string) => {
    const serverMsgs = await getSessionMessages(uuid);
    const npcCount = serverMsgs.filter((m) => m.speaker_type === "npc").length;
    setServerNpcCount(npcCount);
    pushDebug("api", `服务端共 ${serverMsgs.length} 条消息，NPC ${npcCount} 条`);
    return serverMsgs;
  }, [pushDebug]);

  const refreshAgentMemories = useCallback(async (uuid: string) => {
    setAgentMemoryLoading(true);
    setAgentMemoryError("");
    try {
      const data: SessionAgentMemories = await getSessionAgentMemories(uuid);
      setAgentMemories((prev) => {
        const serverDebug = data.last_agent_debug || {};
        const prevDebug = prev?.last_agent_debug || {};
        const mergedIds = new Set([...Object.keys(serverDebug), ...Object.keys(prevDebug)]);
        const last_agent_debug: Record<string, Record<string, unknown>> = {};
        for (const id of mergedIds) {
          const fromServer = serverDebug[id];
          const fromPrev = prevDebug[id];
          if (fromServer?.action) {
            last_agent_debug[id] = { ...fromPrev, ...fromServer };
          } else if (fromPrev?.action) {
            last_agent_debug[id] = fromPrev;
          } else {
            last_agent_debug[id] = fromServer || fromPrev || {};
          }
        }
        return {
          orchestration_mode: data.orchestration_mode,
          character_names: {
            ...buildCharacterNameMap(scenarioRef.current?.characters, localeRef.current),
            ...(prev?.character_names || {}),
            ...(data.character_names || {}),
          },
          agents: data.agents || {},
          world_timeline: data.world_timeline || [],
          last_agent_debug,
          last_turn_id:
            data.last_turn_id ??
            prev?.last_turn_id ??
            undefined,
        };
      });
      pushDebug("memory", `Agent 记忆已刷新，角色数 ${Object.keys(data.agents || {}).length}`);
    } catch (e) {
      setAgentMemoryError(String(e));
      pushDebug("memory", `记忆拉取失败: ${String(e)}`);
    } finally {
      setAgentMemoryLoading(false);
    }
  }, [pushDebug]);

  const patchAgentDebug = useCallback((
    sharedState: Record<string, unknown>,
    replies?: NPCReply[],
  ) => {
    const lastDebug = sharedState._last_debug;
    if (!lastDebug || typeof lastDebug !== "object") return;
    const agents = (lastDebug as Record<string, unknown>).agents;
    if (!agents || typeof agents !== "object") return;
    const turnId = (lastDebug as Record<string, unknown>).turn_id;
    const nameMap = buildCharacterNameMap(scenarioRef.current?.characters, localeRef.current);

    setAgentMemories((prev) => {
      const last_agent_debug: Record<string, Record<string, unknown>> = {
        ...(prev?.last_agent_debug || {}),
        ...(agents as Record<string, Record<string, unknown>>),
      };
      for (const r of replies || []) {
        last_agent_debug[r.speaker_id] = {
          ...(last_agent_debug[r.speaker_id] || {}),
          action: "speak",
          spoke_content: r.text,
          emotion: r.emotion,
          gesture: r.gesture,
        };
      }
      return {
        orchestration_mode: prev?.orchestration_mode || "generative",
        character_names: { ...nameMap, ...(prev?.character_names || {}) },
        agents: prev?.agents || {},
        last_agent_debug,
        last_turn_id: typeof turnId === "number" ? turnId : prev?.last_turn_id,
      };
    });
  }, []);

  useEffect(() => {
    resolveServiceUrls()
      .then((u) => setAdminUrl(u.admin))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const id = parseInt(scenarioId || "0");
    if (!id) return;

    let cancelled = false;
    setScenario(null);
    setSessionUuid(null);
    setMessages([]);
    setError("");

    (async () => {
      try {
        const s = await getScenario(id);
        if (cancelled) return;
        setScenario(s);
        scenarioRef.current = s;

        const cacheKey = sessionCacheKey(id);
        const cached = sessionStorage.getItem(cacheKey);
        let uuid: string;

        if (cached) {
          pushDebug("session", `复用会话 ${cached.slice(0, 8)}…`);
          try {
            const history = await getSessionMessages(cached);
            if (!cancelled && history.length) {
              const nameMap = buildCharacterNameMap(s.characters, locale);
              setMessages(
                history.map((m) => ({
                  ...m,
                  display_name:
                    m.speaker_type === "npc"
                      ? resolveNpcFullName(m.speaker_id, nameMap, m.display_name, locale)
                      : undefined,
                })),
              );
            }
          } catch {
            /* ignore history load errors */
          }
          uuid = cached;
        } else {
          pushDebug("session", `创建会话 scenario=${id}`);
          let inflight = sessionCreateInflight.get(id);
          if (!inflight) {
            inflight = createSession(id);
            sessionCreateInflight.set(id, inflight);
            inflight.finally(() => sessionCreateInflight.delete(id));
          }
          const session = await inflight;
          if (cancelled) return;
          sessionStorage.setItem(cacheKey, session.session_uuid);
          setPhase(session.current_phase);
          pushDebug("session", `session_uuid=${session.session_uuid}`);
          uuid = session.session_uuid;
        }

        if (!cancelled) setSessionUuid(uuid);
      } catch (e) {
        if (!cancelled) {
          setError(String(e));
          pushDebug("error", String(e));
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [scenarioId, pushDebug]);

  useEffect(() => {
    sessionUuidRef.current = sessionUuid;
  }, [sessionUuid]);

  useEffect(() => {
    if (!scenario) return;
    const names = buildCharacterNameMap(scenario.characters, locale);
    setAgentMemories((prev) => ({
      orchestration_mode: prev?.orchestration_mode || "generative",
      character_names: { ...names, ...(prev?.character_names || {}) },
      agents: prev?.agents || {},
      last_agent_debug: prev?.last_agent_debug,
      last_turn_id: prev?.last_turn_id,
    }));
    const nameMap = buildCharacterNameMap(scenario.characters, locale);
    setMessages((prev) =>
      prev.map((m) =>
        m.speaker_type === "npc"
          ? {
              ...m,
              display_name: resolveNpcFullName(m.speaker_id, nameMap, m.display_name, locale),
            }
          : m,
      ),
    );
  }, [scenario, locale]);

  useEffect(() => {
    if (!sessionUuid) return;
    refreshAgentMemories(sessionUuid).catch(() => {});
  }, [sessionUuid, refreshAgentMemories]);

  const syncNpcMessagesFromServer = useCallback(async (uuid: string) => {
    pushDebug("sync", "从服务端拉取 NPC 消息…");
    const serverMsgs = await refreshServerNpcCount(uuid);
    const nameMap = buildCharacterNameMap(scenarioRef.current?.characters, localeRef.current);
    const npcMsgs = serverMsgs
      .filter((m) => m.speaker_type === "npc")
      .map((m) => ({
        ...m,
        display_name: resolveNpcFullName(m.speaker_id, nameMap, m.display_name, localeRef.current),
      }));

    setMessages((prev) => {
      const withoutStaleStreaming = prev.filter((m) => !(m.streaming && m.speaker_type === "npc"));
      const existingNpc = new Set(
        withoutStaleStreaming
          .filter((m) => m.speaker_type === "npc")
          .map((m) => `${m.speaker_id}:${m.content.trim()}`),
      );
      const toAdd = npcMsgs.filter((m) => !existingNpc.has(`${m.speaker_id}:${m.content.trim()}`));
      pushDebug("sync", `合并 ${toAdd.length} 条新 NPC 消息到界面`);
      if (!toAdd.length && withoutStaleStreaming.length === prev.length) return prev;
      return [...withoutStaleStreaming, ...toAdd];
    });
  }, [pushDebug, refreshServerNpcCount]);

  useEffect(() => {
    wsHandlersRef.current = {
      onNpcStart,
      onNpcDelta,
      onNpcDone,
      forceCompleteStreaming,
      syncNpcMessagesFromServer,
      refreshServerNpcCount,
      refreshAgentMemories,
    };
  });

  useEffect(() => {
    if (!sessionUuid) return;

    setWsMode("connecting");
    wsRef.current = null;
    pushDebug("ws", `开始连接 session=${sessionUuid}`);

    const disconnect = connectGameWSWithRetry(
      sessionUuid,
      (data) => {
        const h = wsHandlersRef.current;
        const type = String(data.type || "unknown");
        if (type === "debug") {
          pushDebug("server", String(data.message || data.stage || JSON.stringify(data)));
          if (data.stage === "committed" && sessionUuidRef.current) {
            h.refreshAgentMemories(sessionUuidRef.current).catch(() => {});
          }
          return;
        }

        pushDebug(
          "event",
          type === "npc_delta"
            ? `${type} ${data.speaker_id}`
            : `${type} ${JSON.stringify(data).slice(0, 120)}`,
        );

        if (data.type === "connected") {
          setPhase(data.phase as string);
        } else if (data.type === "turn_result") {
          setPhase(data.phase as string);
          setLoading(false);
          clearLoadingTimer();
          const shared = (data.shared_state as Record<string, unknown>) || {};
          const streamed = (data.replies as NPCReply[]) || [];
          patchAgentDebug(shared, streamed);
          const debugCount = data.debug_replies_count as number | undefined;
          pushDebug(
            "turn",
            `turn_result replies=${streamed.length} debug_count=${debugCount ?? "—"}`,
          );

          h.forceCompleteStreaming(
            streamed.map((r) => ({
              speaker_id: r.speaker_id,
              text: r.text,
              display_name: r.display_name,
              emotion: r.emotion,
              gesture: r.gesture,
            })),
          );

          if (streamed.length && !npcStreamedRef.current) {
            const nameMap = buildCharacterNameMap(scenarioRef.current?.characters, localeRef.current);
            const newMsgs: ChatMessage[] = streamed.map((r) => ({
              speaker_id: r.speaker_id,
              speaker_type: "npc",
              display_name: resolveNpcFullName(r.speaker_id, nameMap, r.display_name, localeRef.current),
              content: r.text,
              emotion: r.emotion,
              gesture: r.gesture,
            }));
            setMessages((prev) => {
              const keys = new Set(newMsgs.map((m) => `${m.speaker_id}:${m.content.trim()}`));
              const kept = prev.filter(
                (m) =>
                  m.speaker_type !== "npc" ||
                  !keys.has(`${m.speaker_id}:${m.content.trim()}`),
              );
              return [...kept, ...newMsgs];
            });
            if (newMsgs.length) {
              setActiveSpeaker(newMsgs[0].speaker_id);
              setTimeout(() => setActiveSpeaker(null), 3000);
            }
          }

          npcStreamedRef.current = false;
          if (sessionUuidRef.current) {
            h.syncNpcMessagesFromServer(sessionUuidRef.current).catch((e) => setError(String(e)));
            h.refreshServerNpcCount(sessionUuidRef.current).catch(() => {});
          }
        } else if (data.type === "npc_start") {
          npcStreamedRef.current = true;
          setLoadingHint(fill(t.game.speakingStream, {
            name: resolveNpcLabel(
              data.speaker_id as string,
              characterNames,
              data.display_name as string | undefined,
              localeRef.current,
            ),
          }));
          setActiveSpeaker(data.speaker_id as string);
          h.onNpcStart(data.speaker_id as string, data.display_name as string | undefined);
        } else if (data.type === "npc_delta") {
          h.onNpcDelta(data.speaker_id as string, data.delta as string);
        } else if (data.type === "npc_done") {
          h.onNpcDone(
            data.speaker_id as string,
            (data.text as string) || "",
            data.emotion as string | undefined,
            data.gesture as string | undefined,
          );
          const sid = data.speaker_id as string;
          const text = (data.text as string) || "";
          if (sid && text) {
            setAgentMemories((prev) => ({
              orchestration_mode: prev?.orchestration_mode || "generative",
              character_names: {
                ...buildCharacterNameMap(scenarioRef.current?.characters, localeRef.current),
                ...(prev?.character_names || {}),
              },
              agents: prev?.agents || {},
              last_turn_id: prev?.last_turn_id,
              last_agent_debug: {
                ...(prev?.last_agent_debug || {}),
                [sid]: {
                  action: "speak",
                  spoke_content: text,
                  emotion: data.emotion,
                  gesture: data.gesture,
                  reasoning: t.game.speakDone,
                },
              },
            }));
          }
          setTimeout(() => setActiveSpeaker(null), 3000);
        } else if (data.type === "processing") {
          const stage = String(data.stage || "");
          const msg = String(data.message || t.game.processing);
          if (stage === "seed_and_plan") {
            setLoadingHint(t.game.seedPlanning);
          } else {
            setLoadingHint(msg);
          }
          const speakerId = data.speaker_id as string | undefined;
          if (speakerId) {
            setAgentMemories((prev) => ({
              orchestration_mode: prev?.orchestration_mode || "generative",
              character_names: prev?.character_names || {},
              agents: prev?.agents || {},
              last_agent_debug: {
                ...(prev?.last_agent_debug || {}),
                [speakerId]: {
                  ...(prev?.last_agent_debug?.[speakerId] || {}),
                  action: "processing",
                  reasoning: String(data.message || t.game.processingPipeline),
                },
              },
            }));
          }
        } else if (data.type === "error") {
          setError(data.message as string);
          setLoading(false);
          clearLoadingTimer();
        }
      },
      (state, ws) => {
        if (state === "connected" && ws) {
          wsRef.current = ws;
          setWsMode("connected");
          pushDebug("ws", "状态: connected");
        } else if (state === "failed") {
          wsRef.current = null;
          setWsMode("rest");
          pushDebug("ws", "状态: failed → 将使用 REST");
        } else if (state === "connecting") {
          pushDebug("ws", "状态: connecting");
        }
      },
      {
        onDebug: (line, tag = "ws") => {
          if (tag === "ws-url") setWsUrl(line);
          pushDebug(tag, line);
        },
      },
    );

    return () => {
      wsRef.current = null;
      disconnect();
    };
  }, [sessionUuid, pushDebug, patchAgentDebug]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (e: FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || !sessionUuid || loading) return;

    setMessages((prev) => [...prev, { speaker_id: "user", speaker_type: "user", content: text }]);
    setInput("");
    setLoading(true);
    setError("");
    npcStreamedRef.current = false;
    startLoadingTimer();

    try {
      const wsOpen = wsRef.current?.readyState === WebSocket.OPEN;
      const canWs = wsOpen && wsMode === "connected";

      pushDebug(
        "send",
        `readyState=${wsRef.current?.readyState ?? "null"} wsMode=${wsMode} path=${canWs ? "websocket" : "rest"}`,
      );

      if (canWs) {
        setLastSendPath("websocket");
        wsRef.current!.send(JSON.stringify({ type: "user_message", content: text, locale }));
        pushDebug("send", `已通过 WS 发送: ${text.slice(0, 40)}`);
        turnWatchdogRef.current = setTimeout(() => {
          pushDebug("watchdog", "90s 未收到 turn_result，从服务端同步消息");
          setLoading(false);
          clearLoadingTimer();
          if (sessionUuidRef.current) {
            wsHandlersRef.current
              .syncNpcMessagesFromServer(sessionUuidRef.current)
              .catch((e) => setError(String(e)));
          }
        }, 90000);
        return;
      }

      setLastSendPath("rest");
      pushDebug("send", "走 REST /message …");
      const result = await sendMessageREST(sessionUuid, text, locale);
      setPhase(result.phase);
      const shared = (result.shared_state as Record<string, unknown>) || {};
      const replies = (result.replies || []) as NPCReply[];
      patchAgentDebug(shared, replies);
      const nameMap = buildCharacterNameMap(scenarioRef.current?.characters, localeRef.current);
      const newMsgs: ChatMessage[] = replies.map((r: NPCReply) => ({
        speaker_id: r.speaker_id,
        speaker_type: "npc",
        display_name: resolveNpcFullName(r.speaker_id, nameMap, r.display_name),
        content: r.text,
        emotion: r.emotion,
        gesture: r.gesture,
      }));
      pushDebug("rest", `HTTP 200 replies=${newMsgs.length}`);
      if (newMsgs.length) {
        setMessages((prev) => [...prev, ...newMsgs]);
        setActiveSpeaker(newMsgs[0].speaker_id);
        setTimeout(() => setActiveSpeaker(null), 3000);
      } else {
        await syncNpcMessagesFromServer(sessionUuid);
      }
      await refreshServerNpcCount(sessionUuid);
      await refreshAgentMemories(sessionUuid);
      setLoading(false);
      clearLoadingTimer();
    } catch (err) {
      const msg = String(err);
      setError(msg);
      pushDebug("error", msg);
      setLoading(false);
      clearLoadingTimer();
    }
  };

  const characterOrder = useMemo(
    () => (scenario?.characters || []).map((c) => c.character_id),
    [scenario],
  );

  const characterNames = useMemo(
    () => buildCharacterNameMap(scenario?.characters, locale),
    [scenario, locale],
  );
  const playerCharacter = useMemo(() => resolvePlayerCharacter(scenario), [scenario]);
  const characterSideMap = useMemo(
    () => buildCharacterSideMap(scenario?.characters),
    [scenario],
  );
  const characterJobTitles = useMemo(
    () =>
      Object.fromEntries(
        (scenario?.characters || []).map((c) => [c.character_id, c.job_title || ""]),
      ),
    [scenario],
  );

  if (!scenario) {
    return <div className="loading-screen">{error || t.game.loadingScenario}</div>;
  }

  const wsBadge =
    wsMode === "connected" ? t.game.wsConnected : wsMode === "connecting" ? t.game.wsConnecting : t.game.wsRest;

  const wsReadyState = wsRef.current?.readyState ?? null;

  const scenarioTitle = resolveScenarioText(
    scenario.slug,
    "title",
    scenario.title,
    t.scenarios as Record<string, Record<string, string>>,
  );
  const scenarioGoal = resolveScenarioText(
    scenario.slug,
    "goal",
    scenario.player_side_goal || scenario.business_goal || "",
    t.scenarios as Record<string, Record<string, string>>,
  );

  const onSceneResizeStart = (e: React.MouseEvent) => {
    const row = sceneChatRef.current;
    if (!row) return;
    const rect = row.getBoundingClientRect();
    bindDragResize(
      e,
      (clientX) => setSceneRatio((clientX - rect.left) / rect.width),
      "col-resize",
    );
  };

  const onAgentResizeStart = (e: React.MouseEvent) => {
    const main = gameMainRef.current;
    if (!main) return;
    const rect = main.getBoundingClientRect();
    bindDragResize(
      e,
      (_x, clientY) => setAgentRatio((rect.bottom - clientY) / rect.height),
      "row-resize",
    );
  };

  return (
    <div className="game-layout">
      <header className="game-header">
        <a href={adminUrl || "#"} className="back">← {t.nav.back}</a>
        <Link to="/system" className="back system-back">{t.nav.system}</Link>
        <div className="game-header-main">
          <h1>{scenarioTitle}</h1>
          <div className="game-header-meta">
            <span className="phase">{t.game.phase}: {phase}</span>
            <span className="orchestration-badge">{t.game.stanfordBadge}</span>
            <span className={`ws-badge ws-${wsMode}`}>{wsBadge}</span>
            <LanguageSwitcher className="inline-lang" />
          </div>
        </div>
        <p className="game-goal">🎯 {t.game.goal}: {scenarioGoal}</p>
        <CharacterSideLegend characters={scenario.characters || []} scenario={scenario} />
        <div className="game-header-debug">
          <GameDebugPanel
            corner
            lines={debugLines}
            sessionUuid={sessionUuid}
            wsMode={wsMode}
            wsUrl={wsUrl}
            wsReadyState={wsReadyState}
            sendPath={lastSendPath}
            uiMessageCount={messages.length}
            serverNpcCount={serverNpcCount}
            loading={loading}
            lastError={error}
            onRefreshServer={() => {
              if (sessionUuid) syncNpcMessagesFromServer(sessionUuid).catch((e) => setError(String(e)));
            }}
            onForceRest={() => {
              setWsMode("rest");
              wsRef.current = null;
              pushDebug("manual", "已手动切换为 REST 模式");
            }}
          />
        </div>
      </header>

      <div className="game-main" ref={gameMainRef}>
        <div
          className="game-main-upper"
          style={{ flex: `${1 - agentRatio} 1 0` }}
        >
          <section className="scene-chat-quadrant" ref={sceneChatRef}>
            <aside
              className="scene-widget"
              style={{ width: `${sceneRatio * 100}%` }}
              aria-label={t.game.roomPreview}
            >
              <MeetingScene
                characters={scenario.characters || []}
                playerCharacter={playerCharacter}
                activeSpeaker={activeSpeaker}
                compact
              />
              <span className="scene-widget-label">{t.game.room}</span>
            </aside>

            <ResizeHandle
              direction="horizontal"
              label={t.game.resizeScene}
              onDragStart={onSceneResizeStart}
            />

            <div className="chat-section">
              <div className="chat-main-head">
                <h2>{t.game.meeting}</h2>
                {loading && (
                  <span className="chat-status">{loadingHint || t.game.thinking}</span>
                )}
              </div>

              {wsMode === "rest" && (
                <div className="info-banner">{t.game.restBanner}</div>
              )}

              <div className="chat-messages">
                {messages.map((m, i) => {
                  const side = resolveCharacterSide(m.speaker_id, characterSideMap);
                  return (
                  <div
                    key={i}
                    className={`msg ${m.speaker_type} side-${side}${m.streaming ? " streaming" : ""}`}
                  >
                    <span className="speaker">
                      <CharacterSideBadge side={side} compact />
                      {m.speaker_id === "user"
                        ? resolvePlayerChatLabel(scenario, t.game.you)
                        : resolveNpcLabel(m.speaker_id, characterNames, m.display_name, locale)}
                    </span>
                    {m.speaker_id === "user" && playerCharacter?.job_title && (
                      <span className="speaker-title">{playerCharacter.job_title}</span>
                    )}
                    {m.speaker_id !== "user" && characterJobTitles[m.speaker_id] && (
                      <span className="speaker-title">{characterJobTitles[m.speaker_id]}</span>
                    )}
                    <p>
                      {m.content || (m.streaming ? "" : t.game.emptyContent)}
                      {m.streaming && <span className="stream-cursor">▍</span>}
                    </p>
                    {m.gesture && m.speaker_type === "npc" && (
                      <span className="meta">{m.emotion} · {m.gesture}</span>
                    )}
                  </div>
                  );
                })}
                {loading && !messages.some((m) => m.streaming) && (
                  <div className="msg system">{loadingHint || t.game.thinking}</div>
                )}
                <div ref={chatEndRef} />
              </div>

              {error && <div className="error-banner">{error}</div>}

              <form onSubmit={send} className="chat-input">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={t.game.inputPlaceholder}
                  disabled={loading}
                />
                <button type="submit" disabled={loading || !input.trim()}>{t.game.send}</button>
              </form>
            </div>
          </section>
        </div>

        <ResizeHandle
          direction="vertical"
          label={t.game.resizeAgent}
          onDragStart={onAgentResizeStart}
        />

        <div className="game-agent-panel" style={{ flex: `${agentRatio} 1 0` }}>
          <AgentMemoryStrip
            data={agentMemories}
            loading={agentMemoryLoading}
            turnLoading={loading}
            error={agentMemoryError}
            characterOrder={characterOrder}
            characterNames={characterNames}
            characterSideMap={characterSideMap}
            playerCharacter={playerCharacter}
            sessionUuid={sessionUuid}
            onOpenBrowser={() => setMemoryBrowserOpen(true)}
            onRefresh={() => {
              if (sessionUuid) refreshAgentMemories(sessionUuid).catch(() => {});
            }}
          />
        </div>
      </div>

      <AgentMemoryBrowser
        open={memoryBrowserOpen}
        onClose={() => setMemoryBrowserOpen(false)}
        sessionUuid={sessionUuid}
        data={agentMemories}
        loading={agentMemoryLoading}
        error={agentMemoryError}
        characterOrder={characterOrder}
        onRefresh={() => {
          if (sessionUuid) refreshAgentMemories(sessionUuid).catch(() => {});
        }}
        onSaveNode={
          sessionUuid
            ? async (nodeId, patch) => {
                await updateAgentMemoryNode(sessionUuid, nodeId, patch);
              }
            : undefined
        }
      />
    </div>
  );
}
