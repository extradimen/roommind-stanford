import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import AppShell from "../components/AppShell";
import { BlindReviewQueue, getBlindReviewQueue, submitBlindReview } from "../api";

type Locale = "bilingual" | "zh-CN" | "en";

const scoreOptions = [1, 2, 3, 4, 5, 6, 7];

function mean(values: number[]): number {
  return Math.round((values.reduce((sum, value) => sum + value, 0) / values.length) * 100) / 100;
}

export default function ExpertReviewPage() {
  const { batchUuid = "" } = useParams();
  const [queue, setQueue] = useState<BlindReviewQueue | null>(null);
  const [index, setIndex] = useState(0);
  const [locale, setLocale] = useState<Locale>("bilingual");
  const [reviewerId, setReviewerId] = useState("");
  const [expertise, setExpertise] = useState("");
  const [experienceYears, setExperienceYears] = useState("");
  const [indicatorRatings, setIndicatorRatings] = useState<Record<string, number>>({});
  const [dimensionEvidence, setDimensionEvidence] = useState<Record<string, string>>({});
  const [overall, setOverall] = useState(4);
  const [notes, setNotes] = useState("");
  const [fullTranscript, setFullTranscript] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getBlindReviewQueue(batchUuid).then(setQueue).catch((err) => setError(String(err)));
  }, [batchUuid]);

  const packet = queue?.packets[index];
  const rubricEntries = useMemo(() => Object.entries(packet?.rubric || {}), [packet]);

  useEffect(() => {
    if (!packet) return;
    setIndicatorRatings(Object.fromEntries(
      Object.values(packet.rubric).flatMap((rubric) => rubric.indicators.map(([key]) => [key, 4])),
    ));
    setDimensionEvidence({});
    setOverall(4);
    setNotes("");
    setMessage("");
    setFullTranscript(false);
  }, [packet?.run_label]);

  function label(en: string, zh: string) {
    if (locale === "en") return en;
    if (locale === "zh-CN") return zh;
    return <><span>{zh}</span><small>{en}</small></>;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!packet || !reviewerId.trim()) {
      setError("请输入评审编号。 / Enter a reviewer code.");
      return;
    }
    const ratings = Object.fromEntries(rubricEntries.map(([dimension, rubric]) => [
      dimension,
      mean(rubric.indicators.map(([key]) => indicatorRatings[key] || 4)),
    ]));
    setBusy(true); setError(""); setMessage("");
    try {
      await submitBlindReview(batchUuid, packet.run_label, {
        reviewer_id: reviewerId.trim(),
        ratings: { ...ratings, overall_believability: overall },
        indicator_ratings: indicatorRatings,
        evidence: { dimension_evidence: dimensionEvidence, entry_point: "external_expert_page" },
        reviewer_profile: {
          expertise: expertise.trim(),
          experience_years: experienceYears ? Number(experienceYears) : null,
          declared_interface_locale: locale,
        },
        notes,
        transcript_sha256: packet.source_provenance.transcript_sha256,
        interface_locale: locale,
        finalize: true,
      });
      setMessage("评分已锁定保存。 / Review finalized and saved.");
      if (queue && index < queue.packets.length - 1) setIndex((value) => value + 1);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!queue || !packet) {
    return <AppShell><main className="expert-review-page"><Link to="/batch-experiments">← Experiments</Link><h1>专家盲评 · Expert blind review</h1>{error ? <div className="error-banner">{error}</div> : <p>正在载入真实对话… / Loading persisted transcript…</p>}</main></AppShell>;
  }

  const transcript = fullTranscript ? packet.public_transcript : (packet.fixed_window_transcript || packet.public_transcript);
  const scenario = packet.gold_specification as { title?: string; scenario_description?: string; role_cards?: Array<Record<string, unknown>> };

  return <AppShell>
    <main className="expert-review-page">
      <header className="expert-review-header">
        <div><Link to="/batch-experiments">← 实验管理 / Experiments</Link><h1>外部专家匿名评审 · External expert blind review</h1><p>评审项目 {index + 1}/{queue.packets.length} · Anonymous item <strong>{packet.run_label}</strong></p></div>
        <label>界面 / Interface<select value={locale} onChange={(event) => setLocale(event.target.value as Locale)}><option value="bilingual">中英双语 / Bilingual</option><option value="zh-CN">中文</option><option value="en">English</option></select></label>
      </header>

      <section className="review-integrity-banner">
        <strong>真实对话证据 · Authentic transcript evidence</strong>
        <span>以下内容直接来自当时保存的会话，不翻译、不重写、不重新生成。 / This is the exact persisted session transcript—never translated, rewritten, or regenerated.</span>
        <code>SHA-256 {packet.source_provenance.transcript_sha256}</code>
      </section>

      {error && <div className="error-banner">{error}</div>}
      {message && <div className="success-banner">{message}</div>}

      <form onSubmit={submit} className="expert-review-layout">
        <aside className="expert-context-panel">
          <h2>情境资料 · Case context</h2>
          <h3>{scenario.title}</h3><p>{scenario.scenario_description}</p>
          <p className="blind-notice"><strong>条件已隐藏 / Condition hidden.</strong><br />你不会看到该对话来自 RoomMind 或 Baseline。</p>
          <h3>角色卡 · Role cards</h3>
          {(scenario.role_cards || []).map((role, roleIndex) => <details key={roleIndex}><summary>{String(role.speaker_label || `Participant ${roleIndex + 1}`)} · {String(role.job_title || "Business role")}</summary><p>{String(role.responsibility || "")}</p></details>)}
          <h3>专家信息 · Reviewer profile</h3>
          <label>评审编号 / Reviewer code<input value={reviewerId} onChange={(event) => setReviewerId(event.target.value)} required /></label>
          <label>专业领域 / Expertise<input value={expertise} onChange={(event) => setExpertise(event.target.value)} placeholder="Business, HCI, simulation…" /></label>
          <label>从业年限 / Years of experience<input type="number" min="0" max="80" value={experienceYears} onChange={(event) => setExperienceYears(event.target.value)} /></label>
          <small>开发版请勿填写真实邮箱；正式部署将由邮箱魔法链接或机构登录验证身份，并只在服务端保存身份映射。<br />Do not enter a real email in development; production will use verified magic links or institutional SSO with a server-side identity mapping.</small>
        </aside>

        <section className="expert-transcript-panel">
          <div className="transcript-heading"><h2>原始对话 · Original transcript</h2><button type="button" onClick={() => setFullTranscript((value) => !value)}>{fullTranscript ? "显示固定20轮 / Fixed 20-turn window" : "显示完整对话 / Full transcript"}</button></div>
          <div className="expert-transcript">
            {transcript.map((row) => <article key={`${row.sequence_no}-${row.speaker_id}`}><header><strong>{row.speaker_label || row.speaker_id}</strong><span>#{row.sequence_no} · Turn {row.turn_id}</span></header><p>{row.content}</p></article>)}
          </div>
        </section>

        <section className="expert-rubric-panel">
          <h2>六维真实性量表 · Six-dimension realism rubric</h2>
          <p>1 = 非常不真实 / very unrealistic；4 = 中等 / neutral；7 = 非常真实 / highly realistic。请引用对话编号说明依据。</p>
          {rubricEntries.map(([dimension, rubric], dimensionIndex) => {
            const dimensionScore = mean(rubric.indicators.map(([key]) => indicatorRatings[key] || 4));
            return <fieldset key={dimension} className="rubric-dimension"><legend><span>{dimensionIndex + 1}. {rubric.label_zh}</span><small>{rubric.label_en} · 当前均值 / current mean {dimensionScore}</small></legend>
              <p>{label(rubric.description_en, rubric.description_zh)}</p>
              {rubric.indicators.map(([key, en, zh]) => <label className="indicator-rating" key={key}><span>{label(en, zh)}</span><select value={indicatorRatings[key] || 4} onChange={(event) => setIndicatorRatings((current) => ({ ...current, [key]: Number(event.target.value) }))}>{scoreOptions.map((score) => <option value={score} key={score}>{score}</option>)}</select></label>)}
              <label>证据编号与理由 / Sequence evidence and rationale<textarea value={dimensionEvidence[dimension] || ""} onChange={(event) => setDimensionEvidence((current) => ({ ...current, [dimension]: event.target.value }))} placeholder="#12, #18 …" /></label>
            </fieldset>;
          })}
          <label className="overall-rating"><span>总体可信度 / Overall believability</span><select value={overall} onChange={(event) => setOverall(Number(event.target.value))}>{scoreOptions.map((score) => <option value={score} key={score}>{score}</option>)}</select></label>
          <label>其他说明 / Additional notes<textarea value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
          <button className="finalize-review" disabled={busy}>{busy ? "保存中… / Saving…" : "锁定并提交评分 / Finalize & submit"}</button>
          <small>提交后评分与本页 SHA-256 绑定且不可覆盖。 / Once submitted, the review is bound to this transcript checksum and cannot be overwritten.</small>
        </section>
      </form>
    </main>
  </AppShell>;
}
