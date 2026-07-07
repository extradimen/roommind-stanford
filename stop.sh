#!/usr/bin/env bash
# RoomMind 停止全部服务

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$ROOT/scripts/stop-all.sh"
