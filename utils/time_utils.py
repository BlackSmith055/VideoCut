import re

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

def seconds_to_ass_time(seconds: float) -> str:
    """将秒数转换为ASS时间格式 (H:MM:SS.cc)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    centiseconds = int((secs % 1) * 100)
    secs = int(secs)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}" 