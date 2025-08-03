#!/bin/bash

# 高效视频剪辑工具启动脚本

echo "🚀 启动高效视频剪辑工具..."

# 检查虚拟环境是否存在
if [ ! -d ".venv" ]; then
    echo "❌ 虚拟环境不存在，正在创建..."
    python3 -m venv .venv
fi

# 激活虚拟环境
echo "📦 激活虚拟环境..."
source .venv/bin/activate

# 检查依赖是否安装
if ! python3 -c "import gradio" 2>/dev/null; then
    echo "📥 安装依赖包..."
    pip install -r requirements.txt
fi

# 检查 FFmpeg 是否可用
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ FFmpeg 未安装，请先安装 FFmpeg:"
    echo "   macOS: brew install ffmpeg"
    echo "   Ubuntu: sudo apt install ffmpeg"
    exit 1
fi

echo "✅ 环境检查完成"
echo "🌐 启动应用程序..."
echo "📱 访问地址: http://127.0.0.1:7870"
echo "⏹️  按 Ctrl+C 停止应用"
echo ""

# 运行应用程序
python3 app.py 