"""Write the v2 frame, roles and scorer plan to a new directory."""
import argparse
import json
import os
from pathlib import Path

from app.g5.fresh_family_frame_v2 import fresh_family_frame_v2, validate_fresh_family_frame_v2
from app.g5.fresh_family_roles_v2 import fresh_family_role_pack_v2, validate_fresh_family_role_pack_v2
from app.g5.fresh_validation_plan_v2 import fresh_validation_plan_v2, validate_fresh_validation_plan_v2


def write(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True)
        stream.flush(); os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True)
    args = parser.parse_args()
    directory = Path(args.directory)
    directory.mkdir(parents=False, exist_ok=False)
    values = {"frame.json": validate_fresh_family_frame_v2(fresh_family_frame_v2()),
              "roles.json": validate_fresh_family_role_pack_v2(fresh_family_role_pack_v2()),
              "scorer-validation-plan.json": validate_fresh_validation_plan_v2(fresh_validation_plan_v2())}
    for name, value in values.items(): write(directory / name, value)
    print(json.dumps({name: value["sha256"] for name, value in values.items()}, sort_keys=True))


if __name__ == "__main__": main()
