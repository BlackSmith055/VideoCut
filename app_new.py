import gradio as gr
import os

# 导入功能模块
from modules.video_extractor import extract_segment
from modules.video_cropper import (
    crop_video_with_tracking, 
    crop_with_person_tracking, 
    create_crop_preview_image,
    calculate_crop_box
)
from modules.subtitle_generator import generate_subtitles

# 导入工具函数
from utils.ffmpeg_utils import get_video_info

# --- 辅助函数 ---
def update_crop_preview(video_path, aspect_ratio, center_x, center_y, scale):
    """更新裁切预览"""
    if not video_path or not os.path.exists(video_path):
        return None
    
    return create_crop_preview_image(video_path, aspect_ratio, center_x, center_y, scale, scale)

def get_crop_parameters(video_path, aspect_ratio, center_x, center_y, scale):
    """获取裁切参数"""
    if not video_path or not os.path.exists(video_path):
        return 0.5, 0.5, 0.8, 0.8
    
    video_info = get_video_info(video_path)
    crop_box = calculate_crop_box(
        video_info['width'], 
        video_info['height'], 
        aspect_ratio, 
        center_x, 
        center_y, 
        scale
    )
    
    # 转换为相对坐标
    crop_x = crop_box['x'] / video_info['width']
    crop_y = crop_box['y'] / video_info['height']
    crop_width = crop_box['width'] / video_info['width']
    crop_height = crop_box['height'] / video_info['height']
    
    return crop_x, crop_y, crop_width, crop_height

def select_video_source(extracted_video, direct_video):
    """选择视频源"""
    if extracted_video and os.path.exists(extracted_video):
        return extracted_video, False  # 返回提取的视频，隐藏上传按钮
    else:
        return direct_video, True  # 返回直接上传的视频，显示上传按钮

def download_video_segment(video_path):
    """下载视频片段"""
    if video_path and os.path.exists(video_path):
        return gr.File.update(value=video_path, visible=True)
    else:
        return gr.File.update(value=None, visible=False)

def download_subtitle_file(subtitle_path):
    """下载字幕文件"""
    if subtitle_path and os.path.exists(subtitle_path):
        return gr.File.update(value=subtitle_path, visible=True)
    else:
        return gr.File.update(value=None, visible=False)

def update_video_display(extracted_video):
    """更新视频显示"""
    if extracted_video and os.path.exists(extracted_video):
        return extracted_video, False  # 显示提取的视频，隐藏上传按钮
    else:
        return None, True  # 不显示视频，显示上传按钮

