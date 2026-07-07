/**
 * RoomMind Architecture Diagram
 * 完全用 React 组件构建，所有节点、连线、文字均为独立配置。
 * 后期调整：修改下方 CONFIG 对象即可，无需触碰渲染逻辑。
 */

// ─────────────────────────────────────────
// CONFIG — 修改这里来调整所有内容
// ─────────────────────────────────────────

const COLORS = {
  gray:       { fill: "#f5f5f4", stroke: "#a8a29e", title: "#1c1917", sub: "#78716c" },
  purple:     { fill: "#ede9fe", stroke: "#7c3aed", title: "#3730a3", sub: "#5b21b6" },
  teal:       { fill: "#ccfbf1", stroke: "#0d9488", title: "#134e4a", sub: "#0f766e" },
  tealStrong: { fill: "#ccfbf1", stroke: "#0d9488", title: "#134e4a", sub: "#0f766e", strokeWidth: 1.5 },
  amber:      { fill: "#fef3c7", stroke: "#d97706", title: "#92400e", sub: "#b45309" },
  blue:       { fill: "#dbeafe", stroke: "#2563eb", title: "#1e40af", sub: "#3b82f6" },
  section:    { fill: "none",    stroke: "#d6d3d1" },
  inner:      { fill: "none",    stroke: "#e7e5e4" },
  connector:  "#a8a29e",
  text:       "#1c1917",
  muted:      "#78716c",
  faint:      "#a8a29e",
  divider:    "#e7e5e4",
};

// Section bounding boxes
const SECTIONS = {
  A: { x: 30, y: 58,  w: 620, h: 90,  label: "A  Infrastructure" },
  B: { x: 30, y: 166, w: 620, h: 388, label: "B  Agent loop — per NPC, per turn" },
  C: { x: 30, y: 572, w: 620, h: 162, label: "C  Memory retrieval — retrieve detail" },
  D: { x: 30, y: 754, w: 620, h: 140, label: "D  World line and session flow" },
};

// All boxes: { id, x, y, w, h, color, title, sub? }
const BOXES: Record<string, { x: number; y: number; w: number; h: number; color: keyof typeof COLORS; title: string; sub?: string }> = {
  // A
  client:       { x: 46,  y: 82,  w: 112, h: 52, color: "gray",       title: "React + Three.js",     sub: "client · :5183" },
  gateway:      { x: 188, y: 82,  w: 120, h: 52, color: "gray",       title: "WebSocket / REST",      sub: "bidirectional" },
  orchestrator: { x: 338, y: 82,  w: 132, h: 52, color: "purple",     title: "FastAPI orchestrator",  sub: ":8810 · generative mode" },
  pg:           { x: 498, y: 82,  w: 52,  h: 52, color: "gray",       title: "PG",                   sub: ":5432" },
  redis:        { x: 556, y: 82,  w: 56,  h: 52, color: "gray",       title: "Redis",                sub: ":6379" },
  llm:          { x: 618, y: 82,  w: 28,  h: 52, color: "gray",       title: "LLM",                  sub: "" },
  // B session-start row
  sessionStart: { x: 46,  y: 208, w: 98,  h: 40, color: "tealStrong", title: "Session start",         sub: "" },
  seedMemory:   { x: 170, y: 208, w: 136, h: 40, color: "teal",       title: "Seed memory",           sub: "identity · role · redlines" },
  initialPlan:  { x: 332, y: 208, w: 136, h: 40, color: "teal",       title: "Initial plan",          sub: "LLM · from seed · imp 8.5" },
  // B per-turn cycle
  perceive:     { x: 60,  y: 286, w: 108, h: 52, color: "purple",     title: "Perceive",              sub: "world-line events" },
  retrieve:     { x: 194, y: 286, w: 108, h: 52, color: "purple",     title: "Retrieve",              sub: "3-factor scoring" },
  react:        { x: 328, y: 286, w: 108, h: 52, color: "purple",     title: "React",                 sub: "decision LLM (JSON)" },
  act:          { x: 462, y: 286, w: 108, h: 52, color: "purple",     title: "Act",                   sub: "speak / wait / plan" },
  reflection:   { x: 534, y: 466, w: 132, h: 52, color: "amber",      title: "Reflection",            sub: "higher-order inference" },
  // C
  memStream:    { x: 46,  y: 596, w: 110, h: 126, color: "gray",      title: "Memory stream",         sub: "" },
  scoreR:       { x: 182, y: 614, w: 88,  h: 90,  color: "blue",      title: "R",                     sub: "" },
  scoreI:       { x: 292, y: 614, w: 88,  h: 90,  color: "blue",      title: "I",                     sub: "" },
  scoreRel:     { x: 402, y: 614, w: 88,  h: 90,  color: "blue",      title: "Rel",                   sub: "" },
  formula:      { x: 516, y: 614, w: 120, h: 44,  color: "purple",    title: "α·R + β·I + γ·Rel",    sub: "min-max normalised" },
  topK:         { x: 516, y: 676, w: 120, h: 40,  color: "purple",    title: "Weighted top-K",        sub: "k=10 · plan pinned" },
  // D
  userSpeaks:   { x: 46,  y: 780, w: 82,  h: 44, color: "gray",       title: "User speaks",           sub: "user_speech" },
  writeTimeline:{ x: 150, y: 780, w: 90,  h: 44, color: "gray",       title: "Write timeline",        sub: "turn_id · tick" },
  npc1:         { x: 262, y: 780, w: 92,  h: 44, color: "purple",     title: "NPC-1 decide",          sub: "tick < own tick" },
  npc2:         { x: 376, y: 780, w: 92,  h: 44, color: "purple",     title: "NPC-2 decide",          sub: "sees NPC-1 action" },
  fallback:     { x: 490, y: 780, w: 82,  h: 44, color: "amber",      title: "Fallback",              sub: "force if empty" },
  chatUI:       { x: 594, y: 780, w: 50,  h: 44, color: "teal",       title: "Chat UI",               sub: "npc_delta" },
};

