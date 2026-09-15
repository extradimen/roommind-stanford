#!/usr/bin/env python3
"""Run G5 fresh-family v9 after conservative repair qualification passes."""
import argparse
import asyncio
import fcntl
import json
import os
from pathlib import Path

from dotenv import dotenv_values

from app.g5.fresh_execution_v9 import execution_binding, run_execution


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--authorization-id", required=True)
    parser.add_argument("--predecessor-execution-sha256", required=True)
    parser.add_argument("--credential-source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--base-url", default="https://ollama.com")
    args = parser.parse_args()
    values = dotenv_values(args.credential_source)
    key = values.get("OLLAMA_API_KEY") or values.get("OLLAMA_CLOUD_API_KEY")
    if not key:
        raise SystemExit("Explicit credential source has no Ollama key")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(output / "worker.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        execution = execution_binding(
            args.source_revision,
            authorization_id=args.authorization_id,
            predecessor_execution_sha256=args.predecessor_execution_sha256,
        )
        result = asyncio.run(run_execution(execution, output, api_key=key,
                                            base_url=args.base_url))
        print(json.dumps({"status": "complete", "sha256": result["sha256"]}), flush=True)
    finally:
        os.close(lock_fd)


if __name__ == "__main__":
    main()
