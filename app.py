import gradio as gr
import re
import tempfile
import os
import subprocess
import json
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import base64
import io
import whisper
import torch
# from googletrans import Translator
import json

# --- Utility: 时间格式解析 ---
def time_to_seconds(time_str: str) -> float:
    """
    将多种时间格式转换为秒（浮点数）。
    支持格式：
    - MM:SS (分钟:秒)
    - HH:MM:SS (小时:分钟:秒)
    - HH:MM:SS.ss (小时:分钟:秒.毫秒)
    """
    # 去除空白字符
    time_str = time_str.strip()
    
    # 尝试 MM:SS 格式
    pattern1 = r"^(?P<m>\d+):(?P<s>\d+(?:\.\d{1,2})?)$"
    m = re.match(pattern1, time_str)
    if m:
        minutes = int(m.group('m'))
        seconds = float(m.group('s'))
        return minutes * 60 + seconds
    
    # 尝试 HH:MM:SS 格式
    pattern2 = r"^(?P<h>\d+):(?P<m>[0-5]\d):(?P<s>\d+(?:\.\d{1,2})?)$"
    m = re.match(pattern2, time_str)
    if m:
        hours = int(m.group('h'))
        minutes = int(m.group('m'))
        seconds = float(m.group('s'))
        return hours * 3600 + minutes * 60 + seconds
    
    raise ValueError(f"时间格式无效: {time_str}. 请使用 MM:SS 或 HH:MM:SS 格式。")

