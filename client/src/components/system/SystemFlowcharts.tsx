import { useLocale } from "../../i18n";

type Rect = { x: number; y: number; w: number; h: number };
type Side = "n" | "s" | "e" | "w";
type BoxKind = "process" | "data" | "decision" | "start" | "external";

const GAP_H = 36;
const GAP_V = 28;
const BOX_H = 58;
const ZONE_GAP = 48;
const ZONE_HDR = 48;
const ZONE_PAD = 18;

const kindFill: Record<BoxKind, [string, string]> = {
  process: ["var(--fc-process)", "var(--fc-process-border)"],
  data: ["var(--fc-data)", "var(--fc-data-border)"],
  decision: ["var(--fc-decision)", "var(--fc-decision-border)"],
  start: ["var(--fc-start)", "var(--fc-start-border)"],
  external: ["var(--fc-external)", "var(--fc-external-border)"],
};

type Pt = { x: number; y: number };

function anchor(r: Rect, side: Side): Pt {
  const cx = r.x + r.w / 2;
  const cy = r.y + r.h / 2;
  if (side === "n") return { x: cx, y: r.y };
  if (side === "s") return { x: cx, y: r.y + r.h };
  if (side === "e") return { x: r.x + r.w, y: cy };
  return { x: r.x, y: cy };
}

function diamondPt(cx: number, cy: number, size: number, side: Side): Pt {
  const s = size / 2;
  if (side === "n") return { x: cx, y: cy - s };
  if (side === "s") return { x: cx, y: cy + s };
  if (side === "e") return { x: cx + s, y: cy };
  return { x: cx - s, y: cy };
}

function routeVH(a: Pt, b: Pt): string {
  if (a.x === b.x || a.y === b.y) return `M ${a.x} ${a.y} L ${b.x} ${b.y}`;
  return `M ${a.x} ${a.y} L ${a.x} ${b.y} L ${b.x} ${b.y}`;
}

function straight(a: Pt, b: Pt): string {
  return `M ${a.x} ${a.y} L ${b.x} ${b.y}`;
}

/** 水平相邻：右缘 → 左缘 */
function linkH(from: Rect, to: Rect): string {
  return straight(anchor(from, "e"), anchor(to, "w"));
}

/** 垂直接相邻：下缘 → 上缘 */
function linkV(from: Rect, to: Rect): string {
  return straight(anchor(from, "s"), anchor(to, "n"));
}

/** 从上方框经水平走廊连到下方框（不穿过中间区域） */
function linkDownCorridor(from: Rect, to: Rect, corridorY: number): string {
  const a = anchor(from, "s");
  const b = anchor(to, "n");
  return `M ${a.x} ${a.y} L ${a.x} ${corridorY} L ${b.x} ${corridorY} L ${b.x} ${b.y}`;
}

function stackRight(prev: Rect, w: number, h = BOX_H): Rect {
  return { x: prev.x + prev.w + GAP_H, y: prev.y, w, h };
}

function FlowBox({ rect, lines, kind = "process" }: { rect: Rect; lines: string[]; kind?: BoxKind }) {
  const [fill, stroke] = kindFill[kind];
  return (
    <g>
      <rect x={rect.x} y={rect.y} width={rect.w} height={rect.h} rx={8} fill={fill} stroke={stroke} strokeWidth={1.5} />
      <foreignObject x={rect.x + 8} y={rect.y + 6} width={rect.w - 16} height={rect.h - 12}>
        <div className="fc-fo">
          {lines.map((line) => (
            <span key={line}>{line}</span>
          ))}
        </div>
      </foreignObject>
    </g>
  );
}

function FlowDiamond({ cx, cy, size, label }: { cx: number; cy: number; size: number; label: string }) {
  const s = size / 2;
  return (
    <g>
      <polygon
        points={`${cx},${cy - s} ${cx + s},${cy} ${cx},${cy + s} ${cx - s},${cy}`}
        fill="var(--fc-decision)"
        stroke="var(--fc-decision-border)"
        strokeWidth={1.5}
      />
      <text x={cx} y={cy + 5} textAnchor="middle" className="fc-text">
        {label}
      </text>
    </g>
  );
}

function FlowLink({
  d,
  label,
  lx,
  ly,
  dashed,
  noArrow,
}: {
  d: string;
  label?: string;
  lx?: number;
  ly?: number;
  dashed?: boolean;
  noArrow?: boolean;
}) {
  return (
    <g>
      <path
        d={d}
        fill="none"
        stroke="var(--fc-arrow)"
        strokeWidth={1.8}
        strokeDasharray={dashed ? "6 4" : undefined}
        markerEnd={noArrow ? undefined : "url(#fc-arrowhead)"}
      />
      {label != null && lx != null && ly != null && (
        <text x={lx} y={ly} textAnchor="middle" className="fc-sub">
          {label}
        </text>
      )}
    </g>
  );
}

