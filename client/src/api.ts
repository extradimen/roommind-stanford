import { pageHostname, rewriteServiceUrls } from "./serviceUrls";

export interface Scenario {
  id: number;
  slug: string;
  title: string;
  description: string | null;
  business_goal?: string;
  player_side_goal?: string;
  schema_version?: 2;
  task_config?: Record<string, unknown>;
  player_character?: PlayerCharacter;
  phases?: string[];
  scene_config?: Record<string, unknown>;
  characters?: Character[];
}

export interface PlayerCharacter {
  character_id?: string;
  character_name: string;
  job_title: string;
  display_name: string;
  avatar_manifest?: AvatarManifestFields;
}

export interface AvatarManifestFields {
  suit?: string;
  skin?: string;
  accent?: string;
  pattern?: string;
  accessory?: string;
  height?: number;
  image_url?: string;
  model_url?: string;
  label?: string;
  team?: string;
  color?: string;
  glasses?: boolean;
  necklace?: boolean;
}

export interface Character {
  character_id: string;
  character_name?: string;
  job_title?: string;
  display_name: string;
  side?: "opponent" | "player_ally";
  team_id?: string;
  relationship_to_player?: string;
  interaction_role?: string;
  spawn_point?: string;
  avatar_manifest?: AvatarManifestFields;
}

export interface ChatMessage {
  speaker_id: string;
  speaker_type: string;
  speaker_source?: "human" | "ai" | "system";
  turn_id?: number;
  sequence_no?: number;
  content: string;
  display_name?: string;
  emotion?: string;
  gesture?: string;
  streaming?: boolean;
  streamKey?: string;
}

export interface BatchExperimentRun {
  id: number;
  scenario_id: number;
  condition: "roommind" | "baseline";
  session_mode: "test" | "baseline";
  repetition: number;
  status: string;
  session_uuid: string | null;
  result: Record<string, unknown>;
  error: string | null;
}

export interface BatchExperiment {
  batch_uuid: string;
  name: string;
  status: string;
  config: Record<string, unknown>;
  total_runs: number;
  completed_runs: number;
  failed_runs: number;
  cancelled_runs: number;
  created_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
  runs?: BatchExperimentRun[];
}

export interface BlindReviewPacket {
  run_label: string;
  gold_specification: Record<string, unknown>;
  public_transcript: Array<{ sequence_no?: number; turn_id?: number; speaker_id?: string; content?: string }>;
  fixed_window_transcript?: Array<{ sequence_no?: number; turn_id?: number; speaker_id?: string; content?: string }>;
  system_claim: Record<string, unknown>;
}

export interface BlindReviewQueue {
  protocol: string;
  packets: BlindReviewPacket[];
  saved_reviews: Record<string, Array<{ reviewer_id: string; ratings: Record<string, number> }>>;
}

export interface NPCReply {
  type: string;
  speaker_id: string;
  display_name: string;
  text: string;
  emotion: string;
  gesture: string;
}

export interface PlatformPorts {
  ports: { api: number; admin: number; client: number };
  public_host: string;
  urls?: { api?: string; client?: string };
}

let cachedWsBase: string | null = null;

const READ_RETRY_DELAYS_MS = [0, 250, 750];

async function fetchReadWithRetry(input: RequestInfo | URL): Promise<Response> {
  let lastError: unknown;
  for (const delay of READ_RETRY_DELAYS_MS) {
    if (delay) await new Promise((resolve) => window.setTimeout(resolve, delay));
    try {
      const response = await fetch(input, { cache: "no-store" });
      // Retry only transient gateway failures. Other HTTP responses are real
      // application results and must be handled by the caller.
      if (![502, 503, 504].includes(response.status)) return response;
      lastError = new Error(`Transient gateway response (HTTP ${response.status})`);
    } catch (error) {
      // Vite's development proxy can occasionally close an idle/reused
      // connection and surface ERR_EMPTY_RESPONSE as a fetch TypeError.
      lastError = error;
    }
  }
  throw lastError instanceof Error ? lastError : new Error("Failed to fetch");
}

