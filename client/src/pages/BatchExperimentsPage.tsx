import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import AppShell from "../components/AppShell";
import {
  BatchExperiment,
  cancelBatchExperiment,
  createBatchExperiment,
  getBatchExperiment,
  listBatchExperiments,
  listScenarios,
  Scenario,
} from "../api";

const terminal = new Set(["completed", "cancelled"]);

function value(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "1" : "0";
  return String(value);
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
  const [seed, setSeed] = useState(20260728);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

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
        random_seed: seed,
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

  return (
    <AppShell>
      <div className="batch-page">
        <header className="batch-header">
          <div>
            <Link to="/">← Scenarios</Link>
            <h1>Batch Experiments</h1>
            <p>Server-side runs continue after this page is closed. Results are evaluated externally and stored as one row per run.</p>
          </div>
        </header>

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
                <label><input type="checkbox" checked={conditions.includes("baseline")} onChange={(e) => setConditions((v) => e.target.checked ? [...v, "baseline"] : v.filter((x) => x !== "baseline"))} /> Prompt Baseline</label>
              </div>
            </fieldset>
            <label>Runs per combination<input type="number" min={1} max={100} value={repetitions} onChange={(e) => setRepetitions(Number(e.target.value))} /></label>
            <label>Concurrent runs<select value={concurrency} onChange={(e) => setConcurrency(Number(e.target.value))}>
              <option value={1}>1 · safest</option><option value={2}>2 · recommended</option><option value={3}>3</option><option value={4}>4 · server maximum</option>
            </select><small>Two balances throughput with model rate limits. Run order is randomized.</small></label>
            <label>Maximum turns<input type="number" min={10} max={100} value={maxTurns} onChange={(e) => setMaxTurns(Number(e.target.value))} /></label>
            <label>Randomization seed<input type="number" min={0} value={seed} onChange={(e) => setSeed(Number(e.target.value))} /><small>Keep this value for a reproducible run order.</small></label>
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
              {!terminal.has(selected.status) && <button onClick={async () => { await cancelBatchExperiment(selected.batch_uuid); setSelected(await getBatchExperiment(selected.batch_uuid)); }}>Cancel</button>}
              <a className="play-btn" href={`/api/game/batch-experiments/${selected.batch_uuid}/results.csv`}>Download CSV</a>
              <button onClick={() => { const blob = new Blob([JSON.stringify(selected, null, 2)], { type: "application/json" }); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = `batch-${selected.batch_uuid}.json`; a.click(); URL.revokeObjectURL(url); }}>Download JSON</button>
            </div>
          </div>
          <div className="progress-track"><span style={{ width: `${selected.total_runs ? 100 * (selected.completed_runs + selected.failed_runs + (selected.cancelled_runs || 0)) / selected.total_runs : 0}%` }} /></div>
          <div className="batch-table-wrap"><table className="batch-table"><thead><tr>
            <th>Scenario</th><th>Condition</th><th>Rep.</th><th>Status</th><th>Valid</th><th>Premature</th><th>Turn</th><th>Confirmations</th><th>Authority</th><th>Leaks</th><th>Contradictions</th><th>Repetition</th><th>Responsibility</th><th>Distinct</th><th>Role</th><th>Closure</th><th>Error</th>
          </tr></thead><tbody>{(selected.runs || []).map((run) => <tr key={run.id}>
            <td>{scenarioNames.get(run.scenario_id) || run.scenario_id}</td><td>{run.condition}</td><td>{run.repetition}</td><td>{run.status}</td>
            <td>{value(run.result.externally_validated_completion)}</td><td>{value(run.result.premature_completion)}</td><td>{value(run.result.first_valid_completion_turn)}</td><td>{value(run.result.total_confirmation_count)}</td><td>{value(run.result.authority_violation_count)}</td><td>{value(run.result.private_information_leakage_count)}</td><td>{value(run.result.contradiction_count)}</td><td>{value(run.result.semantic_repetition_count)}</td><td>{value(run.result.responsibility_match_rate)}</td><td>{value(run.result.distinct_contribution_rate)}</td><td>{value(run.result.role_consistency_mean)}</td><td>{value(run.result.closure_coherence)}</td><td className="error-cell" title={run.error || ""}>{run.error || ""}</td>
          </tr>)}</tbody></table></div>
        </section>}
      </div>
    </AppShell>
  );
}
