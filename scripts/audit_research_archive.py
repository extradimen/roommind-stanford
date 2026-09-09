"""Inventory historical evidence without importing generation or probe code.

An existing inventory is verification-only. New inventories use exclusive
creation; neither evidence nor an earlier inventory is ever overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def inventory(root: Path) -> dict:
    paths = set((root / "research/experiments").rglob("*"))
    paths.update((root / "docs").glob("*.md"))
    files = {}
    for path in sorted(paths):
        if path.is_file() and not path.is_symlink():
            files[path.relative_to(root).as_posix()] = {
                "bytes": path.stat().st_size, "sha256": digest(path),
            }
    return {"schema": "roommind-archive-inventory-v1", "files": files}


def verify(root: Path, saved: dict) -> dict:
    missing, changed = [], []
    for relative, entry in saved["files"].items():
        path = root / relative
        if not path.is_file():
            missing.append(relative)
        elif digest(path) != entry["sha256"]:
            changed.append(relative)
    return {"checked": len(saved["files"]), "missing": missing,
            "changed": changed, "passed": not (missing or changed)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--create", type=Path)
    group.add_argument("--verify", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.create:
        result = inventory(root)
        args.create.parent.mkdir(parents=True, exist_ok=True)
        with args.create.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print(json.dumps({"inventoried": len(result["files"]),
                          "bytes": sum(v["bytes"] for v in result["files"].values())}))
    else:
        with args.verify.open(encoding="utf-8") as stream:
            result = verify(root, json.load(stream))
        print(json.dumps(result))
        if not result["passed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
