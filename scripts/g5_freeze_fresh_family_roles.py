#!/usr/bin/env python3
"""Write the fresh-family role pack exactly once."""
import json
import os
from pathlib import Path

from app.g5.fresh_family_roles import fresh_family_role_pack, validate_fresh_family_role_pack


OUTPUT = Path("research/experiments/2026-09-12-g5-fresh-family-frame/roles.json")


def main():
    pack = validate_fresh_family_role_pack(fresh_family_role_pack())
    fd = os.open(OUTPUT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(pack, stream, ensure_ascii=False, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"scenarios": len(pack["scenario_roles"]), "sha256": pack["sha256"],
                      "external_execution_authorized": False}))


if __name__ == "__main__":
    main()