function ZoneFrame({ rect, label }: { rect: Rect; label: string }) {
  const sepY = rect.y + ZONE_HDR - 6;
  return (
    <g>
      <rect x={rect.x} y={rect.y} width={rect.w} height={rect.h} rx={10} fill="var(--bg-elevated)" stroke="var(--border)" strokeWidth={1} />
      <text x={rect.x + 14} y={rect.y + 30} className="fc-zone">
        {label}
      </text>
      <line x1={rect.x + 10} y1={sepY} x2={rect.x + rect.w - 10} y2={sepY} stroke="var(--border)" strokeWidth={1} opacity={0.7} />
    </g>
  );
}

function Defs() {
  return (
    <defs>
      <marker id="fc-arrowhead" viewBox="0 0 10 10" markerWidth="8" markerHeight="8" refX="9" refY="5" orient="auto" markerUnits="userSpaceOnUse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--fc-arrow)" />
      </marker>
    </defs>
  );
}

/** 水平全景：四行从左到右 */
function UnifiedSystemDiagram() {
  const { t } = useLocale();
  const fc = t.system.flowcharts;
  const arch = fc.arch.nodes;
  const loop = fc.loop.nodes;
  const mem = fc.memory.nodes;
  const tl = fc.timeline.nodes;

  const W = 1420;
  const M = 16;

  let y = M;

  /* ① 架构 */
  const archZoneY = y;
  const row1y = archZoneY + ZONE_HDR;
  const client: Rect = { x: 40, y: row1y, w: 150, h: BOX_H };
  const ws = stackRight(client, 138);
  const api = stackRight(ws, 172);
  const infraY = row1y + BOX_H + GAP_V;
  const db: Rect = { x: api.x - 20, y: infraY, w: 130, h: 50 };
  const cache = stackRight(db, 130, 50);
  const llm = stackRight(cache, 150, 50);
  const archZoneH = infraY + 50 + ZONE_PAD - archZoneY;
  const archZone: Rect = { x: M, y: archZoneY, w: W - M * 2, h: archZoneH };
  y = archZoneY + archZoneH + ZONE_GAP;

  /* ② Agent */
  const agentZoneY = y;
  const initY = agentZoneY + ZONE_HDR;
  const start: Rect = { x: 40, y: initY, w: 108, h: BOX_H };
  const seed = stackRight(start, 152);
  const plan = stackRight(seed, 152);

  const cycleY = initY + BOX_H + GAP_V + 10;
  const cycleH = 118;
  const flowY = cycleY + 32;
  const perceive: Rect = { x: 52, y: flowY, w: 128, h: BOX_H };
  const retrieve = stackRight(perceive, 128);
  const react = stackRight(retrieve, 118);
  const act = stackRight(react, 118);
  const diamondSize = 58;
  const reflectCx = act.x + act.w + GAP_H + diamondSize / 2;
  const reflectCy = flowY + BOX_H / 2;
  const reflectBox: Rect = { x: reflectCx + diamondSize / 2 + GAP_H, y: flowY, w: 128, h: BOX_H };
  const loopRailY = cycleY + cycleH + 8;
  const agentZoneH = loopRailY + 28 - agentZoneY;
  const agentZone: Rect = { x: M, y: agentZoneY, w: W - M * 2, h: agentZoneH };
  y = agentZoneY + agentZoneH + ZONE_GAP;

  /* ③ 记忆 */
  const memZoneY = y;
  const memY = memZoneY + ZONE_HDR;
  const stream: Rect = { x: retrieve.x, y: memY, w: 128, h: BOX_H };
  const recency = stackRight(stream, 100, 50);
  const importance = stackRight(recency, 108, 50);
  const relevance = stackRight(importance, 108, 50);
  const normalize = stackRight(relevance, 132, BOX_H);
  const topK = stackRight(normalize, 108, BOX_H);
  const memZoneH = memY + BOX_H + ZONE_PAD - memZoneY;
  const memZone: Rect = { x: M, y: memZoneY, w: W - M * 2, h: memZoneH };
  const gapMidY = agentZoneY + agentZoneH + ZONE_GAP / 2;
  y = memZoneY + memZoneH + ZONE_GAP;

  /* ④ 世界线 */
  const tlZoneY = y;
  const tlY = tlZoneY + ZONE_HDR;
  const userSpeak: Rect = { x: 40, y: tlY, w: 120, h: BOX_H };
  const timelineWrite = stackRight(userSpeak, 136);
  const npc1 = stackRight(timelineWrite, 120);
  const npc2 = stackRight(npc1, 120);
  const display = stackRight(npc2, 108);
  const tlZoneH = tlY + BOX_H + ZONE_PAD - tlZoneY;
  const tlZone: Rect = { x: M, y: tlZoneY, w: W - M * 2, h: tlZoneH };
  const H = tlZoneY + tlZoneH + M;

  const cycleRect: Rect = { x: 36, y: cycleY, w: reflectBox.x + reflectBox.w - 24, h: cycleH };
  const planCorridorY = cycleY + 6;
  const infraBusY = infraY - 12;
  const loopExitX = reflectCx - diamondSize / 2 - 24;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="fc-svg fc-svg-unified" role="img" aria-label={fc.unified.title}>
      <Defs />

      {/* —— 连线层（在节点下方，止于边缘） —— */}
      <g className="fc-links">
        <FlowLink d={linkH(client, ws)} />
        <FlowLink d={linkH(ws, api)} />
        <FlowLink d={straight(anchor(api, "s"), { x: anchor(api, "s").x, y: infraBusY })} noArrow />
        <line x1={anchor(db, "n").x} y1={infraBusY} x2={anchor(llm, "n").x} y2={infraBusY} stroke="var(--fc-arrow)" strokeWidth={1.8} />
        <FlowLink d={straight({ x: anchor(db, "n").x, y: infraBusY }, anchor(db, "n"))} />
        <FlowLink d={straight({ x: anchor(cache, "n").x, y: infraBusY }, anchor(cache, "n"))} />
        <FlowLink d={straight({ x: anchor(llm, "n").x, y: infraBusY }, anchor(llm, "n"))} />

        <FlowLink d={linkH(start, seed)} />
        <FlowLink d={linkH(seed, plan)} />
        <FlowLink d={linkDownCorridor(plan, perceive, planCorridorY)} />

        <FlowLink d={linkH(perceive, retrieve)} />
        <FlowLink d={linkH(retrieve, react)} />
        <FlowLink d={linkH(react, act)} />
        <FlowLink d={straight(anchor(act, "e"), diamondPt(reflectCx, reflectCy, diamondSize, "w"))} />
        <FlowLink d={straight(diamondPt(reflectCx, reflectCy, diamondSize, "e"), anchor(reflectBox, "w"))} />
        <FlowLink
          d={`M ${diamondPt(reflectCx, reflectCy, diamondSize, "w").x} ${reflectCy} L ${loopExitX} ${reflectCy} L ${loopExitX} ${loopRailY} L ${anchor(perceive, "w").x} ${loopRailY} L ${anchor(perceive, "w").x} ${anchor(perceive, "w").y}`}
          label={loop.loopBack}
          lx={loopExitX - 6}
          ly={loopRailY + 14}
        />

        <FlowLink
          d={linkV(retrieve, stream)}
          label={fc.unified.links.detail}
          lx={retrieve.x + retrieve.w / 2}
          ly={agentZoneY + agentZoneH + ZONE_GAP / 2 + 4}
          dashed
        />
        <FlowLink d={linkH(stream, recency)} />
        <FlowLink d={linkH(recency, importance)} />
        <FlowLink d={linkH(importance, relevance)} />
        <FlowLink d={linkH(relevance, normalize)} />
        <FlowLink d={linkH(normalize, topK)} />
        <FlowLink d={routeVH(anchor(topK, "n"), { x: anchor(react, "s").x, y: gapMidY })} noArrow />
        <FlowLink
          d={straight({ x: anchor(react, "s").x, y: gapMidY }, anchor(react, "s"))}
          label={fc.unified.links.toReact}
          lx={anchor(react, "s").x + 36}
          ly={gapMidY - 8}
          dashed
        />

        <FlowLink d={linkH(userSpeak, timelineWrite)} label={tl.shared} lx={(userSpeak.x + timelineWrite.x + timelineWrite.w) / 2} ly={tlY - 12} dashed />
        <FlowLink d={linkH(timelineWrite, npc1)} />
        <FlowLink d={linkH(npc1, npc2)} />
        <FlowLink d={linkH(npc2, display)} />
      </g>

      {/* —— 节点层（覆盖连线，避免穿入框内） —— */}
      <g className="fc-nodes">
      {/* ① 架构 */}
      <ZoneFrame rect={archZone} label={fc.unified.zones.arch} />
      <FlowBox rect={client} lines={arch.client.split("\n")} kind="external" />
      <FlowBox rect={ws} lines={[arch.ws]} kind="process" />
      <FlowBox rect={api} lines={arch.api.split("\n")} kind="process" />
      <FlowBox rect={db} lines={[arch.db]} kind="data" />
      <FlowBox rect={cache} lines={[arch.cache]} kind="data" />
      <FlowBox rect={llm} lines={arch.llm.split("\n")} kind="data" />

      {/* ② Agent */}
      <ZoneFrame rect={agentZone} label={fc.unified.zones.agent} />
      <FlowBox rect={start} lines={[loop.start]} kind="start" />
      <FlowBox rect={seed} lines={loop.seed.split("\n")} kind="process" />
      <FlowBox rect={plan} lines={loop.plan.split("\n")} kind="process" />
      <rect x={cycleRect.x} y={cycleRect.y} width={cycleRect.w} height={cycleRect.h} rx={8} fill="var(--bg-surface)" stroke="var(--border)" strokeDasharray="5 4" />
      <text x={cycleRect.x + 12} y={cycleRect.y + 22} className="fc-sub">
        {fc.loop.cycleLabel}
      </text>
      <FlowBox rect={perceive} lines={loop.perceive.split("\n")} kind="process" />
      <FlowBox rect={retrieve} lines={loop.retrieve.split("\n")} kind="process" />
      <FlowBox rect={react} lines={loop.react.split("\n")} kind="process" />
      <FlowBox rect={act} lines={loop.act.split("\n")} kind="process" />
      <FlowDiamond cx={reflectCx} cy={reflectCy} size={diamondSize} label={loop.reflectGate} />
      <text x={reflectCx} y={reflectCy - diamondSize / 2 - 6} textAnchor="middle" className="fc-sub">
        {loop.no}
      </text>
      <text x={reflectCx} y={reflectCy + diamondSize / 2 + 14} textAnchor="middle" className="fc-sub">
        {loop.yes}
      </text>
      <FlowBox rect={reflectBox} lines={loop.reflect.split("\n")} kind="data" />

      {/* ③ 记忆 */}
      <ZoneFrame rect={memZone} label={fc.unified.zones.memory} />
      <FlowBox rect={stream} lines={mem.stream.split("\n")} kind="data" />
      <FlowBox rect={recency} lines={[mem.recency]} kind="process" />
      <FlowBox rect={importance} lines={[mem.importance]} kind="process" />
      <FlowBox rect={relevance} lines={[mem.relevance]} kind="process" />
      <FlowBox rect={normalize} lines={mem.normalize.split("\n")} kind="process" />
      <text x={normalize.x + normalize.w / 2} y={normalize.y - 8} textAnchor="middle" className="fc-formula">
        α·R + β·I + γ·Rel
      </text>
      <FlowBox rect={topK} lines={mem.score.split("\n")} kind="process" />

      {/* ④ 世界线 */}
      <ZoneFrame rect={tlZone} label={fc.unified.zones.timeline} />
      <FlowBox rect={userSpeak} lines={[tl.userSpeak]} kind="external" />
      <FlowBox rect={timelineWrite} lines={[tl.timelineWrite]} kind="data" />
      <FlowBox rect={npc1} lines={[tl.npc1]} kind="process" />
      <FlowBox rect={npc2} lines={[tl.npc2]} kind="process" />
      <FlowBox rect={display} lines={[tl.display]} kind="start" />
      </g>
    </svg>
  );
}

export default function SystemFlowcharts() {
  const { t } = useLocale();
  const fc = t.system.flowcharts;

  return (
    <div className="system-flowcharts">
      <section className="system-card fc-section">
        <h2>{fc.unified.title}</h2>
        <p className="fc-desc">{fc.unified.desc}</p>
        <div className="fc-wrap fc-wrap-unified">
          <UnifiedSystemDiagram />
        </div>
        <p className="fc-legend-note">{fc.unified.legendNote}</p>
        <p className="fc-legend">
          <span className="fc-legend-item">
            <i className="fc-swatch fc-swatch-process" />
            {fc.unified.legend.process}
          </span>
          <span className="fc-legend-item">
            <i className="fc-swatch fc-swatch-data" />
            {fc.unified.legend.data}
          </span>
          <span className="fc-legend-item">
            <i className="fc-swatch fc-swatch-decision" />
            {fc.unified.legend.decision}
          </span>
          <span className="fc-legend-item">
            <i className="fc-swatch fc-swatch-start" />
            {fc.unified.legend.start}
          </span>
          <span className="fc-legend-item">
            <i className="fc-swatch fc-swatch-external" />
            {fc.unified.legend.external}
          </span>
        </p>
      </section>
    </div>
  );
}
