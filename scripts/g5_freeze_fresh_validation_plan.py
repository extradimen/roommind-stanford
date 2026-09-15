"""Write the immutable pre-generation scorer-validation plan once."""
import argparse
import json
import os
from pathlib import Path

from app.g5.fresh_validation_plan import fresh_validation_plan, validate_fresh_validation_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    target = Path(args.output)
    value = validate_fresh_validation_plan(fresh_validation_plan())
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True)
        stream.flush(); os.fsync(stream.fileno())
    print(json.dumps({"assignments": len(value["assignments"]),
                      "expected_cases": value["analysis"]["expected_cases"],
                      "sha256": value["sha256"], "launch_authorized": False}, sort_keys=True))


if __name__ == "__main__":
    main()