// Footer rows
const FOOTER = {
  llm: [
    { label: "decision",   value: "Qwen2.5-7B (agent JSON)",  x: 112 },
    { label: "npc",        value: "Kimi-K2.5 (speech render)", x: 318 },
    { label: "reflection", value: "Qwen2.5-7B",               x: 496 },
  ],
  meta: "phases: opening → discovery → bargaining → closing  ·  provider: SiliconFlow / Ollama",
};

// ─────────────────────────────────────────
// PRIMITIVE COMPONENTS
// ─────────────────────────────────────────

function Box({ id }: { id: string }) {
  const b = BOXES[id];
  const c = COLORS[b.color] as typeof COLORS["gray"] & { strokeWidth?: number };
  const cx = b.x + b.w / 2;
  const titleY = b.sub ? b.y + b.h * 0.38 : b.y + b.h / 2;
  const subY   = b.y + b.h * 0.72;
  const isLLM  = id === "llm";

  return (
    <g>
      <rect
        x={b.x} y={b.y} width={b.w} height={b.h} rx={4}
        fill={c.fill} stroke={c.stroke}
        strokeWidth={c.strokeWidth ?? 0.75}
      />
      {isLLM ? (
        <text
          x={cx} y={b.y + b.h / 2}
          textAnchor="middle" dominantBaseline="central"
          fontSize={10} fontWeight={500} fill={c.title}
          transform={`rotate(-90 ${cx} ${b.y + b.h / 2})`}
        >LLM</text>
      ) : (
        <>
          <text x={cx} y={titleY} textAnchor="middle" dominantBaseline="central"
            fontSize={12} fontWeight={500} fill={c.title}>
            {b.title}
          </text>
          {b.sub && (
            <text x={cx} y={subY} textAnchor="middle" dominantBaseline="central"
              fontSize={10} fill={c.sub}>
              {b.sub}
            </text>
          )}
        </>
      )}
    </g>
  );
}

// Horizontal arrow between two box IDs (right edge → left edge, same Y center)
function HArrow({ from, to, color = COLORS.connector, markerId = "arr" }: {
  from: string; to: string; color?: string; markerId?: string;
}) {
  const a = BOXES[from], b = BOXES[to];
  const y = a.y + a.h / 2;
  return (
    <line
      x1={a.x + a.w} y1={y} x2={b.x} y2={y}
      stroke={color} strokeWidth={0.75}
      markerEnd={`url(#${markerId})`}
    />
  );
}

