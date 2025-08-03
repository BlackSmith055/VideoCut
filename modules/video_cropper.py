import os
import tempfile
import cv2
import numpy as np
from utils.ffmpeg_utils import get_video_info, run_ffmpeg_command
from utils.person_tracker import PersonTracker

def calculate_crop_box(video_width: int, video_height: int, aspect_ratio: str, center_x: float = 0.5, center_y: float = 0.5, scale: float = 0.8) -> dict:
    """计算裁切框的参数"""
    if aspect_ratio == "3:4":
        # 3:4 比例，适合竖屏
        target_ratio = 3 / 4
    elif aspect_ratio == "1:1":
        # 1:1 比例，适合方形
        target_ratio = 1
    else:
        target_ratio = 3 / 4  # 默认使用 3:4
    
    # 计算裁切框的尺寸
    if video_width * target_ratio <= video_height:
        # 以宽度为基准
        crop_width = int(video_width * scale)
        crop_height = int(crop_width / target_ratio)
    else:
        # 以高度为基准
        crop_height = int(video_height * scale)
        crop_width = int(crop_height * target_ratio)
    
    # 计算裁切框的位置
    crop_x = int((video_width - crop_width) * center_x)
    crop_y = int((video_height - crop_height) * center_y)
    
    # 确保裁切框不超出视频边界
    crop_x = max(0, min(crop_x, video_width - crop_width))
    crop_y = max(0, min(crop_y, video_height - crop_height))
    
    return {
        'x': crop_x,
        'y': crop_y,
        'width': crop_width,
        'height': crop_height
    }

def crop_video_with_tracking(input_path: str, aspect_ratio: str, crop_x: float, crop_y: float, crop_width: float, crop_height: float):
    """智能裁切视频，支持人物跟踪和动态调整"""
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
        
        # 执行裁切
        success = run_ffmpeg_command(cmd, "裁切命令")
        if not success:
            raise ValueError("视频裁切失败")
        
        print(f"视频裁切成功: {output_path}")
        return output_path, ""
        
    except Exception as e:
        error_msg = f"视频裁切时出错: {str(e)}"
        print(error_msg)
        return None, error_msg

def crop_with_person_tracking(input_path: str, aspect_ratio: str, crop_x: float, crop_y: float, crop_width: float, crop_height: float):
    """使用人物跟踪进行智能裁切"""
    try:
        if not input_path or not os.path.exists(input_path):
            raise ValueError("请先选择视频文件")
        
        # 获取视频信息
        video_info = get_video_info(input_path)
        original_width = video_info['width']
        original_height = video_info['height']
        fps = video_info['fps']
        
        # 打开视频
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise ValueError("无法打开视频文件")
        
        # 获取总帧数
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f"开始人物跟踪裁切，总帧数: {total_frames}")
        
        # 初始化人物跟踪器
        tracker = PersonTracker()
        
        # 创建临时输出文件
        tmp_dir = tempfile.gettempdir()
        output_path = os.path.join(tmp_dir, f"tracked_{aspect_ratio}.mp4")
        final_output = os.path.join(tmp_dir, f"final_tracked_{aspect_ratio}.mp4")
        
        # 准备视频写入器
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (int(crop_width * original_width), int(crop_height * original_height)))
        
        frame_count = 0
        initialized = False
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            
            # 显示进度
            if frame_count % 30 == 0:
                progress = frame_count / total_frames * 100
                print(f"处理进度: {frame_count}/{total_frames} ({progress:.1f}%)")
            
            # 第一帧初始化跟踪器
            if not initialized:
                # 计算初始裁切区域
                crop_box = calculate_crop_box(original_width, original_height, aspect_ratio, crop_x, crop_y, crop_width, crop_height)
                
                # 在初始区域内检测人物
                x, y, w, h = crop_box['x'], crop_box['y'], crop_box['width'], crop_box['height']
                roi = frame[y:y+h, x:x+w]
                person_bbox = tracker.detect_person(roi)
                
                if person_bbox:
                    # 调整检测框到全局坐标
                    px, py, pw, ph = person_bbox
                    global_bbox = (x + px, y + py, pw, ph)
                    tracker.initialize_tracker(frame, global_bbox)
                    print(f"人物跟踪器初始化成功，帧 {frame_count}")
                else:
                    # 如果没有检测到人物，使用初始裁切区域
                    tracker.last_bbox = (x, y, w, h)
                
                initialized = True
            
            # 跟踪人物位置
            bbox = tracker.track_person(frame)
            if bbox:
                x, y, w, h = bbox
                
                # 确保裁切区域不超出视频边界
                x = max(0, min(x, original_width - w))
                y = max(0, min(y, original_height - h))
                w = min(w, original_width - x)
                h = min(h, original_height - y)
                
                # 裁切当前帧
                cropped_frame = frame[y:y+h, x:x+w]
                
                # 调整到目标尺寸
                target_width = int(crop_width * original_width)
                target_height = int(crop_height * original_height)
                resized_frame = cv2.resize(cropped_frame, (target_width, target_height))
                
                out.write(resized_frame)
            else:
                # 如果跟踪失败，使用上一帧的裁切区域
                if tracker.last_bbox:
                    x, y, w, h = tracker.last_bbox
                    cropped_frame = frame[y:y+h, x:x+w]
                    target_width = int(crop_width * original_width)
                    target_height = int(crop_height * original_height)
                    resized_frame = cv2.resize(cropped_frame, (target_width, target_height))
                    out.write(resized_frame)
        
        # 释放资源
        cap.release()
        out.release()
        
        # 使用FFmpeg重新编码以确保兼容性
        cmd = [
            'ffmpeg', '-i', output_path,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'ultrafast',
            '-crf', '23',
            '-y', final_output
        ]
        
        success = run_ffmpeg_command(cmd, "人物跟踪裁切命令")
        if success:
            # 删除临时文件
            if os.path.exists(output_path):
                os.remove(output_path)
            print(f"人物跟踪裁切成功: {final_output}")
            return final_output, ""
        else:
            print(f"人物跟踪裁切成功: {output_path}")
            return output_path, ""
        
    except Exception as e:
        error_msg = f"人物跟踪裁切时出错: {str(e)}"
        print(error_msg)
        return None, error_msg

