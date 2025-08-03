import os
import tempfile
import subprocess
import whisper
import ssl
from utils.time_utils import seconds_to_ass_time
from utils.ffmpeg_utils import run_ffmpeg_command

class SubtitleGenerator:
    def __init__(self):
        self.model = None
        # self.translator = Translator()  # 暂时注释掉翻译功能
    
    def load_model(self, model_size="base"):
        """加载Whisper模型"""
        try:
            if self.model is None:
                print(f"正在加载Whisper模型: {model_size}")
                # 设置SSL验证为False来解决证书问题
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
            start_time = seconds_to_ass_time(subtitle['start'])
            end_time = seconds_to_ass_time(subtitle['end'])
            
            # 英文字幕
            en_text = subtitle['en'].replace('\n', '\\N')
            ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{en_text}\n"
            
            # 中文字幕
            if 'zh' in subtitle:
                zh_text = subtitle['zh'].replace('\n', '\\N')
                ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{zh_text}\n"
        
        return ass_content
    
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
            
            success = run_ffmpeg_command(cmd, "字幕嵌入命令")
            
            # 清理临时ASS文件
            if os.path.exists(ass_path):
                os.remove(ass_path)
            
            if success:
                print(f"字幕嵌入成功: {output_path}")
                return output_path
            else:
                print(f"字幕嵌入失败")
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