// Generic path arrow
function PathArrow({ d, color = COLORS.connector, dashed = false, markerId = "arr" }: {
  d: string; color?: string; dashed?: boolean; markerId?: string;
}) {
  return (
    <path
      d={d} fill="none" stroke={color} strokeWidth={0.75}
      strokeDasharray={dashed ? "4 2" : undefined}
      markerEnd={`url(#${markerId})`}
    />
  );
}

// Section container (dashed border + label)
function Section({ id }: { id: keyof typeof SECTIONS }) {
  const s = SECTIONS[id];
  return (
    <>
      <rect x={s.x} y={s.y} width={s.w} height={s.h} rx={6}
        fill="none" stroke={COLORS.section.stroke} strokeWidth={0.75} strokeDasharray="5 3"/>
      <text x={s.x + 12} y={s.y + 16} fontSize={11} fill={COLORS.muted}>{s.label}</text>
    </>
  );
}

// Diamond (Reflect?)
function Diamond({ cx, cy, r = 28, color = COLORS.amber }: {
  cx: number; cy: number; r?: number; color?: typeof COLORS["amber"];
}) {
  return (
    <g>
      <rect
        x={cx - r} y={cy - r} width={r * 2} height={r * 2} rx={3}
        fill={color.fill} stroke={color.stroke} strokeWidth={1}
        transform={`rotate(45 ${cx} ${cy})`}
      />
      <text x={cx} y={cy - 6} textAnchor="middle" fontSize={11} fontWeight={500} fill={color.title}>Reflect</text>
      <text x={cx} y={cy + 8} textAnchor="middle" fontSize={10} fill={color.title}>?</text>
    </g>
  );
}

// Score card (R / I / Rel) with custom inner content
function ScoreCard({ id, sym, name, line1, line2 }: {
  id: string; sym: string; name: string; line1: string; line2: string;
}) {
  const b = BOXES[id];
  const c = COLORS[b.color] as typeof COLORS["blue"];
  const cx = b.x + b.w / 2;
  return (
    <g>
      <rect x={b.x} y={b.y} width={b.w} height={b.h} rx={4}
        fill={c.fill} stroke={c.stroke} strokeWidth={0.75}/>
      <text x={cx} y={b.y + 28} textAnchor="middle" fontSize={16} fontWeight={500} fill={c.title}>{sym}</text>
      <text x={cx} y={b.y + 46} textAnchor="middle" fontSize={11} fontWeight={500} fill="#1e3a8a">{name}</text>
      <text x={cx} y={b.y + 61} textAnchor="middle" fontSize={10} fill={c.title}>{line1}</text>
      <text x={cx} y={b.y + 76} textAnchor="middle" fontSize={10} fill={c.sub}>{line2}</text>
    </g>
  );
}

// ─────────────────────────────────────────
// MAIN DIAGRAM
// ─────────────────────────────────────────

