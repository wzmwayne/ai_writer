#!/bin/sh
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
VENV="$ROOT/venv"

echo "================================================"
echo "  AI Novel Forge — 小说创作工坊启动脚本"
echo "================================================"

# 1. 虚拟环境
if [ ! -f "$VENV/bin/python3" ]; then
    echo "[*] 创建虚拟环境..."
    python3 -m venv "$VENV"
fi
. "$VENV/bin/activate"

# 2. 安装依赖
PIP_MIRROR="-i https://pypi.tuna.tsinghua.edu.cn/simple"
if [ ! -f "$VENV/.deps_ok" ]; then
    echo "[*] 安装依赖（清华源）..."
    pip install $PIP_MIRROR -r "$BACKEND/requirements.txt"
    pip install $PIP_MIRROR python-dotenv markdown
    touch "$VENV/.deps_ok"
fi

# 3. 数据目录
mkdir -p "$BACKEND/novels"

# 4. 端口查重与重启
PORT=8000
if command -v lsof >/dev/null 2>&1; then
    OLD_PID=$(lsof -ti tcp:$PORT 2>/dev/null || true)
elif command -v fuser >/dev/null 2>&1; then
    OLD_PID=$(fuser $PORT/tcp 2>/dev/null | awk '{print $1}' || true)
else
    OLD_PID=$(ss -tlnp 2>/dev/null | grep ":$PORT " | grep -oP 'pid=\K[0-9]+' || true)
fi
if [ -n "$OLD_PID" ]; then
    echo "[!] 端口 $PORT 已被 PID=$OLD_PID 占用，正在关闭旧进程..."
    kill "$OLD_PID" 2>/dev/null || true
    sleep 1
    # 强制终止（如果未退出）
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[!] 强制终止..."
        kill -9 "$OLD_PID" 2>/dev/null || true
        sleep 1
    fi
    echo "[✓] 旧进程已关闭"
fi

# 5. 启动
cd "$BACKEND"
echo "[✓] http://0.0.0.0:8000"
python3 main.py
