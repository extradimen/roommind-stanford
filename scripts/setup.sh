#!/usr/bin/env bash
# 兼容旧用法：等价于 ./start.sh（首次会自动安装依赖）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/start.sh"
