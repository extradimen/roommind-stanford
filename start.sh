#!/usr/bin/env bash
# RoomMind 一键启动（后台守护进程，终端关闭后服务继续运行）

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source "$ROOT/scripts/_lib.sh"

LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

start_api() {
  local port="${API_PORT:-8800}"
  local pid_file="$LOG_DIR/api.pid"
  local venv
  venv="$(roommind_venv "$ROOT")"

  if roommind_is_running "$pid_file" "$port"; then
    roommind_warn "API 已在运行 (端口 :${port})"
    return
  fi

  roommind_stop_port "$port"
  rm -f "$pid_file"

  local uvicorn_args=(app.main:app --app-dir server --host "${API_HOST:-0.0.0.0}" --port "$port")
  if [[ "${ROOMMIND_DEV:-0}" == "1" ]]; then
    uvicorn_args+=(--reload)
    roommind_warn "开发模式 ROOMMIND_DEV=1：启用 --reload（不适合长期后台）"
  fi

  local pid
  pid="$(roommind_daemon_start "$LOG_DIR/api.log" "$venv/bin/uvicorn" "${uvicorn_args[@]}")"
  echo "$pid" > "$pid_file"
  roommind_info "API 已在后台启动 → http://${API_HOST:-0.0.0.0}:$port (pid $pid)"
}

start_npm_app() {
  local name="$1"
  local dir="$2"
  local port="$3"
  local pub_host="$4"
  local pid_file="$LOG_DIR/${name}.pid"
  local log_file="$LOG_DIR/${name}.log"

  if roommind_is_running "$pid_file" "$port"; then
    roommind_warn "$name 已在运行 (端口 :${port})"
    return
  fi

  if [[ -f "$pid_file" ]]; then
    local old_pid
    old_pid="$(cat "$pid_file")"
    kill "$old_pid" 2>/dev/null || true
    rm -f "$pid_file"
  fi
  roommind_stop_port "$port"
  pkill -f "${ROOT}/${dir}/node_modules/.bin/vite" 2>/dev/null || true

  local pid
  pid="$(roommind_daemon_start "$log_file" bash -c "cd '$ROOT/$dir' && set -a && source '$ROOT/.env' && set +a && exec npx vite --host --port '$port' --strictPort")"
  echo "$pid" > "$pid_file"
  roommind_info "$name 已在后台启动 → http://${pub_host}:$port (pid $pid)"
}

main() {
  roommind_info "=== RoomMind 后台启动 ==="
  roommind_bootstrap "$ROOT"

  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a

  local pub_host
  pub_host="$(roommind_resolve_public_host "$ROOT")"

  start_api
  start_npm_app admin admin "${ADMIN_PORT:-5180}" "$pub_host"
  start_npm_app client client "${CLIENT_PORT:-5181}" "$pub_host"

  sleep 3
  echo ""
  roommind_info "=== 服务状态（已与终端分离，可安全关闭 SSH）==="
  if port_listening "${API_PORT:-8800}"; then
    echo "  API:    http://${pub_host}:${API_PORT:-8800}/health  ✓"
  else
    echo "  API:    ✗ 见 logs/api.log"
  fi
  if port_listening "${ADMIN_PORT:-5180}"; then
    echo "  Admin:  http://${pub_host}:${ADMIN_PORT:-5180}  ✓"
  else
    echo "  Admin:  ✗ 见 logs/admin.log"
  fi
  if port_listening "${CLIENT_PORT:-5181}"; then
    echo "  Client: http://${pub_host}:${CLIENT_PORT:-5181}  ✓"
  else
    echo "  Client: ✗ 见 logs/client.log"
  fi
  echo ""
  echo "  查看状态: ./status.sh"
  echo "  停止服务: ./stop.sh"
  echo "  查看日志: tail -f logs/api.log logs/admin.log logs/client.log"
  echo "  开机自启: bash scripts/install-systemd.sh"
}

main "$@"
