const ADMIN_SECRET_KEY = "roommind_admin_secret";

export function getAdminSecret(): string {
  return localStorage.getItem(ADMIN_SECRET_KEY) || "roommind-admin-dev-secret";
}

export function setAdminSecret(secret: string) {
  localStorage.setItem(ADMIN_SECRET_KEY, secret);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Admin-Secret": getAdminSecret(),
    ...(options.headers as Record<string, string>),
  };
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  getProviders: () =>
    request<{
      providers: Record<string, string[]>;
      catalogs: Record<string, { id: string; name: string }[]>;
      meta?: Record<string, unknown>;
    }>(`/api/admin/llm/providers?_=${Date.now()}`),
  getLLMConfig: () => request<LLMConfig | null>("/api/admin/llm/config"),
  updateLLMConfig: (id: number, data: Partial<LLMConfig>) =>
    request<LLMConfig>(`/api/admin/llm/config/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  getLLMStatus: () => request<Record<string, unknown>>("/api/admin/llm/status"),

  getLLMKeys: () => request<LLMKeysStatus>("/api/admin/llm/keys"),
  updateLLMKeys: (data: { siliconflow_api_key?: string; ollama_api_key?: string }) =>
    request<LLMKeysStatus>("/api/admin/llm/keys", { method: "PUT", body: JSON.stringify(data) }),

  listScenarios: () => request<ScenarioListItem[]>("/api/admin/scenarios"),
  getScenario: (id: number) => request<Scenario>("/api/admin/scenarios/" + id),
  createScenario: (data: ScenarioInput) =>
    request<Scenario>("/api/admin/scenarios", { method: "POST", body: JSON.stringify(data) }),
  updateScenario: (id: number, data: ScenarioInput) =>
    request<Scenario>(`/api/admin/scenarios/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteScenario: (id: number) =>
    request<{ status: string }>(`/api/admin/scenarios/${id}`, { method: "DELETE" }),

  listDispatchRules: (scenarioId?: number) =>
    request<DispatchRule[]>(
      "/api/admin/dispatch-rules" + (scenarioId != null ? `?scenario_id=${scenarioId}` : "")
    ),
  createDispatchRule: (data: DispatchRuleInput) =>
    request<DispatchRule>("/api/admin/dispatch-rules", { method: "POST", body: JSON.stringify(data) }),
  updateDispatchRule: (id: number, data: DispatchRuleInput) =>
    request<DispatchRule>(`/api/admin/dispatch-rules/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteDispatchRule: (id: number) =>
    request<{ status: string }>(`/api/admin/dispatch-rules/${id}`, { method: "DELETE" }),

  getPlatformConfig: () => request<PlatformConfig>("/api/admin/platform-config"),
  updatePlatformConfig: (data: PlatformConfigInput) =>
    request<PlatformConfig>("/api/admin/platform-config", { method: "PUT", body: JSON.stringify(data) }),

  getOrchestration: (scenarioId: number) =>
    request<OrchestrationResponse>(`/api/admin/scenarios/${scenarioId}/orchestration`),
  updateOrchestration: (scenarioId: number, config: Record<string, unknown>) =>
    request<OrchestrationResponse>(`/api/admin/scenarios/${scenarioId}/orchestration`, {
      method: "PUT",
      body: JSON.stringify({ orchestration_config: config }),
    }),

  listSessions: (scenarioId?: number, limit = 40) =>
    request<SessionListItem[]>(
      `/api/admin/sessions?limit=${limit}` + (scenarioId != null ? `&scenario_id=${scenarioId}` : ""),
    ),
  getSessionDebug: (sessionUuid: string) =>
    request<SessionDebug>(`/api/admin/sessions/${sessionUuid}/debug`),
};

export interface LLMConfig {
  id: number;
  name: string;
  provider: string;
  model: string;
  base_url: string | null;
  temperature: number;
  max_tokens: number;
  is_active: boolean;
}

export interface LLMKeysStatus {
  siliconflow: { configured: boolean; masked: string };
  ollama: { configured: boolean; masked: string };
  storage: string;
}

export interface Character {
  id?: number;
  character_id: string;
  display_name: string;
  persona: string;
  responsibility: string;
  tendency: Record<string, string>;
  private_state: Record<string, unknown>;
  system_prompt?: string | null;
  voice_id?: string | null;
  spawn_point?: string | null;
  avatar_manifest: Record<string, unknown>;
  llm_config?: Record<string, unknown>;
  sort_order: number;
}

export interface Scenario {
  id: number;
  slug: string;
  title: string;
  description: string | null;
  business_goal: string;
  phases: string[];
  win_conditions: Record<string, unknown>[];
  scene_config: Record<string, unknown>;
  orchestration_config?: Record<string, unknown>;
  is_published: boolean;
  characters: Character[];
}

export type ScenarioInput = Omit<Scenario, "id">;

export interface ScenarioListItem {
  id: number;
  slug: string;
  title: string;
  description: string | null;
  is_published: boolean;
  character_count: number;
}

export interface OrchestrationResponse {
  scenario_id: number;
  orchestration_config: Record<string, unknown>;
  orchestration_mode?: string;
}

export interface SessionListItem {
  session_uuid: string;
  scenario_id: number;
  orchestration_mode: string;
  current_phase: string;
  status: string;
  created_at?: string;
}

export interface SessionDebug {
  session_uuid: string;
  scenario_id: number;
  orchestration_mode: string;
  current_phase: string;
  shared_state: Record<string, unknown>;
  orchestration_config: Record<string, unknown>;
  last_debug: Record<string, unknown>;
  messages: Array<{
    speaker_id: string;
    speaker_type: string;
    content: string;
    emotion?: string | null;
    gesture?: string | null;
  }>;
  agent_memories?: Record<string, Array<Record<string, unknown>>>;
  character_names?: Record<string, string>;
}

export interface DispatchRule {
  id: number;
  scenario_id: number | null;
  name: string;
  description: string | null;
  trigger_keywords: string[];
  priority_character_ids: string[];
  min_speakers: number;
  max_speakers: number;
  weights: Record<string, number>;
  is_active: boolean;
}

export type DispatchRuleInput = Omit<DispatchRule, "id">;

export interface PlatformPorts {
  api: number;
  admin: number;
  client: number;
  postgres: number;
  redis: number;
}

export interface PlatformHosts {
  api_bind: string;
  public_host: string;
}

export interface PlatformDatabase {
  user: string;
  password: string;
  name: string;
}

export interface PlatformConfig {
  ports: PlatformPorts;
  hosts: PlatformHosts;
  database: PlatformDatabase;
  urls: Record<string, string>;
  detected_public_host?: string;
  config_path: string;
  restart_note: string;
}

export type PlatformConfigInput = Pick<PlatformConfig, "ports" | "hosts" | "database">;
