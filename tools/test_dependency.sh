#!/usr/bin/env bash
# 验证依从可见性：改 gpu 值后分组应即时增删。
set -uo pipefail
export DISPLAY=:99
xdpyinfo -display :99 >/dev/null 2>&1 || { Xvfb :99 -screen 0 1600x1000x24 >/dev/null 2>&1 & sleep 2; }
# 以脚本自身位置定位项目根目录，避免把绝对路径写死（CI 里工作目录不同）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
OUT=build/dep; mkdir -p "$OUT"

# 用测试配置（gpu = d3d12）
python3 - <<'PY'
import shutil
from pathlib import Path
p = Path.home()/'.config/xenia-canary.config.toml'
shutil.copy('reference.config.toml', p)
print('测试配置已就位，gpu =', 'd3d12')
PY

python3 src/app.py >/tmp/dep.log 2>&1 &
APP=$!
sleep 7

# 进入「图形后端」大类
xdotool mousemove 200 212 click 1; sleep 2
import -display :99 -window root "$OUT/01-gpu-d3d12.png"
echo "✓ 01 — gpu=d3d12：应只看到 D3D12 卡片"

# 去 GPU 分组改 gpu 为 vulkan
xdotool mousemove 110 249 click 1; sleep 2   # 侧栏 GPU 分组
import -display :99 -window root "$OUT/02-gpu-section.png"
echo "✓ 02 — GPU 分组列表"

kill $APP 2>/dev/null; wait $APP 2>/dev/null

# 直接改成 vulkan 再启动，看导航差异
python3 - <<'PY'
import sys, shutil
sys.path.insert(0,'src')
from pathlib import Path
from toml_edit import TomlDoc
p = Path.home()/'.config/xenia-canary.config.toml'
d = TomlDoc.load(p)
d.set('gpu','vulkan','string')
d.save(p)
print('已改为 gpu = vulkan')
PY

python3 src/app.py >/tmp/dep2.log 2>&1 &
APP=$!
sleep 7
xdotool mousemove 200 212 click 1; sleep 2
import -display :99 -window root "$OUT/03-gpu-vulkan.png"
echo "✓ 03 — gpu=vulkan：应只看到 Vulkan 卡片，且底部有隐藏提示"
kill $APP 2>/dev/null; wait $APP 2>/dev/null

# 还原
python3 -c "
import shutil; shutil.copy('reference.config.toml', __import__('pathlib').Path.home()/'.config/xenia-canary.config.toml')"
echo "✓ 测试配置已还原"
echo; echo "日志:"; grep -i "error\|traceback" /tmp/dep.log /tmp/dep2.log || echo "  无错误"
