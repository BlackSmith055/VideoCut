import gradio as gr
import re
import tempfile
import os
from moviepy.editor import VideoFileClip

# --- Utility: 时间格式解析 ---
def time_to_seconds(time_str: str) -> float:
    """
    将格式 HH:MM:SS 或 HH:MM:SS.ss 转换为秒（浮点数）。
    精确到小数点后两位。
    """
    pattern = r"^(?P<h>\d+):(?P<m>[0-5]\d):(?P<s>\d+(?:\.\d{1,2})?)$"
    m = re.match(pattern, time_str)
    if not m:
        raise ValueError(f"时间格式无效: {time_str}. 请使用 HH:MM:SS 或 HH:MM:SS.ss 格式。")
    h = int(m.group('h'))
    mnt = int(m.group('m'))
    sec = float(m.group('s'))
    return h * 3600 + mnt * 60 + sec

# --- Feature 1: 片段提取与预览 ---
def extract_segment(input_path: str, start_str: str, end_str: str):
    """
    从 input_path 中根据 start_str 和 end_str 提取视频片段，并返回临时文件路径以供预览。
    """
    try:
        start = time_to_seconds(start_str)
        end = time_to_seconds(end_str)
        if end <= start:
            raise ValueError("结束时间必须大于开始时间")
    except Exception as e:
        return gr.update(error=str(e))

    # 创建临时输出文件
    tmp_dir = tempfile.gettempdir()
    out_path = os.path.join(tmp_dir, f"segment_{int(start*100)}_{int(end*100)}.mp4")

    # 提取片段
    clip = VideoFileClip(input_path).subclip(start, end)
    clip.write_videofile(out_path, codec='libx264', audio_codec='aac', verbose=False, logger=None)
    return out_path

# --- Gradio 界面 & 绑定 ---
with gr.Blocks() as demo:
    gr.Markdown("## 本地视频剪辑工具 — 片段提取与预览")
    video_input = gr.Video(label="上传视频 (<=3GB)")
    start_time = gr.Textbox(label="开始时间 (HH:MM:SS 或 HH:MM:SS.ss)")
    end_time = gr.Textbox(label="结束时间 (HH:MM:SS 或 HH:MM:SS.ss)")
    preview = gr.Video(label="预览片段")
    
    extract_btn = gr.Button("提取并预览片段")
    extract_btn.click(fn=extract_segment,
                        inputs=[video_input, start_time, end_time],
                        outputs=[preview])

if __name__ == "__main__":
    demo.launch()
