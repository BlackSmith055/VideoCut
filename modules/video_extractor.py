import os
import tempfile
import subprocess
from utils.time_utils import time_to_seconds, seconds_to_ffmpeg_time
from utils.ffmpeg_utils import get_video_duration, run_ffmpeg_command

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
        
        # 执行 FFmpeg 命令
        success = run_ffmpeg_command(cmd_precise, "精确切割 FFmpeg 命令")
        if not success:
            raise ValueError("FFmpeg 处理失败")
        
        # 检查输出文件是否存在
        if not os.path.exists(out_path):
            raise ValueError("输出文件未生成")
        
        print(f"视频片段提取成功: {out_path}")
        return out_path, "", out_path  # 返回视频路径、空错误消息和状态
        
    except Exception as e:
        error_msg = f"提取视频片段时出错: {str(e)}"
        print(error_msg)
        return None, error_msg, None  # 返回 None、错误消息和状态 