/** Resolve WebSocket base URL (without path). */
export async function resolveWsBase(): Promise<string> {
  if (cachedWsBase) return cachedWsBase;

  // Build-time override for production (no Vite proxy)
  const envApi = import.meta.env.VITE_API_URL as string | undefined;
  if (envApi) {
    cachedWsBase = envApi.replace(/^http/i, "ws").replace(/\/$/, "");
    return cachedWsBase;
  }

  // Dev: same origin → Vite proxies /api to backend
  if (import.meta.env.DEV) {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    cachedWsBase = `${proto}://${window.location.host}`;
    return cachedWsBase;
  }

  // Prod: prefer same origin (Nginx 反代); fallback to platform ports API
  try {
    const res = await fetch("/api/platform/ports");
    if (res.ok) {
      const data = (await res.json()) as PlatformPorts;
      const host = window.location.hostname;
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      // Same host as page → use it (reverse proxy)
      if (host === data.public_host || host !== "localhost") {
        cachedWsBase = `${proto}://${window.location.host}`;
      } else {
        cachedWsBase = `${proto}://${data.public_host}:${data.ports.api}`;
      }
      return cachedWsBase;
    }
  } catch {
    /* ignore */
  }

  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  cachedWsBase = `${proto}://${window.location.host}`;
  return cachedWsBase;
}

export async function resolveServiceUrls(): Promise<{
  admin: string;
  client: string;
  api: string;
  publicHost: string;
  ports: PlatformPorts["ports"];
}> {
  const res = await fetch("/api/platform/ports");
  if (!res.ok) throw new Error("Failed to load platform ports");
  const data = (await res.json()) as PlatformPorts & {
    urls?: { admin?: string; client?: string; api?: string };
  };
  const configHost = data.public_host || "localhost";
  const host = pageHostname(configHost);
  const ports = data.ports;
  const resolved = rewriteServiceUrls(data.urls || {}, ports, configHost);
  return {
    admin: resolved.admin,
    client: resolved.client,
    api: resolved.api,
    publicHost: host,
    ports,
  };
}

export async function listScenarios(): Promise<Scenario[]> {
  const res = await fetch("/api/game/scenarios");
  if (!res.ok) throw new Error("Failed to load scenarios");
  return res.json();
}

export async function getScenario(id: number): Promise<Scenario> {
  const res = await fetch(`/api/game/scenarios/${id}?_=${Date.now()}`);
  if (!res.ok) throw new Error("Scenario not found");
  return res.json();
}

export async function getSessionMessages(sessionUuid: string): Promise<ChatMessage[]> {
  const res = await fetchReadWithRetry(`/api/game/sessions/${sessionUuid}/messages`);
  if (!res.ok) throw new Error("Failed to load messages");
  const rows = await res.json();
  return rows.map((m: ChatMessage) => ({
    speaker_id: m.speaker_id,
    speaker_type: m.speaker_type,
    speaker_source: m.speaker_source,
    turn_id: m.turn_id,
    sequence_no: m.sequence_no,
    content: m.content,
    emotion: m.emotion,
    gesture: m.gesture,
  }));
}

export interface AgentMemoryNode {
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
}

export interface SessionAgentMemories {
  session_uuid: string;
  orchestration_mode: string;
  character_names: Record<string, string>;
  agents: Record<string, AgentMemoryNode[]>;
  world_timeline: Array<Record<string, unknown>>;
  last_agent_debug: Record<string, Record<string, unknown>>;
  last_turn_id?: number | null;
}

export async function getSessionAgentMemories(sessionUuid: string): Promise<SessionAgentMemories> {
  const res = await fetchReadWithRetry(`/api/game/sessions/${sessionUuid}/agent-memories`);
  if (!res.ok) throw new Error("Failed to load agent memories");
  return res.json();
}

