"""Frozen, lossless presentation/order/repeat controls for independent scoring.

Formatting controls do not rewrite utterances or establish semantic-style
invariance. Repeated ratings are measurements of one source, not new samples.
"""
from copy import deepcopy
import json
from itertools import combinations, product

from app.factorial_study import digest
from app.g5.world import canonical


def validate(config):
    if (not isinstance(config, dict) or set(config) != {"schema", "presentations", "orders", "repetitions", "seed"}
            or config["schema"] != "g5-evaluation-controls-v1"
            or config["presentations"] != ["compact-json", "indented-json"]
            or config["orders"] != ["forward", "reverse"]
            or type(config["repetitions"]) is not int or not 2 <= config["repetitions"] <= 20
            or type(config["seed"]) is not int):
        raise ValueError("Invalid frozen evaluation controls")


def cells(config):
    validate(config)
    return [{"presentation": p, "order": o, "repeat": r, "controls_sha256": digest(config)}
            for p, o, r in product(config["presentations"], config["orders"], range(1, config["repetitions"] + 1))]


def validate_cell(plan, cell):
    config = plan["config"].get("evaluation_controls")
    if config is None:
        if cell is not None:
            raise ValueError("Unfrozen evaluation control")
    elif canonical(cell) not in {canonical(c) for c in cells(config)}:
        raise ValueError("Missing or invalid frozen evaluation cell")