def seconds_to_ffmpeg_time(seconds: float) -> str:
    """将秒数转换为 FFmpeg 时间格式 (HH:MM:SS.ss)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

def get_video_duration(input_path: str) -> float:
    """使用 FFmpeg 获取视频时长"""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
            '-of', 'json', input_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return float(data['format']['duration'])
    except Exception as e:
        print(f"获取视频时长失败: {e}")
        return 0

def get_video_info(input_path: str) -> dict:
    """获取视频信息（分辨率、帧率等）"""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,r_frame_rate',
            '-of', 'json', input_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        stream = data['streams'][0]
        
        # 解析帧率
        fps_parts = stream['r_frame_rate'].split('/')
        fps = float(fps_parts[0]) / float(fps_parts[1])
        
        return {
            'width': int(stream['width']),
            'height': int(stream['height']),
            'fps': fps
        }
    except Exception as e:
        print(f"获取视频信息失败: {e}")
        return {'width': 1920, 'height': 1080, 'fps': 30}



def extract_video_frame(video_path: str, time_seconds: float = 0) -> str:
    """从视频中提取指定时间的帧作为预览图"""
    try:
        tmp_dir = tempfile.gettempdir()
        frame_path = os.path.join(tmp_dir, f"preview_frame_{int(time_seconds*100)}.jpg")
        
        cmd = [
            'ffmpeg', '-i', video_path,
            '-ss', str(time_seconds),
            '-vframes', '1',
            '-q:v', '2',
            '-y', frame_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and os.path.exists(frame_path):
            return frame_path
        return None
    except Exception as e:
        print(f"提取预览帧失败: {e}")
        return None

def create_crop_preview_image(video_path: str, aspect_ratio: str, crop_x: float, crop_y: float, crop_width: float, crop_height: float) -> str:
    """创建带有裁切框的预览图像"""
    try:
        # 提取视频帧
        frame_path = extract_video_frame(video_path, 0)
        if not frame_path:
            return None
        
        # 读取图像
        img = cv2.imread(frame_path)
        if img is None:
            return None
        
        height, width = img.shape[:2]
        
        # 计算裁切框的实际像素位置
        crop_x_pixels = int(crop_x * width)
        crop_y_pixels = int(crop_y * height)
        crop_w_pixels = int(crop_width * width)
        crop_h_pixels = int(crop_height * height)
        
        # 确保裁切框在图像范围内
        crop_x_pixels = max(0, min(crop_x_pixels, width - crop_w_pixels))
        crop_y_pixels = max(0, min(crop_y_pixels, height - crop_h_pixels))
        crop_w_pixels = min(crop_w_pixels, width - crop_x_pixels)
        crop_h_pixels = min(crop_h_pixels, height - crop_y_pixels)
        
        # 绘制裁切框
        cv2.rectangle(img, 
                     (crop_x_pixels, crop_y_pixels), 
                     (crop_x_pixels + crop_w_pixels, crop_y_pixels + crop_h_pixels), 
                     (0, 255, 0), 3)
        
        # 添加比例标签
        label = f"{aspect_ratio} 裁切框"
        cv2.putText(img, label, (crop_x_pixels, crop_y_pixels - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # 保存预览图像
        preview_path = os.path.join(tempfile.gettempdir(), f"crop_preview_{aspect_ratio}.jpg")
        cv2.imwrite(preview_path, img)
        
        return preview_path
        
    except Exception as e:
        print(f"创建裁切预览失败: {e}")
        return None

def calculate_crop_box(video_width: int, video_height: int, aspect_ratio: str, center_x: float = 0.5, center_y: float = 0.5, scale: float = 0.8) -> dict:
    """根据比例和缩放计算裁切框"""
    if aspect_ratio == "3:4":
        target_ratio = 3/4
    elif aspect_ratio == "1:1":
        target_ratio = 1
    else:  # 9:16
        target_ratio = 9/16
    
    # 计算最大可能的裁切框尺寸
    if target_ratio > video_width / video_height:
        # 以宽度为基准
        max_crop_width = video_width * scale
        max_crop_height = max_crop_width / target_ratio
    else:
        # 以高度为基准
        max_crop_height = video_height * scale
        max_crop_width = max_crop_height * target_ratio
    
    # 计算中心位置
    center_x_pixels = int(center_x * video_width)
    center_y_pixels = int(center_y * video_height)
    
    # 计算裁切框位置
    crop_x = (center_x_pixels - max_crop_width / 2) / video_width
    crop_y = (center_y_pixels - max_crop_height / 2) / video_height
    crop_width = max_crop_width / video_width
    crop_height = max_crop_height / video_height
    
    # 确保裁切框在视频范围内
    crop_x = max(0, min(crop_x, 1 - crop_width))
    crop_y = max(0, min(crop_y, 1 - crop_height))
    
    return {
        'x': crop_x,
        'y': crop_y,
        'width': crop_width,
        'height': crop_height
    }

# --- 人物检测和跟踪 ---
class PersonTracker:
    def __init__(self):
        # 使用 OpenCV 的 HOG 人物检测器
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        self.tracked_positions = []
        self.tracker = None
        self.initial_bbox = None
    
    def detect_person(self, frame):
        """检测画面中的人物位置"""
        # 转换为灰度图
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 检测人物
        boxes, weights = self.hog.detectMultiScale(
            gray, 
            winStride=(8, 8),
            padding=(4, 4),
            scale=1.05
        )
        
        if len(boxes) > 0:
            # 选择最大的人物框（通常是最主要的人物）
            largest_box = max(boxes, key=lambda x: x[2] * x[3])
            x, y, w, h = largest_box
            
            bbox = {
                'x': x,
                'y': y,
                'width': w,
                'height': h,
                'center_x': x + w // 2,
                'center_y': y + h // 2
            }
            
            self.tracked_positions.append(bbox)
            return bbox
        
        return None
    
    def initialize_tracker(self, frame, bbox):
        """初始化跟踪器 - 使用基于检测的跟踪方法"""
        self.initial_bbox = bbox
        self.last_bbox = bbox
        self.tracked_positions = [bbox]
        return True
    
    def track_person(self, frame):
        """跟踪人物位置 - 使用基于检测的跟踪方法"""
        if self.initial_bbox is None:
            return None
        
        # 在上一帧位置附近检测人物
        last_x, last_y, last_w, last_h = (
            self.last_bbox['x'], self.last_bbox['y'], 
            self.last_bbox['width'], self.last_bbox['height']
        )
        
        # 扩大搜索区域
        search_margin = 50
        search_x = max(0, last_x - search_margin)
        search_y = max(0, last_y - search_margin)
        search_w = min(frame.shape[1] - search_x, last_w + 2 * search_margin)
        search_h = min(frame.shape[0] - search_y, last_h + 2 * search_margin)
        
        # 在搜索区域内检测人物
        search_roi = frame[search_y:search_y+search_h, search_x:search_x+search_w]
        if search_roi.size > 0:
            person_bbox = self.detect_person(search_roi)
            if person_bbox:
                # 调整坐标到原图坐标系
                person_bbox['x'] += search_x
                person_bbox['y'] += search_y
                self.last_bbox = person_bbox
                self.tracked_positions.append(person_bbox)
                return person_bbox
        
        # 如果检测失败，使用上一帧的位置
        return self.last_bbox

# --- Feature 1: 使用 FFmpeg 的高效片段提取 ---
def extract_segment(input_path: str, start_str: str, end_str: str):
    """
    使用 FFmpeg 从 input_path 中根据 start_str 和 end_str 提取视频片段。
    这种方法比 MoviePy 快很多，CPU 使用率也低很多。
    """
    try:
        # 检查输入文件是否存在
        if not input_path or not os.path.exists(input_path):
            raise ValueError("请先上传视频文件")
        
        # 解析时间
        start = time_to_seconds(start_str)
        end = time_to_seconds(end_str)
        
        if end <= start:
            raise ValueError("结束时间必须大于开始时间")
        
        # 检查视频时长
        video_duration = get_video_duration(input_path)
        if video_duration > 0 and end > video_duration:
            raise ValueError(f"结束时间 ({end_str}) 超过了视频总时长 ({video_duration:.1f} 秒)")
        
        # 创建临时输出文件
        tmp_dir = tempfile.gettempdir()
        out_path = os.path.join(tmp_dir, f"segment_ffmpeg_{int(start*100)}_{int(end*100)}.mp4")
        
        # 转换为 FFmpeg 时间格式
        start_time = seconds_to_ffmpeg_time(start)
        duration = end - start
        
        # 使用 FFmpeg 提取片段 - 使用精确切割模式
        cmd_precise = [
            'ffmpeg', '-i', input_path,
            '-ss', start_time,
            '-t', str(duration),
            '-c:v', 'libx264',  # 重新编码视频以确保精确切割
            '-c:a', 'aac',      # 重新编码音频
            '-preset', 'ultrafast',  # 最快编码预设
            '-crf', '23',       # 保持良好质量
            '-avoid_negative_ts', 'make_zero',
            '-fflags', '+genpts',  # 生成新的时间戳
            '-y',  # 覆盖输出文件
            out_path
        ]
        
        print(f"执行精确切割 FFmpeg 命令: {' '.join(cmd_precise)}")
        
        # 执行 FFmpeg 命令
        result = subprocess.run(cmd_precise, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"FFmpeg 错误输出: {result.stderr}")
            raise ValueError(f"FFmpeg 处理失败: {result.stderr}")
        else:
            print("精确切割成功！")
        
        # 检查输出文件是否存在
        if not os.path.exists(out_path):
            raise ValueError("输出文件未生成")
        
        print(f"视频片段提取成功: {out_path}")
        return out_path, "", out_path  # 返回视频路径、空错误消息和状态
        
    except Exception as e:
        error_msg = f"提取视频片段时出错: {str(e)}"
        print(error_msg)
        return None, error_msg, None  # 返回 None、错误消息和状态

# --- Feature 2: 智能视频裁切和人物跟踪 ---
def crop_video_with_tracking(input_path: str, aspect_ratio: str, crop_x: float, crop_y: float, crop_width: float, crop_height: float):
    """
    智能裁切视频，支持人物跟踪和动态调整
    """
    try:
        if not input_path or not os.path.exists(input_path):
            raise ValueError("请先选择视频文件")
        
        # 获取视频信息
        video_info = get_video_info(input_path)
        original_width = video_info['width']
        original_height = video_info['height']
        
        # 计算裁切区域
        crop_x_pixels = int(crop_x * original_width)
        crop_y_pixels = int(crop_y * original_height)
        crop_w_pixels = int(crop_width * original_width)
        crop_h_pixels = int(crop_height * original_height)
        
        # 确保裁切区域不超出视频边界
        crop_x_pixels = max(0, min(crop_x_pixels, original_width - crop_w_pixels))
        crop_y_pixels = max(0, min(crop_y_pixels, original_height - crop_h_pixels))
        crop_w_pixels = min(crop_w_pixels, original_width - crop_x_pixels)
        crop_h_pixels = min(crop_h_pixels, original_height - crop_y_pixels)
        
        # 创建临时输出文件
        tmp_dir = tempfile.gettempdir()
        output_path = os.path.join(tmp_dir, f"cropped_{aspect_ratio}_{int(crop_x*100)}_{int(crop_y*100)}.mp4")
        
        # 构建 FFmpeg 命令
        cmd = [
            'ffmpeg', '-i', input_path,
            '-vf', f'crop={crop_w_pixels}:{crop_h_pixels}:{crop_x_pixels}:{crop_y_pixels}',
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'ultrafast',
            '-crf', '23',
            '-y', output_path
        ]
        
        print(f"执行裁切命令: {' '.join(cmd)}")
        
        # 执行裁切
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"裁切失败: {result.stderr}")
            raise ValueError(f"视频裁切失败: {result.stderr}")
        
        # 如果需要添加黑边实现9:16格式
        if aspect_ratio == "9:16":
            final_output = os.path.join(tmp_dir, f"final_9x16_{int(crop_x*100)}_{int(crop_y*100)}.mp4")
            
            # 获取裁切后视频的尺寸
            crop_info = get_video_info(output_path)
            crop_width = crop_info['width']
            crop_height = crop_info['height']
            
            # 计算9:16的目标高度
            target_height = int(crop_width * 16 / 9)
            padding = (target_height - crop_height) // 2
            
            # 添加黑边
            pad_cmd = [
                'ffmpeg', '-i', output_path,
                '-vf', f'pad={crop_width}:{target_height}:0:{padding}:black',
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-preset', 'ultrafast',
                '-crf', '23',
                '-y', final_output
            ]
            
            print(f"添加黑边命令: {' '.join(pad_cmd)}")
            pad_result = subprocess.run(pad_cmd, capture_output=True, text=True)
            
            if pad_result.returncode == 0:
                os.remove(output_path)  # 删除中间文件
                output_path = final_output
            else:
                print(f"添加黑边失败: {pad_result.stderr}")
        
        print(f"视频裁切成功: {output_path}")
        return output_path, ""
        
    except Exception as e:
        error_msg = f"视频裁切时出错: {str(e)}"
        print(error_msg)
        return None, error_msg

# --- Feature 3: 人物跟踪裁切 ---
def crop_with_person_tracking(input_path: str, aspect_ratio: str, crop_x: float, crop_y: float, crop_width: float, crop_height: float):
    """
    使用人物跟踪进行智能裁切 - 真正跟踪人物移动
    """
    try:
        if not input_path or not os.path.exists(input_path):
            raise ValueError("请先选择视频文件")
        
        # 获取视频信息
        video_info = get_video_info(input_path)
        original_width = video_info['width']
        original_height = video_info['height']
        
        # 计算初始裁切框尺寸
        crop_w_pixels = int(crop_width * original_width)
        crop_h_pixels = int(crop_height * original_height)
        
        # 创建临时输出文件
        tmp_dir = tempfile.gettempdir()
        output_path = os.path.join(tmp_dir, f"tracked_{aspect_ratio}.mp4")
        
        # 打开视频
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise ValueError("无法打开视频文件")
        
        # 获取视频属性
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # 创建视频写入器
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (crop_w_pixels, crop_h_pixels))
        
        # 初始化人物跟踪器
        tracker = PersonTracker()
        initialized = False
        
        print(f"开始人物跟踪裁切，总帧数: {total_frames}")
        
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            if frame_count % 30 == 0:  # 每30帧打印一次进度
                print(f"处理进度: {frame_count}/{total_frames} ({frame_count/total_frames*100:.1f}%)")
            
            # 初始化跟踪器（在第一帧或检测到人物时）
            if not initialized:
                # 使用用户选择的区域作为初始检测区域
                initial_x = int(crop_x * original_width)
                initial_y = int(crop_y * original_height)
                
                # 在初始区域附近检测人物
                roi = frame[initial_y:initial_y+crop_h_pixels, initial_x:initial_x+crop_w_pixels]
                if roi.size > 0:
                    person_bbox = tracker.detect_person(roi)
                    if person_bbox:
                        # 调整坐标到原图坐标系
                        person_bbox['x'] += initial_x
                        person_bbox['y'] += initial_y
                        if tracker.initialize_tracker(frame, person_bbox):
                            initialized = True
                            print(f"人物跟踪器初始化成功，帧 {frame_count}")
            
            # 跟踪人物
            if initialized:
                tracked_bbox = tracker.track_person(frame)
                if tracked_bbox:
                    # 计算裁切区域，以人物为中心
                    person_center_x = tracked_bbox['center_x']
                    person_center_y = tracked_bbox['center_y']
                    
                    # 计算裁切框位置，确保人物在中心
                    crop_x_pixels = max(0, min(person_center_x - crop_w_pixels // 2, original_width - crop_w_pixels))
                    crop_y_pixels = max(0, min(person_center_y - crop_h_pixels // 2, original_height - crop_h_pixels))
                else:
                    # 跟踪失败，使用上一帧的位置或默认位置
                    crop_x_pixels = int(crop_x * original_width)
                    crop_y_pixels = int(crop_y * original_height)
            else:
                # 未初始化，使用用户选择的位置
                crop_x_pixels = int(crop_x * original_width)
                crop_y_pixels = int(crop_y * original_height)
            
            # 确保裁切区域在视频范围内
            crop_x_pixels = max(0, min(crop_x_pixels, original_width - crop_w_pixels))
            crop_y_pixels = max(0, min(crop_y_pixels, original_height - crop_h_pixels))
            
            # 裁切帧
            cropped_frame = frame[crop_y_pixels:crop_y_pixels+crop_h_pixels, 
                                crop_x_pixels:crop_x_pixels+crop_w_pixels]
            
            # 写入输出视频
            out.write(cropped_frame)
        
        # 释放资源
        cap.release()
        out.release()
        
        # 使用 FFmpeg 重新编码以确保兼容性
        final_output = os.path.join(tmp_dir, f"final_tracked_{aspect_ratio}.mp4")
        cmd = [
            'ffmpeg', '-i', output_path,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'ultrafast',
            '-crf', '23',
            '-y', final_output
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            os.remove(output_path)  # 删除中间文件
            output_path = final_output
        
        print(f"人物跟踪裁切成功: {output_path}")
        return output_path, ""
        
    except Exception as e:
        error_msg = f"人物跟踪裁切时出错: {str(e)}"
        print(error_msg)
        return None, error_msg

# --- 辅助函数 ---
def update_crop_preview(video_path, aspect_ratio, center_x, center_y, scale):
    """更新裁切预览图像"""
    if not video_path or not os.path.exists(video_path):
        return None
    
    try:
        # 获取视频信息
        video_info = get_video_info(video_path)
        crop_box = calculate_crop_box(video_info['width'], video_info['height'], aspect_ratio, center_x, center_y, scale)
        
        # 创建预览图像
        preview_path = create_crop_preview_image(video_path, aspect_ratio, 
                                               crop_box['x'], crop_box['y'], 
                                               crop_box['width'], crop_box['height'])
        return preview_path
    except Exception as e:
        print(f"更新预览失败: {e}")
        return None

def get_crop_parameters(video_path, aspect_ratio, center_x, center_y, scale):
    """获取裁切参数"""
    if not video_path or not os.path.exists(video_path):
        return 0.1, 0.1, 0.8, 0.8
    
    try:
        video_info = get_video_info(video_path)
        crop_box = calculate_crop_box(video_info['width'], video_info['height'], aspect_ratio, center_x, center_y, scale)
        return crop_box['x'], crop_box['y'], crop_box['width'], crop_box['height']
    except Exception as e:
        print(f"获取裁切参数失败: {e}")
        return 0.1, 0.1, 0.8, 0.8

def select_video_source(extracted_video, direct_video):
    """选择视频源：优先使用直接上传的视频，其次使用提取的视频"""
    if direct_video and os.path.exists(direct_video):
        return direct_video
    elif extracted_video and os.path.exists(extracted_video):
        return extracted_video
    else:
        return None

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
    """更新视频显示：如果有提取的视频则显示，否则显示上传按钮"""
    if extracted_video and os.path.exists(extracted_video):
        return extracted_video, False  # 显示视频，隐藏上传按钮
    else:
        return None, True  # 不显示视频，显示上传按钮

# --- 字幕生成功能 ---
class SubtitleGenerator:
    def __init__(self):
        self.model = None
        # self.translator = Translator()
    
    def load_model(self, model_size="base"):
        """加载Whisper模型"""
        try:
            if self.model is None:
                print(f"正在加载Whisper模型: {model_size}")
                # 设置SSL验证为False来解决证书问题
                import ssl
                ssl._create_default_https_context = ssl._create_unverified_context
                self.model = whisper.load_model(model_size)
                print("Whisper模型加载完成")
            return True
        except Exception as e:
            print(f"加载Whisper模型失败: {e}")
            return False
    
    def extract_audio(self, video_path):
        """从视频中提取音频"""
        try:
            audio_path = video_path.replace('.mp4', '_audio.wav')
            cmd = [
                'ffmpeg', '-i', video_path,
                '-vn',  # 不包含视频
                '-acodec', 'pcm_s16le',  # 音频编码
                '-ar', '16000',  # 采样率
                '-ac', '1',  # 单声道
                '-y', audio_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return audio_path
            else:
                raise Exception(f"音频提取失败: {result.stderr}")
        except Exception as e:
            print(f"音频提取错误: {e}")
            return None
    
    def transcribe_audio(self, audio_path):
        """使用Whisper进行语音识别"""
        try:
            if not self.load_model():
                return None
            
            print("开始语音识别...")
            result = self.model.transcribe(audio_path)
            print("语音识别完成")
            return result
        except Exception as e:
            print(f"语音识别错误: {e}")
            return None
    
    def translate_text(self, text, target_lang='zh'):
        """翻译文本"""
        try:
            if not text or text.strip() == "":
                return ""
            
            # 暂时返回原文，后续可以集成其他翻译服务
            # translation = self.translator.translate(text, dest=target_lang)
            # return translation.text
            return f"[中文翻译] {text}"  # 临时占位符
        except Exception as e:
            print(f"翻译错误: {e}")
            return text  # 翻译失败时返回原文
    
    def format_subtitles(self, segments, translate=True):
        """格式化字幕"""
        subtitles = []
        for segment in segments:
            start_time = segment['start']
            end_time = segment['end']
            text = segment['text'].strip()
            
            # 格式化时间
            start_str = f"{int(start_time//60):02d}:{start_time%60:05.2f}"
            end_str = f"{int(end_time//60):02d}:{end_time%60:05.2f}"
            
            subtitle_entry = {
                'start': start_time,
                'end': end_time,
                'start_str': start_str,
                'end_str': end_str,
                'en': text
            }
            
            if translate:
                subtitle_entry['zh'] = self.translate_text(text)
            
            subtitles.append(subtitle_entry)
        
        return subtitles
    
    def generate_srt(self, subtitles):
        """生成SRT格式字幕"""
        srt_content = ""
        for i, subtitle in enumerate(subtitles, 1):
            srt_content += f"{i}\n"
            srt_content += f"{subtitle['start_str']} --> {subtitle['end_str']}\n"
            srt_content += f"{subtitle['en']}\n"
            if 'zh' in subtitle:
                srt_content += f"{subtitle['zh']}\n"
            srt_content += "\n"
        
        return srt_content
    
    def generate_ass_subtitles(self, subtitles):
        """生成ASS格式字幕文件，支持样式设置"""
        ass_content = """[Script Info]
