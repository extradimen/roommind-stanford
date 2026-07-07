import { useState } from "react";
import { useLocale } from "../i18n";

export type DebugLine = {
  ts: string;
  tag: string;
  detail: string;
};

type Props = {
  lines: DebugLine[];
  sessionUuid: string | null;
  wsMode: string;
  wsUrl: string;
  wsReadyState: number | null;
  sendPath: string;
  uiMessageCount: number;
  serverNpcCount: number | null;
  loading: boolean;
  lastError: string;
  onRefreshServer: () => void;
  onForceRest: () => void;
  embedded?: boolean;
  corner?: boolean;
  defaultOpen?: boolean;
};

const WS_STATE: Record<number, string> = {
  0: "CONNECTING",
  1: "OPEN",
  2: "CLOSING",
  3: "CLOSED",
};

export default function GameDebugPanel({
  lines,
  sessionUuid,
  wsMode,
  wsUrl,
  wsReadyState,
  sendPath,
  uiMessageCount,
  serverNpcCount,
  loading,
  lastError,
  onRefreshServer,
  onForceRest,
  embedded = false,
  corner = false,
  defaultOpen = false,
}: Props) {
  const { t } = useLocale();
  const d = t.debug;
  const [open, setOpen] = useState(defaultOpen || embedded);
  const isOpen = embedded || corner ? open : open;

  const body = (
    <div className="debug-body">
      <div className="debug-row">
        <span>{d.session}</span>
        <code>{sessionUuid || "—"}</code>
      </div>
      <div className="debug-row">
        <span>{d.transport}</span>
        <code>{wsMode}</code>
        <span>{d.send}</span>
        <code>{sendPath}</code>
      </div>
      <div className="debug-row">
        <span>WS</span>
        <code>{wsReadyState != null ? WS_STATE[wsReadyState] ?? wsReadyState : "—"}</code>
      </div>
      <div className="debug-row">
        <span>{d.wsAddr}</span>
        <code className="debug-url">{wsUrl || "—"}</code>
      </div>
      <div className="debug-row">
        <span>{d.uiMessages}</span>
        <code>{uiMessageCount}</code>
        <span>{d.serverNpc}</span>
        <code>{serverNpcCount ?? "—"}</code>
      </div>
      {lastError && (
        <div className="debug-error">{d.error}: {lastError}</div>
      )}
      <div className="debug-actions">
        <button type="button" className="btn-debug" onClick={onRefreshServer}>{d.pullServer}</button>
        <button type="button" className="btn-debug" onClick={onForceRest}>{d.forceRest}</button>
      </div>
      <div className="debug-log">
        {lines.length === 0 && <div className="debug-line muted">{d.emptyLog}</div>}
        {lines.map((l, i) => (
          <div key={i} className="debug-line">
            <span className="debug-ts">{l.ts}</span>
            <span className="debug-tag">{l.tag}</span>
            <span className="debug-detail">{l.detail}</span>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className={`debug-panel${embedded ? " embedded" : ""}${corner ? " corner" : ""}`}>
      {embedded ? (
        <>
          <div className="debug-panel-title">
            {d.title} {loading ? `· ${d.processing}` : ""}
          </div>
          {body}
        </>
      ) : (
        <>
          <button
            type="button"
            className={`debug-toggle${corner ? " corner-toggle" : ""}`}
            onClick={() => setOpen((v) => !v)}
            aria-expanded={isOpen}
          >
            {isOpen ? "▼" : "▶"} {d.title}
            {loading && ` · ${d.processing}`}
            {!isOpen && wsMode && (
              <span className={`debug-ws-dot ws-${wsMode}`} title={wsMode} />
            )}
          </button>
          {isOpen && body}
        </>
      )}
    </div>
  );
}
