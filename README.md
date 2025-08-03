# 🚀 高效视频剪辑工具

一个基于 FFmpeg 的高效视频片段提取工具，使用 Gradio 构建的现代化 Web 界面。

## ✨ 特性

- 🎯 **精确切割** - 从任何时间点开始都能正常播放
- 🚀 **高效快速** - 使用 FFmpeg 的 ultrafast 预设
- 🎵 **音视频同步** - 完美解决同步问题
- 💻 **低 CPU 使用率** - 不会让电脑满负荷运行
- 📱 **用户友好** - 现代化的 Web 界面
- 🕐 **灵活时间格式** - 支持 MM:SS 和 HH:MM:SS 格式

## 🛠️ 环境要求

- Python 3.8+
- FFmpeg (已通过 Homebrew 安装)
- macOS/Linux/Windows

## 📦 安装和设置

### 1. 克隆项目
```bash
git clone <your-repo-url>
cd VideoCut
```

### 2. 创建并激活虚拟环境
```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
# macOS/Linux:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate
```

### 3. 安装依赖
```bash
# 确保在虚拟环境中
pip install -r requirements.txt
```

### 4. 验证 FFmpeg 安装
```bash
which ffmpeg
# 应该显示: /opt/homebrew/bin/ffmpeg (macOS) 或其他路径
```

## 🚀 运行应用

### 方法 1: 直接运行（推荐）
```bash
# 确保虚拟环境已激活
source .venv/bin/activate
python3 app.py
```

### 方法 2: 使用虚拟环境中的 Python
```bash
.venv/bin/python app.py
```

### 方法 3: 创建启动脚本
```bash
# 创建启动脚本
echo '#!/bin/bash
source .venv/bin/activate
python3 app.py' > start.sh
chmod +x start.sh

# 运行
./start.sh
```

## 🌐 访问应用

启动后，在浏览器中访问：
- 本地访问: http://127.0.0.1:7870
- 网络访问: 设置 `share=True` 在 `app.py` 中

## 📖 使用说明

1. **上传视频** - 支持大多数视频格式，最大 3GB
2. **输入时间** - 支持格式：
   - `MM:SS` (如: 1:50, 4:00)
   - `HH:MM:SS` (如: 1:30:45)
3. **提取片段** - 点击"🚀 快速提取片段"按钮
4. **预览结果** - 在右侧预览生成的视频片段

## 🔧 技术细节

### FFmpeg 参数说明
```bash
ffmpeg -i input.mp4 -ss 00:01:50.000 -t 130.0 \
       -c:v libx264 -c:a aac \
       -preset ultrafast -crf 23 \
       -avoid_negative_ts make_zero \
       -fflags +genpts -y output.mp4
```

- `-c:v libx264` - 使用 H.264 视频编码器
- `-c:a aac` - 使用 AAC 音频编码器
- `-preset ultrafast` - 最快编码预设
- `-crf 23` - 保持良好质量
- `-fflags +genpts` - 生成新的时间戳

### 依赖包
- `gradio>=4.0.0` - Web 界面框架
- FFmpeg - 视频处理引擎（系统级依赖）

## 🐛 故障排除

### 虚拟环境问题
```bash
# 检查虚拟环境状态
which python3
# 应该显示: /path/to/VideoCut/.venv/bin/python3

# 重新创建虚拟环境
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### FFmpeg 问题
```bash
# 检查 FFmpeg 安装
ffmpeg -version

# macOS 安装 FFmpeg
brew install ffmpeg

# Ubuntu/Debian 安装 FFmpeg
sudo apt update
sudo apt install ffmpeg
```

### 权限问题
```bash
# 确保脚本可执行
chmod +x start.sh
```

## 📝 开发说明

### 项目结构
```
VideoCut/
├── app.py              # 主应用程序
├── requirements.txt    # Python 依赖
├── .venv/             # 虚拟环境
├── README.md          # 项目说明
└── 历史文件/          # 历史版本
```

### 添加新功能
1. 在虚拟环境中开发
2. 更新 `requirements.txt`
3. 测试功能
4. 更新文档

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

---

**注意**: 始终在虚拟环境中运行应用程序，避免依赖冲突！ 