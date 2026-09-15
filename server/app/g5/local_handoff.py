"""Read-only local handoff audit. Hash consistency is not deployment authority.

Only repository G5 code, its explicit acceptance receipt and research artifacts
are inspected. This module never launches workers or accesses a database/model.
"""
import hashlib
import json
import os
from pathlib import Path

from app.factorial_study import digest


def require(ok, message):
    if not ok: raise ValueError(message)


def regular(root, relative):
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute()
            and ".." not in Path(relative).parts, "Repository-relative path required")
    path = root / relative
    require(not any(p.is_symlink() for p in (path, *path.parents)) and path.is_file(),
            "Regular non-symlink evidence file required")
    return path


def fingerprint(path):
    before = path.stat()
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): sha.update(block)
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "File changed during audit")
    return sha.hexdigest()


def sources(root):
    root = Path(root).resolve()
    paths = [*root.glob("server/app/g5/*.py"), root / "server/app/factorial_study.py",
             *root.glob("server/tests/test_g5*.py"), root / "server/tests/test_factorial_study.py"]
    require(bool(list(root.glob("server/app/g5/*.py"))), "Missing G5 source tree")
    return {str(p.relative_to(root)): fingerprint(regular(root, str(p.relative_to(root)))) for p in sorted(paths)}


def acceptance(root, receipt_path):
    require(receipt_path.startswith("docs/G5_LOCAL_ACCEPTANCE_") and receipt_path.endswith(".json"),
            "Explicit G5 acceptance receipt required")
    receipt = json.loads(regular(root, receipt_path).read_text(encoding="utf-8"))
    require(receipt.get("schema") == "g5-local-acceptance-receipt-v1" and
            receipt.get("sha256") == digest({k: v for k, v in receipt.items() if k != "sha256"}), "Invalid acceptance checksum")
    require(receipt.get("evidence_use") == "synthetic-engineering-only" and
            receipt.get("qualification") == "not_inferred", "Incorrect evidence scope")
    for flag in ("engineering_checks_passed", "source_unchanged", "postgres_requested"):
        require(receipt.get(flag) is True, "Incomplete full local acceptance")
    for field in ("failures", "errors", "skipped", "unexpected_successes", "expected_failures"):
        require(receipt.get(field) == [], "Acceptance contains unsuccessful or omitted checks")
    tests = receipt.get("tests")
    require(isinstance(tests, list) and tests and all(isinstance(t, str) for t in tests)
            and len(tests) == len(set(tests)) and type(receipt.get("tests_run")) is int
            and receipt["tests_run"] == len(tests), "Incomplete test accounting")
    require(receipt.get("source_sha256") == sources(root), "Acceptance does not cover current complete source set")
    return receipt


def inventory(root):
    base = root / "research/experiments"
    require(base.is_dir() and not base.is_symlink(), "Research artifact directory required")
    result = {}
    for path in sorted(base.rglob("*")):
        require(not path.is_symlink(), "Symlink in artifact inventory")
        if path.is_dir(): continue
        rel = str(path.relative_to(root))
        result[rel] = fingerprint(regular(root, rel))
    require(bool(result), "Empty artifact inventory")
    return result


def create(root, receipt_path):
    root = Path(root).resolve()
    receipt = acceptance(root, receipt_path)
    artifacts = inventory(root)
    # Recheck source after potentially slower history hashing.
    require(receipt["source_sha256"] == sources(root), "Source changed during handoff")
    raw = {"schema": "g5-local-handoff-v1", "scope": "offline-engineering-only",
        "receipt_path": receipt_path, "receipt_sha256": receipt["sha256"],
        "source_sha256": receipt["source_sha256"], "artifact_sha256": artifacts,
        "tests_run": receipt["tests_run"], "historical_completeness_verified": False,
        "research_quality_verified": False, "launch_authorized": False,
        "limitations": ["unsigned-local-consistency-not-authentication", "no-cross-process-snapshot-lock",
                        "inventory-does-not-prove-prior-history-or-semantic-novelty"]}
    return {**raw, "sha256": digest(raw)}


def verify(root, bundle):
    require(isinstance(bundle, dict) and bundle.get("schema") == "g5-local-handoff-v1", "Invalid handoff")
    rebuilt = create(root, bundle["receipt_path"])
    require(rebuilt == bundle, "Handoff mismatch: source, acceptance or artifacts changed")
    return {"local_consistency_passed": True, "tests_run": bundle["tests_run"],
            "artifact_files": len(bundle["artifact_sha256"]), "handoff_sha256": bundle["sha256"],
            "research_quality_verified": False, "launch_authorized": False}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--receipt")
    group.add_argument("--verify")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.verify:
        if args.output: parser.error("Verification never writes output")
        result = verify(args.root, json.loads(Path(args.verify).read_text(encoding="utf-8")))
    else:
        if not args.output: parser.error("Creation requires a new --output outside research/experiments")
        target = Path(args.output).resolve()
        base = Path(args.root).resolve() / "research/experiments"
        if target.is_relative_to(base): parser.error("Handoff cannot inventory itself")
        bundle = create(args.root, args.receipt)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(bundle, stream, sort_keys=True, ensure_ascii=False)
            stream.flush(); os.fsync(stream.fileno())
        result = verify(args.root, bundle)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__": main()
