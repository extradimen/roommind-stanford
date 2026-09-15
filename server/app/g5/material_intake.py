"""Local internal review preparation; register exposure before returning tasks."""
from copy import deepcopy

from app.factorial_study import digest
from app.g5.annotation_archive import AnnotationArchive, identity
from app.g5.family_registry import verify_export
from app.g5.measurement import require, sha


def prepare_review(registry, manifest, sources, annotation_plan, intake):
    require(isinstance(intake, dict) and set(intake) == {"id", "observer", "source_kind", "sampling", "provenance_sha256"}
        and isinstance(intake["id"], str) and intake["id"].strip()
        and intake["source_kind"] in {"synthetic", "assistant", "human"}
        and intake["sampling"] in {"natural", "error_enriched", "constructed"}
        and sha(intake["provenance_sha256"]), "Explicit intake provenance and sampling required")
    identity(intake["observer"])
    archive = AnnotationArchive(":memory:", manifest, sources, annotation_plan)
    try:
        state = verify_export(registry.export())
        scenarios = {s["id"]: s for s in manifest["design"]["scenarios"]}
        families = set()
        for source in sources:
            assignment = source["binding"]["assignment"]
            scenario = scenarios[assignment["scenario_id"]]
            family = assignment["family"]
            require(family in state["families"] and any(m["family_id"] == family
                and m["snapshot_sha256"] == scenario["snapshot_sha256"] for m in state["materials"]),
                "Source family/snapshot not registered")
            families.add(family)
        source_binding = {"manifest_sha256": manifest["manifest_sha256"], "sources_sha256": digest(sources),
                          "annotation_plan_sha256": annotation_plan["sha256"], "intake": deepcopy(intake)}
        exposure = {"id": intake["id"], "kind": "exposure", "families": sorted(families), "purpose": "calibration",
                    "observer": deepcopy(intake["observer"]), "artifact_sha256": digest(source_binding)}
        registry.append(exposure)  # Durable before any review tasks are returned.
        raw = {"schema": "g5-local-review-intake-v1", "classification": "internal-audit-only",
               **source_binding, "manifest": deepcopy(manifest), "sources": deepcopy(sources),
               "annotation_plan": deepcopy(annotation_plan), "registry": registry.export(), "exposure": exposure,
               "review_tasks": [archive.task(c["id"]) for c in annotation_plan["plan"]["cases"]],
               "reference_labels": "not_collected", "human_identity_authenticated": False, "external_send_authorized": False}
        return {**raw, "sha256": digest(raw)}
    finally:
        archive.close()


def verify_bundle(bundle):
    state = verify_export(bundle["registry"])
    require(bundle["exposure"] in state["exposures"], "Missing durable review exposure")
    # Rebuild using a private in-memory registry; no material/label mutation.
    from app.g5.family_registry import FamilyRegistry
    registry = FamilyRegistry(":memory:", bundle["registry"]["registry_id"])
    try:
        for event in bundle["registry"]["events"]:
            registry.append(event)
        rebuilt = prepare_review(registry, bundle["manifest"], bundle["sources"], bundle["annotation_plan"], bundle["intake"])
        require(rebuilt == bundle, "Review intake bundle does not reproduce")
    finally:
        registry.close()
    return {"sha256": bundle["sha256"], "tasks": len(bundle["review_tasks"]), "external_send_authorized": False}
