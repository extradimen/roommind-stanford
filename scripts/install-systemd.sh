#!/usr/bin/env bash
# 安装 systemd 用户服务：开机自启 + 崩溃自动重启
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
USER_UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNIT_FILE="$USER_UNIT_DIR/roommind.service"

mkdir -p "$USER_UNIT_DIR"

cat > "$UNIT_FILE" <<EOF
[Unit]
Description=RoomMind (API + Admin + Client)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$ROOT
ExecStart=/bin/bash $ROOT/start.sh
ExecStop=/bin/bash $ROOT/stop.sh
TimeoutStartSec=300

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable roommind.service

echo "已安装: $UNIT_FILE"
echo ""
echo "常用命令:"
echo "  立即启动: systemctl --user start roommind"
echo "  停止:     systemctl --user stop roommind"
echo "  状态:     systemctl --user status roommind"
echo "  日志:     journalctl --user -u roommind -f"
echo ""
echo "若希望注销 SSH 后仍运行，请执行一次:"
echo "  loginctl enable-linger \$USER"
