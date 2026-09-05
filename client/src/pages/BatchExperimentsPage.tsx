import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import AppShell from "../components/AppShell";
import {
  BatchExperiment,
  BatchExperimentRun,
  cancelBatchExperiment,
  createBatchExperiment,
  getBatchExperiment,
  listBatchExperiments,
  listScenarios,
  getBlindReviewQueue,
  submitBlindReview,
  startBatchEvaluation,
  retryBatchDialogue,
  BlindReviewQueue,
  Scenario,
} from "../api";

const terminal = new Set(["dialogue_completed", "evaluation_completed", "evaluation_partial", "completed", "cancelled"]);
const realismDimensions = [
  "role_strategic_fidelity", "epistemic_fidelity", "temporal_coherence",
  "interaction_structure_fidelity", "multi_party_dynamics_fidelity", "procedural_fidelity",
] as const;
const dimensionLabels: Record<string, string> = {
  role_strategic_fidelity: "Role & strategy", epistemic_fidelity: "Information boundaries",
  temporal_coherence: "Temporal coherence", interaction_structure_fidelity: "Interaction structure",
  multi_party_dynamics_fidelity: "Multi-party dynamics", procedural_fidelity: "Procedural fidelity",
};

function value(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "1" : "0";
  return String(value);
}

function dialogueStatus(run: BatchExperimentRun): string {
  // The run row is authoritative for live transitions. A retry keeps audit
  // metadata in result, whose queued value can otherwise mask active work.
  if (run.status === "running") return "running";
  if (run.status === "queued") return "queued";
  if (run.status === "cancelled") return "cancelled";
  if (run.status === "failed" || run.status === "dialogue_failed") return "failed";
  const persisted = run.result.dialogue_status;
  if (typeof persisted === "string" && persisted) return persisted;
  if (run.status.startsWith("dialogue_")) return run.status.replace("dialogue_", "");
  if (run.status.startsWith("evaluation_") || run.status === "completed") return "completed";
  return run.session_uuid ? "completed" : run.status;
}

