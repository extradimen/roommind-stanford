#!/usr/bin/env bash
# RoomMind 脚本公共函数

roommind_info() { echo -e "\033[0;32m[roommind]\033[0m $*"; }
roommind_warn() { echo -e "\033[1;33m[roommind]\033[0m $*"; }
roommind_err()  { echo -e "\033[0;31m[roommind]\033[0m $*" >&2; }

roommind_need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    roommind_err "缺少命令: $1"
    exit 1
  fi
}

roommind_venv() {
  echo "$1/.venv"
}

roommind_python() {
  echo "$(roommind_venv "$1")/bin/python"
}

roommind_ensure_env() {
  local root="$1"
  if [[ ! -f "$root/.env" ]]; then
    cp "$root/.env.example" "$root/.env"
    roommind_info "已从 .env.example 创建 .env"
  fi
}

# 首次创建 .venv 并安装根目录 requirements.txt；之后仅在 requirements 变更时重装
roommind_install_python_deps() {
  local root="$1"
  local venv
  venv="$(roommind_venv "$root")"
  local req="$root/requirements.txt"
  local marker="$venv/.deps_installed"

  roommind_need_cmd python3

  if [[ ! -f "$req" ]]; then
    roommind_err "未找到 $req"
    exit 1
  fi

  if [[ ! -d "$venv" ]]; then
    roommind_info "创建 Python 虚拟环境: $venv"
    python3 -m venv "$venv"
  fi

  local reinstall=0
  if [[ ! -f "$marker" ]]; then
    reinstall=1
  elif [[ "$req" -nt "$marker" ]]; then
    roommind_warn "requirements.txt 已更新，重新安装 Python 依赖..."
    reinstall=1
  fi

  if [[ "$reinstall" -eq 1 ]]; then
    roommind_info "安装 Python 依赖（首次或更新后，可能需要几分钟）..."
    "$venv/bin/pip" install -U pip setuptools wheel -q
    "$venv/bin/pip" install -r "$req" -q
    touch "$marker"
    roommind_info "Python 依赖安装完成"
  else
    roommind_info "Python 依赖已就绪，跳过安装"
  fi

  if [[ ! -x "$venv/bin/uvicorn" ]]; then
    roommind_err "虚拟环境中未找到 uvicorn，请删除 .venv 后重新运行 ./start.sh"
    exit 1
  fi
}

roommind_install_npm_deps() {
  local root="$1"
  local dir="$2"
  local full="$root/$dir"

  roommind_need_cmd npm
  if [[ ! -d "$full/node_modules" ]] \
    || [[ "$full/package.json" -nt "$full/node_modules/.package-lock.json" ]]; then
    roommind_info "安装 $dir 前端依赖..."
    (cd "$full" && npm install --silent)
  else
    roommind_info "$dir 前端依赖已就绪，跳过安装"
  fi
}

roommind_sync_platform_config() {
  local root="$1"
  (cd "$root" && "$(roommind_python "$root")" - <<'PY'
import sys
sys.path.insert(0, "server")
from app.platform_config import load_platform_config, save_platform_config
save_platform_config(load_platform_config())
PY
  )
}

roommind_try_docker_services() {
  local root="$1"
  if ! command -v docker >/dev/null 2>&1; then
    roommind_warn "未检测到 docker；使用本机 PostgreSQL / Redis（端口见 config/platform.json）"
    return 0
  fi

  set -a
  # shellcheck disable=SC1091
  source "$root/.env"
  set +a

  roommind_info "启动 Docker PostgreSQL / Redis..."
  (cd "$root" && docker compose up -d 2>/dev/null) || true

  if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^roommind-postgres$'; then
    local i=0
    until docker exec roommind-postgres pg_isready -U "${POSTGRES_USER:-roommind}" >/dev/null 2>&1; do
      sleep 1
      i=$((i + 1))
      [[ "$i" -lt 60 ]] || { roommind_err "PostgreSQL 启动超时"; exit 1; }
    done
  fi
}

# 启动前检查 venv 与前端依赖（start.sh 每次启动前调用，内部会跳过已完成的步骤）
roommind_resolve_public_host() {
  local root="$1"
  local configured="auto"
  if [[ -f "$root/.env" ]]; then
    configured="$(grep -E '^PUBLIC_HOST=' "$root/.env" 2>/dev/null | cut -d= -f2- || echo auto)"
  fi
  configured="${configured:-auto}"
  if [[ "$configured" != "auto" && -n "$configured" && "$configured" != "localhost" ]]; then
    echo "$configured"
    return
  fi
  local ip
  ip="$(curl -fsS --max-time 2 http://checkip.amazonaws.com 2>/dev/null | tr -d '[:space:]')"
  if [[ -z "$ip" ]]; then
    ip="$(curl -fsS --max-time 2 https://api.ipify.org 2>/dev/null | tr -d '[:space:]')"
  fi
  if [[ -z "$ip" ]]; then
    ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") {print $(i+1); exit}}')"
  fi
  echo "${ip:-localhost}"
}

roommind_bootstrap() {
  local root="$1"
  roommind_ensure_env "$root"
  roommind_install_python_deps "$root"
  roommind_sync_platform_config "$root"
  roommind_install_npm_deps "$root" admin
  roommind_install_npm_deps "$root" client
  roommind_try_docker_services "$root"
}

# 后台守护启动（新会话 + nohup，终端关闭不影响）
roommind_daemon_start() {
  local log_file="$1"
  shift
  setsid nohup "$@" >> "$log_file" 2>&1 &
  local pid=$!
  disown "$pid" 2>/dev/null || true
  echo "$pid"
}

roommind_port_pids() {
  local port="$1"
  ss -tlnp 2>/dev/null | grep ":${port} " 2>/dev/null | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | sort -u || true
}

port_listening() {
  ss -tlnp 2>/dev/null | grep -q ":$1 " || return 1
  return 0
}

roommind_stop_port() {
  local port="$1"
  local pids
  pids="$(roommind_port_pids "$port" | tr '\n' ' ')"
  if [[ -n "${pids// /}" ]]; then
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 1
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
  fi
}

roommind_is_running() {
  local pid_file="$1"
  local port="$2"
  if port_listening "$port"; then
    return 0
  fi
  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    return 0
  fi
  return 1
}