def request_for(spec, packet, dimension, rubric, cell=None):
    from app.g5.evaluation import PROMPT, PROMPT_V1, PROMPT_V2, PROMPT_V3
    from app.g5.evaluation_semantics import (semantic_contract_for_dimension,
        semantic_contract_sha256, semantic_contract_v1, semantic_contract_v1_sha256,
        semantic_contract_v2_for_dimension, semantic_contract_v2_sha256,
        semantic_contract_v3_for_dimension, semantic_contract_v3_sha256)
    semantic_sha = spec.get("semantic_contract_sha256")
    if semantic_sha == semantic_contract_v1_sha256():
        contract, prompt = semantic_contract_v1(), PROMPT_V1
    elif semantic_sha == semantic_contract_v2_sha256():
        contract, prompt = semantic_contract_v2_for_dimension(dimension), PROMPT_V2
    elif semantic_sha == semantic_contract_v3_sha256():
        contract, prompt = semantic_contract_v3_for_dimension(dimension), PROMPT_V3
    elif semantic_sha == semantic_contract_sha256():
        contract, prompt = semantic_contract_for_dimension(dimension), PROMPT
    else:
        raise ValueError("Unknown semantic scoring contract")
    selected = {"context": deepcopy(packet["context"]), "turns": deepcopy(packet["transcript"]["turns"]),
                "dimension": dimension, "rubric": rubric[dimension],
                "semantic_contract": contract}
    content = canonical(selected)
    if cell is not None:
        if cell["presentation"] == "indented-json":
            content = json.dumps(selected, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        elif cell["presentation"] != "compact-json":
            raise ValueError("Unknown presentation")
    return {"binding": deepcopy(spec["binding"]), "messages": [
        {"role": "system", "content": prompt}, {"role": "user", "content": content}]}


def schedule(plan, packets, cell):
    from app.g5.measurement import DIMENSIONS
    validate_cell(plan, cell)
    jobs = [(p, d) for p in sorted(packets, key=lambda p: p["transcript"]["ordinal"]) for d in DIMENSIONS]
    if cell is not None:
        seed = plan["config"]["evaluation_controls"]["seed"]
        jobs.sort(key=lambda job: (digest([seed, job[0]["transcript"]["ordinal"], job[1]]),
                                   job[0]["transcript"]["ordinal"], job[1]))
        if cell["order"] == "reverse":
            jobs.reverse()
    return jobs


def diagnostic_report(manifest, plan, packets, exports):
    """Validate all cell archives; retain missing cells and unpaired outcomes."""
    from app.g5.evaluation_archive import EvaluationArchive
    from app.g5.measurement import index_scores, DIMENSIONS
    expected = cells(plan["config"]["evaluation_controls"])
    template = EvaluationArchive(":memory:", manifest, plan, packets, control=expected[0])
    template.close()
    indexed, summaries, failures = {}, [], {}
    for exported in exports:
        cell = exported.get("control")
        validate_cell(plan, cell)
        key = canonical(cell)
        if key in indexed:
            raise ValueError("Repeated evaluation cell archive")
        archive = EvaluationArchive(":memory:", manifest, plan, packets, control=cell)
        try:
            for result in exported["results"]:
                archive.append(result)
            if archive.export() != exported:
                raise ValueError("Control archive provenance/chain mismatch")
        finally:
            archive.close()
        _, indexed[key] = index_scores(manifest, plan, [p["transcript"] for p in packets],
                                       [r["attempt"] for r in exported["results"]])
        failures[key] = sum(r["attempt"]["status"] == "technical_failure" for r in exported["results"])
    slots = [(p["transcript"]["ordinal"], d) for p in packets for d in DIMENSIONS]
    for cell in expected:
        rows = indexed.get(canonical(cell), {})
        counts = {s: 0 for s in ("completed", "not_applicable", "technical_failure", "missing")}
        for slot in slots:
            counts[rows.get(slot, {}).get("status", "missing")] += 1
        summaries.append({"cell": cell, "outcomes": counts, "technical_failure_attempts": failures.get(canonical(cell), 0)})
    comparisons = []
    for left, right in combinations(expected, 2):
        differing = [k for k in ("presentation", "order", "repeat") if left[k] != right[k]]
        if len(differing) != 1:
            continue
        a, b = indexed.get(canonical(left), {}), indexed.get(canonical(right), {})
        for dimension in DIMENSIONS:
            deltas = [b[s]["score"] - a[s]["score"] for s in slots if s[1] == dimension
                      and a.get(s, {}).get("status") == b.get(s, {}).get("status") == "completed"]
            comparisons.append({"factor": differing[0], "left": left, "right": right, "dimension": dimension,
                "eligible_sources": len(packets), "paired_completed": len(deltas),
                "unpaired": len(packets) - len(deltas), "mean_right_minus_left": sum(deltas) / len(deltas) if deltas else None,
                "mean_absolute_difference": sum(map(abs, deltas)) / len(deltas) if deltas else None,
                "exact_agreement": sum(d == 0 for d in deltas) / len(deltas) if deltas else None})
    raw = {"schema": "g5-evaluation-control-diagnostics-v1", "plan_sha256": plan["sha256"],
        "packet_sha256": sorted(p["sha256"] for p in packets), "cells": summaries, "comparisons": comparisons,
        "all_terminal": all(s["outcomes"]["missing"] == s["outcomes"]["technical_failure"] == 0 for s in summaries),
        "style_scope": "lossless-json-formatting-only", "inference": "descriptive-no-independent-replicate-claim",
        "qualification": "not_inferred"}
    return {**raw, "sha256": digest(raw)}


def validate_order(plan, packets, cell, results):
    if cell is None:
        return
    expected = [(p["transcript"]["ordinal"], d) for p, d in schedule(plan, packets, cell)]
    seen = set()
    for result in results:
        row = result["attempt"]
        slot = row["ordinal"], row["dimension"]
        if slot not in seen:
            if len(seen) >= len(expected) or slot != expected[len(seen)]:
                raise ValueError("Evaluation first-attempt order differs from frozen schedule")
            seen.add(slot)


async def evaluate_panel(directory, evaluator, manifest, plan, packets):
    """Explicit caller-run, sequential panel; resume only missing dimensions.

    No background scheduling or automatic external call. The caller supplies
    the authorized evaluator. A plan cannot silently reuse another panel path.
    """
    import os
    from pathlib import Path
    from app.g5.evaluation_archive import EvaluationArchive
    expected = cells(plan["config"]["evaluation_controls"])
    template = EvaluationArchive(":memory:", manifest, plan, packets, control=expected[0])
    template.close()
    if evaluator.judge() != plan["config"]["judge"]:
        raise ValueError("Panel evaluator differs from frozen plan")
    directory = Path(directory)
    directory.mkdir(mode=0o700, exist_ok=True)
    marker = directory / "panel-input.json"
    frozen = {"schema": "g5-evaluation-panel-input-v1", "manifest": manifest["manifest_sha256"],
              "plan": plan["sha256"], "packets": sorted(p["sha256"] for p in packets)}
    if not marker.exists():
        if any(directory.iterdir()):
            raise ValueError("Refusing unrelated panel directory")
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(canonical(frozen))
            stream.flush()
            os.fsync(stream.fileno())
    if marker.read_text(encoding="utf-8") != canonical(frozen):
        raise ValueError("Panel path belongs to different frozen inputs")
    # Validate every existing cell before any model request, not halfway through.
    for cell in expected:
        path = directory / (digest(cell) + ".sqlite")
        if path.exists():
            archive = EvaluationArchive(str(path), manifest, plan, packets, control=cell)
            archive.close()
    for cell in expected:
        archive = EvaluationArchive(str(directory / (digest(cell) + ".sqlite")), manifest, plan, packets, control=cell)
        try:
            async for result in archive.evaluate_missing(evaluator):
                yield {"cell": deepcopy(cell), "result": result}
        finally:
            archive.close()
