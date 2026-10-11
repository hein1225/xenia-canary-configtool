#!/usr/bin/env bash
# 在无头环境下启动 GUI 并截图，用于开发验证。
# 用法: tools/screenshot.sh <输出文件> [等待秒数] [模拟按键脚本]
set -u

OUT="${1:-/workspace/code/xenia-canary-configtool/build/shot.png}"
WAIT="${2:-6}"
ACTIONS="${3:-}"

export DISPLAY=:99
export XDG_SESSION_TYPE=x11

# 启动 Xvfb（若未运行）
if ! xdpyinfo -display :99 >/dev/null 2>&1; then
  Xvfb :99 -screen 0 1280x800x24 >/tmp/xvfb.log 2>&1 &
  sleep 2
fi

# 让窗口管理器不需要；直接跑应用
cd /workspace/code/xenia-canary-configtool
python3 src/app.py >/tmp/app.log 2>&1 &
APP_PID=$!

sleep "$WAIT"

if [ -n "$ACTIONS" ]; then
  bash "$ACTIONS" || true
  sleep 2
fi

import -display :99 -window root "$OUT" 2>/dev/null || \
  xwd -display :99 -root -silent | convert xwd:- "$OUT"

echo "截图: $OUT"
kill $APP_PID 2>/dev/null
wait $APP_PID 2>/dev/null
echo "--- 应用日志 ---"
tail -20 /tmp/app.log
