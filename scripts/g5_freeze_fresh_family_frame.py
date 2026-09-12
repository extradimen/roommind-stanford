#!/usr/bin/env python3
"""Write the pre-generation fresh-family frame exactly once."""
import json
import os
from pathlib import Path

from app.g5.fresh_family_frame import fresh_family_frame, validate_fresh_family_frame


OUTPUT = Path("research/experiments/2026-09-12-g5-fresh-family-frame/frame.json")


def main():
    frame = validate_fresh_family_frame(fresh_family_frame())
    OUTPUT.parent.mkdir(mode=0o700, exist_ok=True)
    fd = os.open(OUTPUT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(frame, stream, ensure_ascii=False, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"families": len(frame["families"]), "worlds": len(frame["worlds"]),
                      "sha256": frame["sha256"], "external_execution_authorized": False}))


if __name__ == "__main__":
    main()