Title: Generated Subtitles
ScriptType: v4.00+
WrapStyle: 1
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,24,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        for subtitle in subtitles:
            start_time = self.seconds_to_ass_time(subtitle['start'])
            end_time = self.seconds_to_ass_time(subtitle['end'])
            
            # 英文字幕
            en_text = subtitle['en'].replace('\n', '\\N')
            ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{en_text}\n"
            
            # 中文字幕
            if 'zh' in subtitle:
                zh_text = subtitle['zh'].replace('\n', '\\N')
                ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{zh_text}\n"
        
        return ass_content
    
    def seconds_to_ass_time(self, seconds):
        """将秒数转换为ASS时间格式 (H:MM:SS.cc)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        centiseconds = int((secs % 1) * 100)
        secs = int(secs)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"
    
    def embed_subtitles_to_video(self, video_path, subtitles, output_path=None):
        """将字幕嵌入到视频中"""
        try:
            if output_path is None:
                output_path = video_path.replace('.mp4', '_with_subtitles.mp4')
            
            # 生成ASS字幕文件
            ass_content = self.generate_ass_subtitles(subtitles)
            ass_path = video_path.replace('.mp4', '_subtitles.ass')
            
            with open(ass_path, 'w', encoding='utf-8') as f:
                f.write(ass_content)
            
            # 使用FFmpeg将字幕嵌入视频
            cmd = [
                'ffmpeg', '-i', video_path,
                '-vf', f'ass={ass_path}',
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-preset', 'ultrafast',
                '-crf', '23',
                '-y', output_path
            ]
            
            print(f"执行字幕嵌入命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # 清理临时ASS文件
            if os.path.exists(ass_path):
                os.remove(ass_path)
            
            if result.returncode == 0:
                print(f"字幕嵌入成功: {output_path}")
                return output_path
            else:
                print(f"字幕嵌入失败: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"字幕嵌入错误: {e}")
            return None

def generate_subtitles(video_path, model_size="base", translate=True, embed_subtitles=False):
    """生成视频字幕的主函数"""
    try:
        if not video_path or not os.path.exists(video_path):
            return None, "视频文件不存在"
        
        print(f"开始为视频生成字幕: {video_path}")
        
        # 初始化字幕生成器
        generator = SubtitleGenerator()
        
        # 提取音频
        print("正在提取音频...")
        audio_path = generator.extract_audio(video_path)
        if not audio_path:
            return None, "音频提取失败"
        
        # 语音识别
        result = generator.transcribe_audio(audio_path)
        if not result:
            return None, "语音识别失败"
        
        # 格式化字幕
        print("正在格式化字幕...")
        subtitles = generator.format_subtitles(result['segments'], translate)
        
        # 生成SRT文件
        srt_content = generator.generate_srt(subtitles)
        
        # 保存SRT文件
        srt_path = video_path.replace('.mp4', '_subtitles.srt')
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        
        # 如果需要嵌入字幕到视频中
        if embed_subtitles:
            print("正在将字幕嵌入到视频中...")
            output_video_path = generator.embed_subtitles_to_video(video_path, subtitles)
            if output_video_path:
                # 清理临时音频文件
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                
                print(f"字幕嵌入完成: {output_video_path}")
                return output_video_path, f"字幕生成并嵌入成功！共生成 {len(subtitles)} 条字幕"
            else:
                # 清理临时音频文件
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                return srt_path, f"字幕生成成功，但嵌入失败！共生成 {len(subtitles)} 条字幕"
        
        # 清理临时音频文件
        if os.path.exists(audio_path):
            os.remove(audio_path)
        
        print(f"字幕生成完成: {srt_path}")
        return srt_path, f"字幕生成成功！共生成 {len(subtitles)} 条字幕"
        
    except Exception as e:
        error_msg = f"字幕生成失败: {str(e)}"
        print(error_msg)
        return None, error_msg

def generate_subtitles_for_ui(video_path, model_size="base", translate=True, embed_subtitles=False):
    """为UI界面生成字幕的函数，返回字幕内容、状态信息和文件路径"""
    try:
        if not video_path or not os.path.exists(video_path):
            return "", "视频文件不存在", None
        
        print(f"开始为视频生成字幕: {video_path}")
        
        # 初始化字幕生成器
        generator = SubtitleGenerator()
        
        # 提取音频
        print("正在提取音频...")
        audio_path = generator.extract_audio(video_path)
        if not audio_path:
            return "", "音频提取失败", None
        
        # 语音识别
        result = generator.transcribe_audio(audio_path)
        if not result:
            return "", "语音识别失败", None
        
        # 格式化字幕
        print("正在格式化字幕...")
        subtitles = generator.format_subtitles(result['segments'], translate)
        
        # 生成SRT内容用于显示
        srt_content = generator.generate_srt(subtitles)
        
        # 如果需要嵌入字幕到视频中
        if embed_subtitles:
            print("正在将字幕嵌入到视频中...")
            output_video_path = generator.embed_subtitles_to_video(video_path, subtitles)
            if output_video_path:
                # 清理临时音频文件
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                
                print(f"字幕嵌入完成: {output_video_path}")
                return srt_content, f"字幕生成并嵌入成功！共生成 {len(subtitles)} 条字幕。输出视频：{os.path.basename(output_video_path)}", output_video_path
            else:
                # 清理临时音频文件
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                return srt_content, f"字幕生成成功，但嵌入失败！共生成 {len(subtitles)} 条字幕", None
        
        # 保存SRT文件
        srt_path = video_path.replace('.mp4', '_subtitles.srt')
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        
        # 清理临时音频文件
        if os.path.exists(audio_path):
            os.remove(audio_path)
        
        print(f"字幕生成完成: {srt_path}")
        return srt_content, f"字幕生成成功！共生成 {len(subtitles)} 条字幕。文件：{os.path.basename(srt_path)}", srt_path
        
    except Exception as e:
        error_msg = f"字幕生成失败: {str(e)}"
        print(error_msg)
        return "", error_msg, None

# --- Gradio 界面 & 绑定 ---
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
                fn=lambda video, model, translate, embed: generate_subtitles_for_ui(video, model, translate, embed),
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