def create_crop_preview_image(video_path: str, aspect_ratio: str, crop_x: float, crop_y: float, crop_width: float, crop_height: float) -> str:
    """创建裁切预览图像"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # 获取视频信息
        video_info = get_video_info(video_path)
        original_width = video_info['width']
        original_height = video_info['height']
        
        # 计算裁切区域
        crop_box = calculate_crop_box(original_width, original_height, aspect_ratio, crop_x, crop_y, crop_width, crop_height)
        
        # 提取视频帧作为背景
        from utils.ffmpeg_utils import extract_video_frame
        frame_path = extract_video_frame(video_path, 1.0)  # 提取1秒处的帧
        
        if frame_path and os.path.exists(frame_path):
            # 打开背景图像
            background = Image.open(frame_path)
            
            # 创建绘图对象
            draw = ImageDraw.Draw(background)
            
            # 绘制裁切框
            x, y, w, h = crop_box['x'], crop_box['y'], crop_box['width'], crop_box['height']
            draw.rectangle([x, y, x + w, y + h], outline='red', width=3)
            
            # 添加文字说明
            try:
                font = ImageFont.truetype("Arial", 24)
            except:
                font = ImageFont.load_default()
            
            text = f"裁切区域: {aspect_ratio}"
            draw.text((10, 10), text, fill='red', font=font)
            
            # 保存预览图像
            import tempfile
            tmp_dir = tempfile.gettempdir()
            preview_path = os.path.join(tmp_dir, f"crop_preview_{aspect_ratio}.jpg")
            background.save(preview_path)
            
            return preview_path
        else:
            # 如果无法提取帧，创建空白预览
            import tempfile
            tmp_dir = tempfile.gettempdir()
            preview_path = os.path.join(tmp_dir, f"crop_preview_{aspect_ratio}.jpg")
            
            # 创建空白图像
            img = Image.new('RGB', (original_width, original_height), color='black')
            draw = ImageDraw.Draw(img)
            
            # 绘制裁切框
            x, y, w, h = crop_box['x'], crop_box['y'], crop_box['width'], crop_box['height']
            draw.rectangle([x, y, x + w, y + h], outline='red', width=3)
            
            img.save(preview_path)
            return preview_path
            
    except Exception as e:
        print(f"创建裁切预览失败: {e}")
        return None 