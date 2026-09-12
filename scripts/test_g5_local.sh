#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${G5_PYTHON:-$repo_root/.venv312/bin/python}"

if [[ ! -x "$python_bin" ]]; then
  echo "G5 Python is not executable: $python_bin" >&2
  exit 2
fi

# ONNX Runtime official macOS builds can abort in PosixTelemetry::Shutdown.
# Set this before Python imports any dependency; subprocesses inherit it.
export ORT_DISABLE_TELEMETRY=1
export PYTHONPATH="$repo_root/server:$repo_root/server/tests"

cd "$repo_root"
exec "$python_bin" -m unittest discover -s server/tests -p 'test_g5_*.py'
