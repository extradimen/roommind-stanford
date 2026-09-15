"""Run the explicitly local G5 engineering suite and save an auditable receipt.

Invoke from the repository root. PostgreSQL tests use only their self-owned
random schemas; G5_TEST_DSN must be explicit and is never copied into a receipt.
No models, deployment, old experiment databases or production modules are run.
"""
import argparse
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import sys
import time
import unittest

from app.factorial_study import digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres", action="store_true", help="Require explicit local G5_TEST_DSN")
    parser.add_argument("--output", required=True, help="New receipt file, never overwrite")
    args = parser.parse_args()
    if args.postgres and not os.environ.get("G5_TEST_DSN"):
        parser.error("--postgres requires an explicit test DSN")
    if not args.postgres and os.environ.get("G5_TEST_DSN"):
        parser.error("Explicit --postgres acknowledgement required when test DSN is present")
    if Path(args.output).exists():
        parser.error("Output exists; choose a new receipt path")
    inputs = sorted([*Path("server/app/g5").glob("*.py"), Path("server/app/factorial_study.py"),
                     *Path("server/tests").glob("test_g5*.py"), Path("server/tests/test_factorial_study.py")])
    import hashlib
    fingerprints = lambda: {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    before = fingerprints()
    for path in inputs:
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    started = datetime.now(timezone.utc).isoformat()
    clock = time.monotonic()
    suite = unittest.TestSuite([unittest.defaultTestLoader.discover("server/tests", pattern=pattern)
                               for pattern in ("test_g5*.py", "test_factorial_study.py")])
    def ids(suite):
        return [name for child in suite for name in (ids(child) if isinstance(child, unittest.TestSuite) else [child.id()])]
    selected = ids(suite)
    if len(selected) != len(set(selected)):
        raise ValueError("Duplicate test identities in acceptance suite")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    stable = before == fingerprints()
    raw = {"schema": "g5-local-acceptance-receipt-v1", "evidence_use": "synthetic-engineering-only",
        "started_at": started, "elapsed_seconds": time.monotonic() - clock,
        "postgres_requested": args.postgres, "source_sha256": before, "source_unchanged": stable,
        "tests": selected, "tests_run": result.testsRun,
        "failures": [test.id() for test, _ in result.failures], "errors": [test.id() for test, _ in result.errors],
        "skipped": [{"test": test.id(), "reason": reason} for test, reason in result.skipped],
        "unexpected_successes": [t.id() for t in result.unexpectedSuccesses],
        "expected_failures": [t.id() for t, _ in result.expectedFailures], "runner_output": stream.getvalue(),
        "engineering_checks_passed": result.wasSuccessful() and not result.skipped and not result.expectedFailures and stable,
        "qualification": "not_inferred", "local_release_all_gates_complete": False}
    receipt = {**raw, "sha256": digest(raw)}
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(receipt, output, ensure_ascii=False, sort_keys=True)
        output.flush()
        os.fsync(output.fileno())
    print(json.dumps({k: receipt[k] for k in ("tests_run", "failures", "errors", "skipped", "source_unchanged",
        "engineering_checks_passed", "sha256", "local_release_all_gates_complete")}, sort_keys=True))
    return 0 if receipt["engineering_checks_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