export async function exportSessionBundle(sessionUuid: string): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/game/sessions/${sessionUuid}/export`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to export session");
  }
  return res.json();
}

export function downloadJsonFile(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function updateAgentMemoryNode(
  sessionUuid: string,
  nodeId: number,
  patch: { content?: string; importance?: number; is_active?: boolean },
): Promise<AgentMemoryNode> {
  const res = await fetch(`/api/game/sessions/${sessionUuid}/agent-memories/${nodeId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "保存失败");
  }
  return res.json();
}

export async function createSession(
  scenarioId: number,
  sessionMode: "participation" | "test" | "baseline" = "participation",
): Promise<{ session_uuid: string; current_phase: string; orchestration_mode?: string; session_mode: string }> {
  const res = await fetch("/api/game/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scenario_id: scenarioId,
      session_mode: sessionMode,
      run_config: sessionMode !== "participation"
        ? { safety_max_turns: 50, max_stagnant_turns: 8, player_strategy: "balanced" }
        : {},
    }),
  });
  if (!res.ok) throw new Error("Failed to create session");
  return res.json();
}

export async function runTestStep(sessionUuid: string, maxSteps = 1, locale?: string, untilComplete = false) {
  const path = maxSteps === 1 && !untilComplete ? "step" : "run";
  const res = await fetch(`/api/game/sessions/${sessionUuid}/test/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ max_steps: maxSteps, until_complete: untilComplete, locale }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to run AI test turn");
  }
  return res.json();
}

export async function controlTestSession(sessionUuid: string, action: "pause" | "resume" | "stop") {
  const res = await fetch(`/api/game/sessions/${sessionUuid}/test/${action}`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to ${action} test session`);
  }
  return res.json();
}

export async function runExternalEvaluation(sessionUuid: string): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/game/sessions/${sessionUuid}/external-evaluation`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to run external evaluation");
  }
  return res.json();
}

export async function listBatchExperiments(): Promise<BatchExperiment[]> {
  const res = await fetchReadWithRetry("/api/game/batch-experiments");
  if (!res.ok) throw new Error("Failed to load batch experiments");
  return res.json();
}

export async function getBatchExperiment(batchUuid: string): Promise<BatchExperiment> {
  const res = await fetchReadWithRetry(`/api/game/batch-experiments/${batchUuid}`);
  if (!res.ok) throw new Error("Failed to load batch experiment");
  return res.json();
}

export async function createBatchExperiment(input: {
  name: string;
  scenario_ids: number[];
  conditions: ("test" | "baseline")[];
  repetitions: number;
  concurrency: number;
  safety_max_turns: number;
  max_stagnant_turns: number;
  locale?: string;
  random_seed: number;
  human_validation_enabled: boolean;
}): Promise<BatchExperiment> {
  const res = await fetch("/api/game/batch-experiments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Failed to create batch experiment");
  }
  return res.json();
}

export async function cancelBatchExperiment(batchUuid: string): Promise<BatchExperiment> {
  const res = await fetch(`/api/game/batch-experiments/${batchUuid}/cancel`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to cancel batch experiment");
  return res.json();
}

export async function retryBatchDialogue(batchUuid: string, runId: number): Promise<BatchExperiment> {
  const res = await fetch(`/api/game/batch-experiments/${batchUuid}/runs/${runId}/retry-dialogue`, {
    method: "POST",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Failed to retry dialogue");
  }
  return res.json();
}

export async function startBatchEvaluation(
  batchUuid: string,
  input: { run_ids?: number[]; retry_all?: boolean; concurrency?: number } = {},
): Promise<BatchExperiment> {
  const res = await fetch(`/api/game/batch-experiments/${batchUuid}/evaluate`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ concurrency: 1, ...input }),
  });
  if (!res.ok) { const body = await res.json().catch(() => ({})); throw new Error(body.detail || "Failed to start evaluation"); }
  return res.json();
}

export async function getBlindReviewQueue(batchUuid: string): Promise<BlindReviewQueue> {
  const res = await fetchReadWithRetry(`/api/game/batch-experiments/${batchUuid}/review-queue`);
  if (!res.ok) throw new Error("Failed to load blinded review queue");
  return res.json();
}

export async function submitBlindReview(
  batchUuid: string, runLabel: string,
  input: { reviewer_id: string; ratings: Record<string, number>; evidence: Record<string, unknown>; notes: string },
): Promise<void> {
  const res = await fetch(`/api/game/batch-experiments/${batchUuid}/reviews/${runLabel}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input),
  });
  if (!res.ok) { const body = await res.json().catch(() => ({})); throw new Error(body.detail || "Failed to save review"); }
}

