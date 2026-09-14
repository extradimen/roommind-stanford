#!/usr/bin/env python3
"""Audit the frozen v17 scorer attempts locally; never invokes a model."""
from pathlib import Path

import g5_audit_catalog_evidence_calibration as audit


audit.INPUT = Path(
    "research/experiments/2026-09-14-g5-fresh-family-v17-scorer-preflight/inputs.json")
audit.OUTPUT = Path(
    "research/experiments/2026-09-15-g5-fresh-family-v17-scorer-predictions")


if __name__ == "__main__":
    audit.main()
