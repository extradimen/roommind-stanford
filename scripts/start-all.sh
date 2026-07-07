#!/usr/bin/env bash
# 兼容旧用法：等价于 ./start.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/start.sh"