export default function BatchExperimentsPage() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [batches, setBatches] = useState<BatchExperiment[]>([]);
  const [selected, setSelected] = useState<BatchExperiment | null>(null);
  const [scenarioIds, setScenarioIds] = useState<number[]>([]);
  const [conditions, setConditions] = useState<("test" | "baseline")[]>(["test", "baseline"]);
  const [name, setName] = useState(`Comparison ${new Date().toISOString().slice(0, 10)}`);
  const [repetitions, setRepetitions] = useState(10);
  const [concurrency, setConcurrency] = useState(2);
  const [maxTurns, setMaxTurns] = useState(50);
  const [maxStagnantTurns, setMaxStagnantTurns] = useState(8);
  const [seed, setSeed] = useState(20260728);
  const [humanValidation, setHumanValidation] = useState(true);
  const [studyPhase, setStudyPhase] = useState<"exploration" | "screening" | "confirmation">("exploration");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reviewQueue, setReviewQueue] = useState<BlindReviewQueue | null>(null);
  const [reviewIndex, setReviewIndex] = useState(0);
  const [reviewerId, setReviewerId] = useState("");
  const [ratings, setRatings] = useState<Record<string, number>>(() => Object.fromEntries(realismDimensions.map((d) => [d, 4])));
  const [reviewNotes, setReviewNotes] = useState("");
  const [busyRunId, setBusyRunId] = useState<number | null>(null);

  const refreshList = () => listBatchExperiments().then(setBatches).catch((e) => setError(String(e)));

  useEffect(() => {
    listScenarios().then((rows) => {
      setScenarios(rows);
      setScenarioIds(rows.map((row) => row.id));
    }).catch((e) => setError(String(e)));
    refreshList();
  }, []);

  useEffect(() => {
    if (!selected || terminal.has(selected.status)) return;
    const timer = window.setInterval(() => {
      getBatchExperiment(selected.batch_uuid).then((row) => {
        setSelected(row);
        refreshList();
      }).catch(() => {});
    }, 3000);
    return () => window.clearInterval(timer);
  }, [selected?.batch_uuid, selected?.status]);

  const plannedRuns = scenarioIds.length * conditions.length * repetitions;
  const scenarioNames = useMemo(
    () => new Map(scenarios.map((scenario) => [scenario.id, scenario.title])),
    [scenarios],
  );

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (!scenarioIds.length || !conditions.length) {
      setError("Select at least one scenario and one condition.");
      return;
    }
    setBusy(true);
    try {
      const batch = await createBatchExperiment({
        name,
        scenario_ids: scenarioIds,
        conditions,
        repetitions,
        concurrency,
        safety_max_turns: maxTurns,
        max_stagnant_turns: maxStagnantTurns,
        random_seed: seed,
        human_validation_enabled: humanValidation,
        study_phase: studyPhase,
      });
      const detail = await getBatchExperiment(batch.batch_uuid);
      setSelected(detail);
      await refreshList();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function openBatch(batchUuid: string) {
    setError("");
    try { setSelected(await getBatchExperiment(batchUuid)); }
    catch (e) { setError(String(e)); }
  }

  async function openReviews() {
    if (!selected) return;
    setError("");
    try { setReviewQueue(await getBlindReviewQueue(selected.batch_uuid)); setReviewIndex(0); }
    catch (e) { setError(String(e)); }
  }

  async function saveReview() {
    if (!selected || !reviewQueue || !reviewerId.trim()) { setError("Enter a reviewer ID."); return; }
    const packet = reviewQueue.packets[reviewIndex];
    try {
      const indicatorRatings = Object.fromEntries(
        Object.entries(packet.rubric || {}).flatMap(([dimension, rubric]) =>
          (rubric.indicators || []).map(([indicator]) => [indicator, ratings[dimension] || 4]),
        ),
      );
      await submitBlindReview(selected.batch_uuid, packet.run_label, {
        reviewer_id: reviewerId, ratings, evidence: { entry_point: "admin_inline" }, notes: reviewNotes,
        transcript_sha256: packet.source_provenance.transcript_sha256,
        indicator_ratings: indicatorRatings, interface_locale: "en", finalize: true,
      });
      setReviewQueue(await getBlindReviewQueue(selected.batch_uuid));
      setReviewNotes("");
      setReviewIndex((i) => Math.min(i + 1, reviewQueue.packets.length - 1));
    } catch (e) { setError(String(e)); }
  }

  async function startEvaluation(retryAll = false) {
    if (!selected) return;
    setBusy(true); setError("");
    try {
      await startBatchEvaluation(selected.batch_uuid, { retry_all: retryAll, concurrency: 1 });
      setSelected(await getBatchExperiment(selected.batch_uuid));
      await refreshList();
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  async function retryDialogue(run: BatchExperimentRun) {
    if (!selected) return;
    setBusyRunId(run.id); setError("");
    try {
      await retryBatchDialogue(selected.batch_uuid, run.id);
      setSelected(await getBatchExperiment(selected.batch_uuid));
      await refreshList();
    } catch (e) { setError(String(e)); }
    finally { setBusyRunId(null); }
  }

  async function retryEvaluation(run: BatchExperimentRun) {
    if (!selected) return;
    setBusyRunId(run.id); setError("");
    try {
      await startBatchEvaluation(selected.batch_uuid, { run_ids: [run.id], concurrency: 1 });
      setSelected(await getBatchExperiment(selected.batch_uuid));
      await refreshList();
    } catch (e) { setError(String(e)); }
    finally { setBusyRunId(null); }
  }

  return (
    <AppShell>
      <div className="batch-page">
        <header className="batch-header">
          <div>
            <Link to="/">← Scenarios</Link>
            <h1>Batch Experiments</h1>
            <p>Dialogue generation and external evaluation are independent server-side processes. Closing this page does not interrupt either process.</p>
          </div>
        </header>

        <section className="experiment-steps" aria-label="Experiment workflow">
          <div><strong>1</strong><span>Configure & run dialogue</span></div>
          <div><strong>2</strong><span>Automatic six-dimension evaluation</span></div>
          <div><strong>3</strong><span>Blinded human review</span></div>
          <div><strong>4</strong><span>Final evidence report</span></div>
        </section>

        {error && <div className="error-banner">{error}</div>}

        <section className="batch-panel">
          <h2>New experiment</h2>
          <form onSubmit={submit} className="batch-form">
            <label className="full">Experiment name<input value={name} onChange={(e) => setName(e.target.value)} /></label>
            <fieldset className="full">
              <legend>Scenarios</legend>
              <div className="check-grid">
                {scenarios.map((scenario) => <label key={scenario.id}>
                  <input type="checkbox" checked={scenarioIds.includes(scenario.id)} onChange={(e) => setScenarioIds((ids) => e.target.checked ? [...ids, scenario.id] : ids.filter((id) => id !== scenario.id))} />
                  Play {scenario.id}: {scenario.title}
                </label>)}
              </div>
            </fieldset>
            <fieldset className="full">
              <legend>Conditions</legend>
              <div className="check-grid two">
                <label><input type="checkbox" checked={conditions.includes("test")} onChange={(e) => setConditions((v) => e.target.checked ? [...v, "test"] : v.filter((x) => x !== "test"))} /> RoomMind AI Test</label>
                <label><input type="checkbox" checked={conditions.includes("baseline")} onChange={(e) => setConditions((v) => e.target.checked ? [...v, "baseline"] : v.filter((x) => x !== "baseline"))} /> Traditional Independent-Agent Baseline</label>
              </div>
            </fieldset>
            <label>Runs per combination<input type="number" min={1} max={100} value={repetitions} onChange={(e) => setRepetitions(Number(e.target.value))} /></label>
            <label>Concurrent runs<select value={concurrency} onChange={(e) => setConcurrency(Number(e.target.value))}>
              <option value={1}>1 · safest</option><option value={2}>2 · recommended</option><option value={3}>3</option><option value={4}>4 · server maximum</option>
            </select><small>Two balances throughput with model rate limits. Run order is randomized.</small></label>
            <label>Maximum turns<input type="number" min={10} max={100} value={maxTurns} onChange={(e) => setMaxTurns(Number(e.target.value))} /></label>
            <label>Stagnation window<input type="number" min={4} max={25} value={maxStagnantTurns} onChange={(e) => setMaxStagnantTurns(Number(e.target.value))} /><small>Stop a RoomMind run after this many turns without material state, work-item, or outcome progress.</small></label>
            <label>Randomization seed<input type="number" min={0} value={seed} onChange={(e) => setSeed(Number(e.target.value))} /><small>Keep this value for a reproducible run order.</small></label>
            <label>Study phase<select value={studyPhase} onChange={(e) => setStudyPhase(e.target.value as typeof studyPhase)}><option value="exploration">Exploration · development evidence</option><option value="screening">Screening · candidate selection</option><option value="confirmation">Confirmation · held-out evidence</option></select><small>The selected phase is frozen in the experiment manifest.</small></label>
            <label className="full"><input type="checkbox" checked={humanValidation} onChange={(e) => setHumanValidation(e.target.checked)} /> Enable blinded human review<small>Recommended. Reviewers score the same six realism dimensions on anonymous transcripts after automatic evaluation.</small></label>
            <div className="batch-submit full"><strong>{plannedRuns} total runs</strong><button disabled={busy || plannedRuns < 1 || plannedRuns > 500}>{busy ? "Creating…" : "Start background experiment"}</button></div>
          </form>
        </section>

        <section className="batch-panel">
          <h2>Experiments</h2>
          <div className="batch-list">
            {batches.map((batch) => <button key={batch.batch_uuid} onClick={() => openBatch(batch.batch_uuid)} className={selected?.batch_uuid === batch.batch_uuid ? "active" : ""}>
              <span><strong>{batch.name}</strong><small>{batch.batch_uuid.slice(0, 8)}</small></span>
              <span>{batch.status} · {batch.completed_runs + batch.failed_runs + (batch.cancelled_runs || 0)}/{batch.total_runs}</span>
            </button>)}
            {!batches.length && <p className="empty">No batch experiments yet.</p>}
          </div>
        </section>

        {selected && <section className="batch-panel batch-results">
          <div className="result-heading">
            <div><h2>{selected.name}</h2><p>Status: <strong>{selected.status}</strong> · completed {selected.completed_runs} · failed {selected.failed_runs} · cancelled {selected.cancelled_runs || 0} · total {selected.total_runs}</p></div>
            <div className="result-actions">
              {!terminal.has(selected.status) && selected.status !== "evaluation_running" && <button onClick={async () => { await cancelBatchExperiment(selected.batch_uuid); setSelected(await getBatchExperiment(selected.batch_uuid)); }}>Cancel dialogue generation</button>}
              {["dialogue_completed", "evaluation_partial"].includes(selected.status) && <button disabled={busy} onClick={() => startEvaluation(false)}>{busy ? "Starting…" : "Start automatic evaluation"}</button>}
              {selected.status === "evaluation_completed" && <button disabled={busy} onClick={() => startEvaluation(true)}>Re-evaluate all dialogues</button>}
              <a className="play-btn" href={`/api/game/batch-experiments/${selected.batch_uuid}/results.csv`}>Download CSV</a>
              <a className="play-btn" href={`/api/game/batch-experiments/${selected.batch_uuid}/transcripts.csv`}>All dialogue CSV</a>
              <a className="play-btn" href={`/api/game/batch-experiments/${selected.batch_uuid}/transcripts.json`}>All dialogue JSON</a>
              <a className="play-btn" href={`/api/game/batch-experiments/${selected.batch_uuid}/debug-bundle.json`}>Debug bundle</a>
              {Boolean(selected.config.human_validation_enabled) && <Link className="play-btn" to={`/expert-review/${selected.batch_uuid}`}>Expert review · 专家盲评</Link>}
              {Boolean(selected.config.human_validation_enabled) && <button onClick={openReviews}>Quick admin review</button>}
              <a className="play-btn" href={`/api/game/batch-experiments/${selected.batch_uuid}/final-evaluation`}>Final evaluation JSON</a>
              <button onClick={() => { const blob = new Blob([JSON.stringify(selected, null, 2)], { type: "application/json" }); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = `batch-${selected.batch_uuid}.json`; a.click(); URL.revokeObjectURL(url); }}>Download JSON</button>
            </div>
          </div>
          <div className="progress-track"><span style={{ width: `${selected.total_runs ? 100 * (selected.completed_runs + selected.failed_runs + (selected.cancelled_runs || 0)) / selected.total_runs : 0}%` }} /></div>
          <div className="batch-table-wrap"><table className="batch-table"><thead><tr>
            <th>Scenario</th><th>Condition</th><th>Rep.</th><th>Dialogue</th><th>AI evaluation</th>{realismDimensions.map((d) => <th key={d}>{dimensionLabels[d]}</th>)}<th>Error</th><th>Actions</th>
          </tr></thead><tbody>{(selected.runs || []).map((run) => <tr key={run.id}>
            <td>{scenarioNames.get(run.scenario_id) || run.scenario_id}</td><td>{run.condition}</td><td>{run.repetition}</td><td>{dialogueStatus(run)}</td><td>{value(run.result.evaluation_status || (run.status.startsWith("evaluation_") ? run.status.replace("evaluation_", "") : "not started"))}</td>
            {realismDimensions.map((d) => <td key={d}>{value(run.result[`ai_${d}`])}</td>)}<td className="error-cell" title={run.error || ""}>{run.error || ""}</td><td><div className="row-actions">
              {["failed", "dialogue_failed"].includes(run.status) && <button disabled={busyRunId === run.id} onClick={() => retryDialogue(run)}>{busyRunId === run.id ? "Queuing…" : "Retry dialogue"}</button>}
              {["evaluation_failed", "evaluation_partial"].includes(run.status) && <button disabled={busyRunId === run.id} onClick={() => retryEvaluation(run)}>{busyRunId === run.id ? "Queuing…" : "Retry evaluation"}</button>}
            </div></td>
          </tr>)}</tbody></table></div>
        </section>}

        {reviewQueue?.packets.length ? <section className="batch-panel blind-review">
          <div className="result-heading"><div><h2>Blinded human review</h2><p>Anonymous item {reviewIndex + 1} of {reviewQueue.packets.length}. System condition is hidden.</p></div><button onClick={() => setReviewQueue(null)}>Close</button></div>
          <label>Reviewer ID<input value={reviewerId} onChange={(e) => setReviewerId(e.target.value)} placeholder="Reviewer code" /></label>
          <div className="review-transcript">{reviewQueue.packets[reviewIndex].public_transcript.map((m) => <p key={m.sequence_no}><strong>#{m.sequence_no} · {m.speaker_id}</strong><br />{m.content}</p>)}</div>
          <div className="review-ratings">{realismDimensions.map((d) => <label key={d}>{dimensionLabels[d]}<select value={ratings[d]} onChange={(e) => setRatings((v) => ({ ...v, [d]: Number(e.target.value) }))}>{[1,2,3,4,5,6,7].map((n) => <option key={n} value={n}>{n}</option>)}</select></label>)}</div>
          <label>Evidence / notes<textarea value={reviewNotes} onChange={(e) => setReviewNotes(e.target.value)} placeholder="Cite sequence numbers and briefly justify the ratings." /></label>
          <div className="result-actions"><button disabled={reviewIndex === 0} onClick={() => setReviewIndex((i) => i - 1)}>Previous</button><button onClick={saveReview}>Save review & next</button><button disabled={reviewIndex >= reviewQueue.packets.length - 1} onClick={() => setReviewIndex((i) => i + 1)}>Next</button></div>
        </section> : null}
      </div>
    </AppShell>
  );
}
