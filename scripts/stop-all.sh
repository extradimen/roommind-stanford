#!/usr/bin/env bash
# RoomMind 停止全部后台服务

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/_lib.sh"

LOG_DIR="$ROOT/logs"

set -a
# shellcheck disable=SC1091
[[ -f "$ROOT/.env" ]] && source "$ROOT/.env"
set +a

stop_named() {
  local name="$1"
  local port="$2"
  local pid_file="$LOG_DIR/${name}.pid"

  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
    echo "Stopped $name (pid $pid)"
  fi

  if port_listening "$port"; then
    roommind_stop_port "$port"
    echo "Stopped $name (port $port)"
  fi
}

stop_named api "${API_PORT:-8800}"
stop_named admin "${ADMIN_PORT:-5180}"
stop_named client "${CLIENT_PORT:-5181}"

pkill -f "${ROOT}/admin/node_modules/.bin/vite" 2>/dev/null || true
pkill -f "${ROOT}/client/node_modules/.bin/vite" 2>/dev/null || true
pkill -f "${ROOT}/admin/node_modules/.bin/esbuild" 2>/dev/null || true
pkill -f "${ROOT}/client/node_modules/.bin/esbuild" 2>/dev/null || true
pkill -f "${ROOT}/.venv/bin/uvicorn" 2>/dev/null || true

echo "Done."
