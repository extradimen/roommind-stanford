#!/usr/bin/env python3
"""Run the frozen semantic-scoring calibration using the immutable v4 runner."""
import asyncio
from pathlib import Path

import g5_run_catalog_evidence_calibration as runner


runner.INPUT = Path("research/experiments/2026-09-12-g5-semantic-scoring-calibration-inputs/inputs.json")
runner.OUTPUT = Path("research/experiments/2026-09-12-g5-semantic-scoring-calibration-predictions")


if __name__ == "__main__":
    try:
        asyncio.run(runner.run())
    except Exception as error:
        print("Stopped safely: " + type(error).__name__, flush=True)
        raise SystemExit(1)