export function connectGameWS(sessionUuid: string, wsBase: string): WebSocket {
  const base = wsBase.replace(/\/$/, "");
  return new WebSocket(`${base}/api/game/ws/${sessionUuid}`);
}

export async function sendMessageREST(sessionUuid: string, content: string, locale?: string) {
  let res: Response;
  try {
    res = await fetch(`/api/game/sessions/${sessionUuid}/message`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, locale }),
    });
  } catch {
    throw new Error("无法连接 API 后端（端口 8800），请确认服务已启动：bash scripts/start-all.sh");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = err.detail;
    if (typeof detail === "string") throw new Error(detail);
    if (Array.isArray(detail)) {
      throw new Error(detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join("; "));
    }
    throw new Error(`发送失败 (HTTP ${res.status})`);
  }
  return res.json();
}

export type WSMessageHandler = (data: Record<string, unknown>) => void;

/** Connect with retry; returns cleanup function. */
export function connectGameWSWithRetry(
  sessionUuid: string,
  onMessage: WSMessageHandler,
  onState: (state: "connecting" | "connected" | "failed", ws?: WebSocket) => void,
  options?: {
    onDebug?: (line: string, tag?: string) => void;
  },
): () => void {
  const onDebug = options?.onDebug;
  let active = true;
  let ws: WebSocket | null = null;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;
  let attempts = 0;
  const maxAttempts = 3;

  const cleanup = () => {
    active = false;
    if (retryTimer) clearTimeout(retryTimer);
    if (ws) {
      ws.onopen = ws.onclose = ws.onerror = ws.onmessage = null;
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close(1000);
      }
      ws = null;
    }
  };

  const tryConnect = async () => {
    if (!active) return;
    attempts += 1;
    onState("connecting");
    onDebug?.(`尝试连接 #${attempts}`, "ws");

    try {
      const base = await resolveWsBase();
      if (!active) return;

      const url = `${base.replace(/\/$/, "")}/api/game/ws/${sessionUuid}`;
      onDebug?.(url, "ws-url");
      ws = connectGameWS(sessionUuid, base);
      let opened = false;

      ws.onopen = () => {
        if (!active) return;
        opened = true;
        onDebug?.("WebSocket 已连接", "ws");
        onState("connected", ws!);
      };

      ws.onmessage = (ev) => {
        if (!active) return;
        try {
          onMessage(JSON.parse(ev.data));
        } catch {
          /* ignore bad json */
        }
      };

      ws.onerror = () => {
        /* wait for onclose */
      };

      ws.onclose = (ev) => {
        if (!active) return;
        onDebug?.(`WebSocket 关闭 code=${ev.code} reason=${ev.reason || "—"}`, "ws");
        if (opened) return;
        // Ignore normal close from React StrictMode remount
        if (ev.code === 1000 && attempts < maxAttempts) return;

        if (attempts < maxAttempts) {
          retryTimer = setTimeout(tryConnect, 400 * attempts);
        } else {
          onState("failed");
        }
      };
    } catch (err) {
      onDebug?.(`连接异常: ${String(err)}`, "ws");
      if (active && attempts < maxAttempts) {
        retryTimer = setTimeout(tryConnect, 400 * attempts);
      } else if (active) {
        onState("failed");
      }
    }
  };

  tryConnect();

  return () => {
    cleanup();
  };
}

/** Get current WebSocket ref for sending (if connected). */
export function createWsSender(getWs: () => WebSocket | null) {
  return (payload: object) => {
    const socket = getWs();
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(payload));
      return true;
    }
    return false;
  };
}
