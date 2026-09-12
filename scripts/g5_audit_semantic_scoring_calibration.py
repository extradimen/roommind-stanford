#!/usr/bin/env python3
"""Audit semantic-scoring calibration without making model calls."""
from pathlib import Path

import g5_audit_catalog_evidence_calibration as audit


audit.INPUT = Path("research/experiments/2026-09-12-g5-semantic-scoring-calibration-inputs/inputs.json")
audit.OUTPUT = Path("research/experiments/2026-09-12-g5-semantic-scoring-calibration-predictions")


if __name__ == "__main__":
    audit.main()