export default function RoomMindArchitecture() {
  const VIEWBOX_H = 920;

  return (
    <svg
      width="100%"
      viewBox={`0 0 680 ${VIEWBOX_H}`}
      xmlns="http://www.w3.org/2000/svg"
      className="roommind-arch-svg"
      style={{ fontFamily: "'Inter','Helvetica Neue',Arial,sans-serif", background: "#ffffff", display: "block" }}
    >
      {/* ── Marker defs ── */}
      <defs>
        {(["arr","arr-purple","arr-teal","arr-amber"] as const).map((id, i) => {
          const colors = [COLORS.connector, COLORS.purple.stroke, COLORS.teal.stroke, COLORS.amber.stroke];
          return (
            <marker key={id} id={id} viewBox="0 0 10 10" refX="8" refY="5"
              markerWidth="5" markerHeight="5" orient="auto-start-reverse">
              <path d="M2 1L8 5L2 9" fill="none" stroke={colors[i]}
                strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </marker>
          );
        })}
      </defs>

      {/* ── Title ── */}
      <text x={340} y={26} textAnchor="middle" fontSize={14} fontWeight={500} fill={COLORS.text}>
        RoomMind — system architecture
      </text>
      <text x={340} y={44} textAnchor="middle" fontSize={11} fill={COLORS.muted}>
        Stanford generative agents · multi-NPC negotiation simulation
      </text>

      {/* ══════════ A  Infrastructure ══════════ */}
      <Section id="A"/>
      <Box id="client"/>
      <HArrow from="client" to="gateway"/>
      <Box id="gateway"/>
      <HArrow from="gateway" to="orchestrator"/>
      <Box id="orchestrator"/>
      <HArrow from="orchestrator" to="pg"/>
      <Box id="pg"/>
      <Box id="redis"/>
      <Box id="llm"/>

      {/* ══════════ B  Agent loop ══════════ */}
      <Section id="B"/>

      {/* B1 session-start row */}
      <text x={46} y={200} fontSize={10} fill={COLORS.muted}>
        ① session start (once per session, idempotent)
      </text>
      <Box id="sessionStart"/>
      <HArrow from="sessionStart" to="seedMemory" color={COLORS.teal.stroke} markerId="arr-teal"/>
      <Box id="seedMemory"/>
      <HArrow from="seedMemory" to="initialPlan" color={COLORS.teal.stroke} markerId="arr-teal"/>
      <Box id="initialPlan"/>
      {/* annotation after initialPlan */}
      <line x1={468} y1={228} x2={490} y2={228} stroke={COLORS.section.stroke} strokeWidth={0.75} strokeDasharray="3 2"/>
      <text x={494} y={224} fontSize={10} fill={COLORS.muted}>drives all</text>
      <text x={494} y={237} fontSize={10} fill={COLORS.muted}>future acts</text>

      {/* B2 per-turn inner box */}
      <rect x={46} y={262} width={608} height={278} rx={5}
        fill="none" stroke={COLORS.inner.stroke} strokeWidth={0.75}/>
      <text x={58} y={278} fontSize={10} fill={COLORS.muted}>② per-turn cycle</text>

      <Box id="perceive"/>
      <HArrow from="perceive" to="retrieve" color={COLORS.purple.stroke} markerId="arr-purple"/>
      <Box id="retrieve"/>
      <HArrow from="retrieve" to="react" color={COLORS.purple.stroke} markerId="arr-purple"/>
      <Box id="react"/>
      <HArrow from="react" to="act" color={COLORS.purple.stroke} markerId="arr-purple"/>
      <Box id="act"/>

      {/* Act → right → down to diamond */}
      <PathArrow d="M570 312 L600 312 L600 390"/>

      {/* Reflect diamond */}
      <Diamond cx={600} cy={418}/>
      <text x={616} y={388} fontSize={10} fill={COLORS.muted}>No</text>

      {/* Yes → Reflection */}
      <line x1={600} y1={442} x2={600} y2={464}
        stroke={COLORS.amber.stroke} strokeWidth={0.75} markerEnd="url(#arr-amber)"/>
      <text x={604} y={458} fontSize={10} fill={COLORS.muted}>Yes</text>
      <Box id="reflection"/>

      {/* Reflection → memory stream feedback (dashed) */}
      <PathArrow
        d="M534 492 L510 492 L510 312 L460 312"
        color={COLORS.amber.stroke} dashed markerId="arr-amber"
      />
      <text x={514} y={308} fontSize={10} fill={COLORS.amber.sub}>→ memory stream</text>

      {/* Plan-update dashed feedback (Act → React) */}
      <PathArrow d="M516 338 L516 356 L382 356 L382 338" dashed/>
      <text x={450} y={372} textAnchor="middle" fontSize={10} fill={COLORS.muted}>
        plan update feeds next decision
      </text>

      <text x={58} y={498} fontSize={10} fill={COLORS.muted}>
        Σ importance ≥ 18 triggers reflection
      </text>

      {/* ══════════ C  Memory retrieval ══════════ */}
      <Section id="C"/>

      {/* Memory stream box with multi-line content */}
      {(() => {
        const b = BOXES.memStream;
        const cx = b.x + b.w / 2;
        const rows = [
          { label: "seed",        imp: "imp 7–9" },
          { label: "observation", imp: "3–8" },
          { label: "reflection",  imp: "7–9" },
          { label: "plan",        imp: "8.5 (pinned)" },
          { label: "action",      imp: "3–7" },
        ];
        return (
          <g>
            <rect x={b.x} y={b.y} width={b.w} height={b.h} rx={4}
              fill={COLORS.gray.fill} stroke={COLORS.gray.stroke} strokeWidth={0.75}/>
            <text x={cx} y={b.y + 18} textAnchor="middle" fontSize={11} fontWeight={500} fill={COLORS.text}>
              Memory stream
            </text>
            {rows.map((r, i) => (
              <text key={r.label} x={cx} y={b.y + 34 + i * 16}
                textAnchor="middle" fontSize={10} fill={COLORS.muted}>
                {r.label}  {r.imp}
              </text>
            ))}
            <text x={cx} y={b.y + 116} textAnchor="middle" fontSize={10} fill={COLORS.faint}>
              all nodes, turn-indexed
            </text>
          </g>
        );
      })()}

      <line x1={156} y1={659} x2={180} y2={659}
        stroke={COLORS.connector} strokeWidth={0.75} markerEnd="url(#arr)"/>

      <ScoreCard id="scoreR"   sym="R"   name="Recency"    line1="e^(−Δturn/8)"     line2="last-access decay"/>
      <text x={280} y={663} textAnchor="middle" fontSize={14} fontWeight={500} fill={COLORS.muted}>+</text>
      <ScoreCard id="scoreI"   sym="I"   name="Importance" line1="1–10, write-time"  line2="never recomputed"/>
      <text x={390} y={663} textAnchor="middle" fontSize={14} fontWeight={500} fill={COLORS.muted}>+</text>
      <ScoreCard id="scoreRel" sym="Rel" name="Relevance"  line1="synonym-expanded"  line2="token overlap"/>

      <line x1={490} y1={659} x2={514} y2={659}
        stroke={COLORS.connector} strokeWidth={0.75} markerEnd="url(#arr)"/>
      <Box id="formula"/>
      <line x1={576} y1={658} x2={576} y2={674}
        stroke={COLORS.purple.stroke} strokeWidth={0.75} markerEnd="url(#arr-purple)"/>
      <Box id="topK"/>

      {/* top-K → React context (dashed feedback) */}
      <PathArrow d="M576 716 L576 736 L36 736 L36 312 L58 312" dashed/>
      <text x={40} y={732} fontSize={10} fill={COLORS.muted}>top-K → React context</text>

      {/* ══════════ D  World line ══════════ */}
      <Section id="D"/>
      <Box id="userSpeaks"/>
      <HArrow from="userSpeaks" to="writeTimeline"/>
      <Box id="writeTimeline"/>
      <HArrow from="writeTimeline" to="npc1"/>
      <Box id="npc1"/>
      <HArrow from="npc1" to="npc2" color={COLORS.purple.stroke} markerId="arr-purple"/>
      <Box id="npc2"/>
      <HArrow from="npc2" to="fallback"/>
      <Box id="fallback"/>
      <HArrow from="fallback" to="chatUI" color={COLORS.amber.stroke} markerId="arr-amber"/>
      <Box id="chatUI"/>

      {/* D annotation row */}
      <text x={46}  y={842} fontSize={10} fill={COLORS.muted}>speak quota: max 2/turn</text>
      <text x={188} y={842} fontSize={10} fill={COLORS.muted}>order: mentioned → dispatch_rule → sort_order</text>
      <text x={456} y={842} fontSize={10} fill={COLORS.muted}>transport: WebSocket / REST fallback</text>

      {/* ══════════ Footer ══════════ */}
      <line x1={30} y1={858} x2={650} y2={858} stroke={COLORS.divider} strokeWidth={0.75}/>
      <text x={40} y={873} fontSize={10} fill={COLORS.muted}>LLM roles —</text>
      {FOOTER.llm.map(item => (
        <text key={item.label} x={item.x} y={873} fontSize={10} fill={COLORS.muted}>
          {item.label}: {item.value}
        </text>
      ))}
      <text x={40} y={890} fontSize={10} fill={COLORS.faint}>{FOOTER.meta}</text>
    </svg>
  );
}
