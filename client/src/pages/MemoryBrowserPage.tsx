import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import AgentMemoryBrowser from "../components/AgentMemoryBrowser";
import type { AgentMemoriesData } from "../components/AgentMemoryPanel";
import {
  getSessionAgentMemories,
  updateAgentMemoryNode,
} from "../api";

export default function MemoryBrowserPage() {
  const { sessionUuid } = useParams();
  const [data, setData] = useState<AgentMemoriesData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!sessionUuid) return;
    setLoading(true);
    setError("");
    try {
      const res = await getSessionAgentMemories(sessionUuid);
      setData({
        orchestration_mode: res.orchestration_mode,
        character_names: res.character_names || {},
        agents: res.agents || {},
        last_agent_debug: res.last_agent_debug || {},
      });
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [sessionUuid]);

  useEffect(() => {
    load();
  }, [load]);

  const characterOrder = Object.keys(data?.character_names || {});

  return (
    <div className="memory-browser-page">
      <AgentMemoryBrowser
        standalone
        open
        onClose={() => window.close()}
        sessionUuid={sessionUuid || null}
        data={data}
        loading={loading}
        error={error}
        characterOrder={characterOrder}
        onRefresh={load}
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
