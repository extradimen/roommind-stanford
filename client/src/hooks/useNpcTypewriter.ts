import { useCallback, useEffect, useRef, type Dispatch, type SetStateAction } from "react";
import type { ChatMessage } from "../api";

type StreamMeta = {
  emotion?: string;
  gesture?: string;
  finalText?: string;
  done: boolean;
};

/** 将 WebSocket 增量文本以打字机方式逐字显示（每轮发言独立 streamKey，避免同角色串台） */
export function useNpcTypewriter(
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>,
) {
  const buffersRef = useRef<Record<string, string>>({});
  const shownLenRef = useRef<Record<string, number>>({});
  const metaRef = useRef<Record<string, StreamMeta>>({});
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const seqRef = useRef(0);
  const activeStreamKeyRef = useRef<string | null>(null);

  const stopPump = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const pump = useCallback(() => {
    let keepGoing = false;

    setMessages((prev) => {
      let changed = false;
      const next = prev.map((m) => {
        if (!m.streaming || !m.streamKey) return m;

        const key = m.streamKey;
        const buf = buffersRef.current[key] || "";
        const shown = shownLenRef.current[key] || 0;
        const meta = metaRef.current[key];

        if (shown < buf.length) {
          const backlog = buf.length - shown;
          const step = backlog > 24 ? 3 : backlog > 10 ? 2 : 1;
          const newShown = Math.min(buf.length, shown + step);
          shownLenRef.current[key] = newShown;
          changed = true;
          keepGoing = true;
          return { ...m, content: buf.slice(0, newShown) };
        }

        if (meta?.done) {
          delete buffersRef.current[key];
          delete shownLenRef.current[key];
          delete metaRef.current[key];
          if (activeStreamKeyRef.current === key) {
            activeStreamKeyRef.current = null;
          }
          changed = true;
          return {
            ...m,
            content: meta.finalText || m.content,
            emotion: meta.emotion,
            gesture: meta.gesture,
            streaming: false,
          };
        }

        keepGoing = true;
        return m;
      });

      return changed ? next : prev;
    });

    if (keepGoing) {
      timerRef.current = setTimeout(pump, 32);
    } else {
      timerRef.current = null;
    }
  }, [setMessages]);

  const ensurePump = useCallback(() => {
    if (!timerRef.current) pump();
  }, [pump]);

  const onNpcStart = useCallback(
    (speakerId: string, displayName?: string) => {
      seqRef.current += 1;
      const streamKey = `${speakerId}-${seqRef.current}`;
      activeStreamKeyRef.current = streamKey;
      buffersRef.current[streamKey] = "";
      shownLenRef.current[streamKey] = 0;
      delete metaRef.current[streamKey];
      setMessages((prev) => [
        ...prev,
        {
          speaker_id: speakerId,
          speaker_type: "npc",
          display_name: displayName,
          content: "",
          streaming: true,
          streamKey,
        },
      ]);
    },
    [setMessages],
  );

  const onNpcDelta = useCallback(
    (speakerId: string, delta: string) => {
      if (!delta) return;
      const key = activeStreamKeyRef.current;
      if (!key || !key.startsWith(`${speakerId}-`)) return;
      buffersRef.current[key] = (buffersRef.current[key] || "") + delta;
      ensurePump();
    },
    [ensurePump],
  );

  const onNpcDone = useCallback(
    (speakerId: string, text: string, emotion?: string, gesture?: string) => {
      const key = activeStreamKeyRef.current;
      if (!key || !key.startsWith(`${speakerId}-`)) return;
      if (text) {
        buffersRef.current[key] = text;
      }
      metaRef.current[key] = {
        done: true,
        finalText: text,
        emotion,
        gesture,
      };
      ensurePump();
    },
    [ensurePump],
  );

  const reset = useCallback(() => {
    stopPump();
    buffersRef.current = {};
    shownLenRef.current = {};
    metaRef.current = {};
    activeStreamKeyRef.current = null;
    seqRef.current = 0;
  }, [stopPump]);

  /** turn_result 时强制结束流式气泡，避免卡在 streaming 状态 */
  const forceCompleteStreaming = useCallback(
    (
      replies?: Array<{
        speaker_id: string;
        text: string;
        display_name?: string;
        emotion?: string;
        gesture?: string;
      }>,
    ) => {
      stopPump();
      const replyMap = Object.fromEntries((replies || []).map((r) => [r.speaker_id, r]));
      setMessages((prev) =>
        prev.map((m) => {
          if (!m.streaming) return m;
          const r = replyMap[m.speaker_id];
          return {
            ...m,
            content: r?.text || m.content || "（空）",
            display_name: r?.display_name || m.display_name,
            emotion: r?.emotion ?? m.emotion,
            gesture: r?.gesture ?? m.gesture,
            streaming: false,
            streamKey: undefined,
          };
        }),
      );
      buffersRef.current = {};
      shownLenRef.current = {};
      metaRef.current = {};
      activeStreamKeyRef.current = null;
    },
    [setMessages, stopPump],
  );

  useEffect(() => () => stopPump(), [stopPump]);

  return { onNpcStart, onNpcDelta, onNpcDone, reset, forceCompleteStreaming };
}
