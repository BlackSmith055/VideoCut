import subprocess
import json
import os
from .time_utils import seconds_to_ffmpeg_time

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
        import tempfile
        tmp_dir = tempfile.gettempdir()
        frame_path = os.path.join(tmp_dir, f"preview_frame_{int(time_seconds*100)}.jpg")
        
        cmd = [
            'ffmpeg', '-i', video_path,
            '-ss', seconds_to_ffmpeg_time(time_seconds),
            '-vframes', '1',
            '-q:v', '2',
            '-y', frame_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and os.path.exists(frame_path):
            return frame_path
        else:
            return None
    except Exception as e:
        print(f"提取视频帧失败: {e}")
        return None

def run_ffmpeg_command(cmd: list, description: str = "FFmpeg命令") -> bool:
    """执行FFmpeg命令的通用函数"""
    try:
        print(f"执行{description}: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"{description}成功！")
            return True
        else:
            print(f"{description}失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"{description}执行错误: {e}")
        return False 