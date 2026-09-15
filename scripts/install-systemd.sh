#!/usr/bin/env bash
# 安装 systemd 用户服务：API / Admin / Client 独立守护与崩溃自动重启
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
USER_UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
TARGET_FILE="$USER_UNIT_DIR/roommind.target"

mkdir -p "$USER_UNIT_DIR"

set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a
API_PORT="${API_PORT:-8800}"
ADMIN_PORT="${ADMIN_PORT:-5180}"
CLIENT_PORT="${CLIENT_PORT:-5181}"

cat > "$USER_UNIT_DIR/roommind-api.service" <<EOF
[Unit]
Description=RoomMind API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$ROOT
EnvironmentFile=$ROOT/.env
ExecStart=$ROOT/.venv/bin/uvicorn app.main:app --app-dir server --host 0.0.0.0 --port ${API_PORT}
Restart=always
RestartSec=3
TimeoutStopSec=30

[Install]
WantedBy=roommind.target
EOF

cat > "$USER_UNIT_DIR/roommind-admin.service" <<EOF
[Unit]
Description=RoomMind Admin UI
After=roommind-api.service

[Service]
Type=simple
WorkingDirectory=$ROOT/admin
EnvironmentFile=$ROOT/.env
ExecStart=/usr/bin/env npx vite --host --port ${ADMIN_PORT} --strictPort
Restart=always
RestartSec=3

[Install]
WantedBy=roommind.target
EOF

cat > "$USER_UNIT_DIR/roommind-client.service" <<EOF
[Unit]
Description=RoomMind Client UI
After=roommind-api.service

[Service]
Type=simple
WorkingDirectory=$ROOT/client
EnvironmentFile=$ROOT/.env
ExecStart=/usr/bin/env npx vite --host --port ${CLIENT_PORT} --strictPort
Restart=always
RestartSec=3

[Install]
WantedBy=roommind.target
EOF

cat > "$TARGET_FILE" <<EOF
[Unit]
Description=RoomMind services
Wants=roommind-api.service roommind-admin.service roommind-client.service
After=network-online.target

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user disable roommind.service >/dev/null 2>&1 || true
systemctl --user enable roommind.target roommind-api.service roommind-admin.service roommind-client.service

echo "已安装: $TARGET_FILE + 3 个独立服务"
echo ""
echo "常用命令:"
echo "  立即启动: systemctl --user start roommind.target"
echo "  停止:     systemctl --user stop roommind.target"
echo "  状态:     systemctl --user status roommind-api roommind-admin roommind-client"
echo "  日志:     journalctl --user -u roommind-api -f"
echo ""
echo "若希望注销 SSH 后仍运行，请执行一次:"
echo "  loginctl enable-linger \$USER"
