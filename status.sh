#!/usr/bin/env bash
# RoomMind 服务状态

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/_lib.sh"

LOG_DIR="$ROOT/logs"

set -a
# shellcheck disable=SC1091
[[ -f "$ROOT/.env" ]] && source "$ROOT/.env"
set +a

pub_host="$(roommind_resolve_public_host "$ROOT")"

check_one() {
  local name="$1"
  local port="$2"
  local pid_file="$LOG_DIR/${name}.pid"
  local pid="-"
  [[ -f "$pid_file" ]] && pid="$(cat "$pid_file")"

  if port_listening "$port"; then
    echo "  $name :$port  ✓ 运行中 (pid $pid)"
  else
    echo "  $name :$port  ✗ 未运行"
  fi
}

roommind_info "=== RoomMind 状态 ==="
check_one API "${API_PORT:-8800}"
check_one Admin "${ADMIN_PORT:-5180}"
check_one Client "${CLIENT_PORT:-5181}"

if port_listening "${API_PORT:-8800}"; then
  if curl -sf "http://127.0.0.1:${API_PORT:-8800}/health" >/dev/null; then
    echo "  health  ✓"
  else
    echo "  health  ✗ API 端口在监听但 /health 失败"
  fi
fi

echo ""
echo "  访问: http://${pub_host}:${ADMIN_PORT:-5180} (管理)  http://${pub_host}:${CLIENT_PORT:-5181} (学员)"
echo "  日志: $LOG_DIR/"
