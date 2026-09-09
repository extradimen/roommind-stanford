"""Validate a persisted batch/session checkpoint before continuing it."""
from copy import deepcopy


def resume_position(run, session):
    if session is None:
        raise ValueError("Interrupted session missing; refusing replacement")
    if (session.scenario_id != run.scenario_id or session.session_mode != run.condition
            or (session.run_config or {}).get("batch_experiment_run_id") != run.id):
        raise ValueError("Interrupted session does not belong to this run")
    if session.status not in {"active", "paused", "completed", "stopped"}:
        raise ValueError("Interrupted session status cannot be resumed")
    last = (run.result or {}).get("last_completed_turn_index", 0)
    if type(last) is not int or last < 0:
        raise ValueError("Invalid committed turn checkpoint")
    shared = session.shared_state or {}
    state_key = "_baseline_state" if run.condition == "baseline" else "_test_state"
    completed = (shared.get(state_key) or {}).get("completed_turns", 0)
    if type(completed) is not int or completed < 0 or completed != last:
        raise ValueError("Session and batch turn checkpoints disagree")
    return last + 1, deepcopy(shared.get("_performance_trace") or [])