# --- Gradio 界面 ---
with gr.Blocks(title="智能视频剪辑工具") as demo:
    gr.Markdown("## 🚀 智能视频剪辑工具 — 支持人物跟踪和字幕生成")
    gr.Markdown("**功能：** 视频片段提取 + 智能裁切 + 人物跟踪 + 字幕生成")
    
    # 存储提取的视频路径和字幕文件路径
    extracted_video = gr.State()
    subtitle_file_path = gr.State()
    
    with gr.Tabs():
        # 第一个标签页：视频片段提取
        with gr.TabItem("🎬 视频片段提取"):
            with gr.Row():
                with gr.Column():
                    video_input = gr.Video(label="上传视频 (<=3GB)")
                    
                    # 时间选择区域
                    with gr.Group():
                        gr.Markdown("### ⏰ 时间选择")
                        with gr.Row():
                            start_time = gr.Textbox(label="开始时间 (MM:SS 或 HH:MM:SS)", placeholder="例如: 1:50")
                            end_time = gr.Textbox(label="结束时间 (MM:SS 或 HH:MM:SS)", placeholder="例如: 4:00")
                        
                        # 时间轴选择提示
                        gr.Markdown("**💡 提示：** 也可以在下方视频预览中点击时间轴来设置开始和结束时间")
                    
                    extract_btn = gr.Button("🚀 快速提取片段", variant="primary")
                
                with gr.Column():
                    # 视频预览区域
                    with gr.Group():
                        gr.Markdown("### 📹 视频预览")
                        preview = gr.Video(label="预览片段", interactive=True)
                        
                        # 下载按钮
                        download_btn = gr.Button("⬇️ 下载视频片段", variant="secondary", visible=False)
                    
                    error_msg = gr.Textbox(label="状态信息", interactive=False, visible=True)
                    info_text = gr.Markdown("""
                    **使用说明：**
                    1. 上传视频文件
                    2. 选择时间范围：
                       - 手动输入开始和结束时间
                       - 或在视频预览中点击时间轴
                    3. 点击"快速提取片段"
                    4. 等待处理完成
                    5. 点击"下载视频片段"保存文件
                    
                    **时间格式支持：**
                    - `MM:SS` (如: 1:50, 4:00)
                    - `HH:MM:SS` (如: 1:30:45)
                    """)
            
            extract_btn.click(fn=extract_segment,
                             inputs=[video_input, start_time, end_time],
                             outputs=[preview, error_msg, extracted_video])
            
            # 当提取成功时显示下载按钮
            extract_btn.click(
                fn=lambda x: True if x else False,
                inputs=[extracted_video],
                outputs=[download_btn]
            )
            
            # 下载按钮功能
            download_btn.click(
                fn=download_video_segment,
                inputs=[extracted_video],
                outputs=[download_btn, error_msg]
            )
        
        # 第二个标签页：智能裁切
        with gr.TabItem("✂️ 智能视频裁切"):
            with gr.Row():
                with gr.Column():
                    # 视频输入区域
                    with gr.Group():
                        gr.Markdown("### 📹 视频输入")
                        # 统一的视频预览区域
                        crop_video_display = gr.Video(label="视频预览", interactive=True)
                        
                        # 条件显示的上传按钮
                        upload_btn = gr.Button("📁 上传视频文件", variant="secondary", visible=True)
                    
                    # 裁切设置
                    with gr.Group():
                        gr.Markdown("### ⚙️ 裁切设置")
                        aspect_ratio = gr.Radio(
                            choices=["3:4", "1:1"],
                            label="选择固定比例框",
                            value="3:4"
                        )
                    
                    # 裁切框控制
                    with gr.Row():
                        center_x = gr.Slider(0, 1, 0.5, label="框中心 X 位置", step=0.01)
                        center_y = gr.Slider(0, 1, 0.5, label="框中心 Y 位置", step=0.01)
                    
                    scale = gr.Slider(0.1, 1, 0.8, label="框缩放大小", step=0.01)
                    
                    with gr.Row():
                        update_preview_btn = gr.Button("🔄 更新预览", variant="secondary")
                        manual_crop_btn = gr.Button("✂️ 手动裁切", variant="primary")
                        auto_track_btn = gr.Button("🎯 人物跟踪裁切", variant="secondary")
                
                with gr.Column():
                    # 裁切预览图像
                    crop_preview_image = gr.Image(label="裁切框预览", type="filepath")
                    crop_preview = gr.Video(label="裁切结果预览")
                    crop_error_msg = gr.Textbox(label="裁切状态", interactive=False, visible=True)
                    crop_info = gr.Markdown("""
                    **裁切功能说明：**
                    
                    **视频输入方式：**
                    - **方式一**：在"视频片段提取"标签页提取视频片段，自动传递到此页面
                    - **方式二**：直接在此页面上传视频文件
                    
                    **使用步骤：**
                    1. 选择视频输入方式：
                       - 从第一步提取的视频片段会自动显示
                       - 或点击"上传视频文件"按钮上传新视频
                    2. 选择固定比例框 (3:4 或 1:1)
                    3. 调整框的位置和大小，框住要跟踪的人物
                    4. 点击"更新预览"查看裁切框
                    5. 选择裁切方式：
                       - **手动裁切**：固定位置裁切
                       - **人物跟踪裁切**：动态跟踪人物移动
                    
                    **裁切框操作：**
                    - 拖动滑块调整裁切框位置和大小
                    - 裁切框会保持选择的比例
                    - 确保框内包含要跟踪的人物
                    
                    **人物跟踪功能：**
                    - 自动检测框内的人物
                    - 实时跟踪人物移动
                    - 裁切框会跟随人物移动
                    - 保持人物在画面中心
                    
                    **3:4 比例：** 适合竖屏短视频
                    **1:1 比例：** 适合方形视频
                    
                    **💡 提示：** 视频预览区域会智能显示当前可用的视频
                    """)
            
            # 当提取的视频更新时，更新裁切界面的视频显示和上传按钮状态
            extracted_video.change(
                fn=update_video_display,
                inputs=[extracted_video],
                outputs=[crop_video_display, upload_btn]
            )
            
            # 当上传按钮被点击时，允许用户上传视频
            upload_btn.click(
                fn=lambda x: x,
                inputs=[upload_btn],
                outputs=[crop_video_display]
            )
            
            # 当比例改变时，更新预览
            aspect_ratio.change(
                fn=lambda video, ratio, cx, cy, s: update_crop_preview(video, ratio, cx, cy, s),
                inputs=[crop_video_display, aspect_ratio, center_x, center_y, scale],
                outputs=[crop_preview_image]
            )
            
            # 当位置或缩放改变时，更新预览
            center_x.change(
                fn=lambda video, ratio, cx, cy, s: update_crop_preview(video, ratio, cx, cy, s),
                inputs=[crop_video_display, aspect_ratio, center_x, center_y, scale],
                outputs=[crop_preview_image]
            )
            
            center_y.change(
                fn=lambda video, ratio, cx, cy, s: update_crop_preview(video, ratio, cx, cy, s),
                inputs=[crop_video_display, aspect_ratio, center_x, center_y, scale],
                outputs=[crop_preview_image]
            )
            
            scale.change(
                fn=lambda video, ratio, cx, cy, s: update_crop_preview(video, ratio, cx, cy, s),
                inputs=[crop_video_display, aspect_ratio, center_x, center_y, scale],
                outputs=[crop_preview_image]
            )
            
            # 更新预览按钮
            update_preview_btn.click(
                fn=lambda video, ratio, cx, cy, s: update_crop_preview(video, ratio, cx, cy, s),
                inputs=[crop_video_display, aspect_ratio, center_x, center_y, scale],
                outputs=[crop_preview_image]
            )
            
            # 手动裁切按钮
            manual_crop_btn.click(
                fn=lambda video, ratio, cx, cy, s: crop_video_with_tracking(
                    video, ratio, *get_crop_parameters(video, ratio, cx, cy, s)
                ),
                inputs=[crop_video_display, aspect_ratio, center_x, center_y, scale],
                outputs=[crop_preview, crop_error_msg]
            )
            
            # 人物跟踪裁切按钮
            auto_track_btn.click(
                fn=lambda video, ratio, cx, cy, s: crop_with_person_tracking(
                    video, ratio, *get_crop_parameters(video, ratio, cx, cy, s)
                ),
                inputs=[crop_video_display, aspect_ratio, center_x, center_y, scale],
                outputs=[crop_preview, crop_error_msg]
            )
        
        # 第三个标签页：字幕生成
        with gr.TabItem("📝 字幕生成"):
            with gr.Row():
                with gr.Column():
                    # 视频输入区域
                    with gr.Group():
                        gr.Markdown("### 📹 视频输入")
                        subtitle_video_input = gr.Video(label="上传视频文件", interactive=True)
                    
                    # 字幕设置
                    with gr.Group():
                        gr.Markdown("### ⚙️ 字幕设置")
                        model_size = gr.Radio(
                            choices=["tiny", "base", "small", "medium", "large"],
                            label="Whisper模型大小",
                            value="base",
                            info="模型越大，识别越准确，但处理时间越长"
                        )
                        
                        translate_subtitles = gr.Checkbox(
                            label="翻译为中文",
                            value=True,
                            info="自动将英文字幕翻译为中文"
                        )
                        
                        embed_subtitles = gr.Checkbox(
                            label="嵌入字幕到视频",
                            value=False,
                            info="将生成的字幕直接嵌入到视频中（推荐）"
                        )
                    
                    generate_subtitle_btn = gr.Button("🎯 生成字幕", variant="primary")
                
                with gr.Column():
                    # 字幕预览和下载
                    with gr.Group():
                        gr.Markdown("### 📄 字幕预览")
                        subtitle_preview = gr.Textbox(
                            label="字幕内容预览",
                            lines=15,
                            interactive=False,
                            placeholder="字幕生成后将在此显示..."
                        )
                        
                        download_subtitle_btn = gr.Button("⬇️ 下载字幕文件", variant="secondary", visible=False)
                    
                    subtitle_error_msg = gr.Textbox(label="处理状态", interactive=False, visible=True)
                    subtitle_info = gr.Markdown("""
                    **字幕生成功能说明：**
                    
                    **功能特点：**
                    - 🎤 **语音识别**：使用OpenAI Whisper进行高精度语音识别
                    - 🌍 **多语言支持**：支持英文等多种语言的语音识别
                    - 🔄 **自动翻译**：将英文字幕自动翻译为中文
                    - 📝 **SRT格式**：生成标准SRT字幕文件
                    
                    **使用步骤：**
                    1. 上传包含语音的视频文件
                    2. 选择Whisper模型大小（推荐base或small）
                    3. 选择是否需要中文翻译
                    4. 点击"生成字幕"
                    5. 等待处理完成
                    6. 下载字幕文件
                    
                    **模型大小说明：**
                    - **tiny**: 最快，适合测试
                    - **base**: 平衡速度和准确性（推荐）
                    - **small**: 更准确，处理时间较长
                    - **medium**: 高准确性，处理时间长
                    - **large**: 最高准确性，处理时间最长
                    
                    **💡 提示：** 首次使用需要下载Whisper模型，请耐心等待
                    """)
            
            # 字幕生成按钮事件
            generate_subtitle_btn.click(
                fn=lambda video, model, translate, embed: generate_subtitles(video, model, translate, embed),
                inputs=[subtitle_video_input, model_size, translate_subtitles, embed_subtitles],
                outputs=[subtitle_preview, subtitle_error_msg, subtitle_file_path]
            )
            
            # 当字幕生成成功时显示下载按钮
            generate_subtitle_btn.click(
                fn=lambda x: True if x else False,
                inputs=[subtitle_file_path],
                outputs=[download_subtitle_btn]
            )
            
            # 下载字幕按钮事件
            download_subtitle_btn.click(
                fn=download_subtitle_file,
                inputs=[subtitle_file_path],
                outputs=[download_subtitle_btn]
            )

if __name__ == "__main__":
    demo.launch(share=False) 