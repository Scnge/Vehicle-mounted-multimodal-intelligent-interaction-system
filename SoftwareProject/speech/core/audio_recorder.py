import pyaudio
import wave
import threading
import tempfile
import os
import time
import numpy as np

class AudioRecorder:
    """音频录制模块"""
    
    def __init__(self, 
                 format=pyaudio.paInt16,
                 channels=1,
                 rate=16000,
                 chunk=1024,
                 save_audio=False,
                 audio_dir="recordings"):
        """
        初始化音频录制模块
        
        参数:
            format: 音频格式
            channels: 声道数
            rate: 采样率
            chunk: 每次读取的帧数
            save_audio: 是否保存录音文件
            audio_dir: 录音文件保存目录
        """
        self.format = format
        self.channels = channels
        self.rate = rate
        self.chunk = chunk
        self.save_audio = save_audio
        self.audio_dir = audio_dir
        
        # 创建音频目录
        if self.save_audio:
            os.makedirs(self.audio_dir, exist_ok=True)
        
        self.audio = pyaudio.PyAudio()
        self.recording = False
        self.stream = None
        self.frames = []
        self.record_thread = None
        
    def start_recording(self):
        """开始录音"""
        if self.recording:
            return
            
        self.recording = True
        self.record_thread = threading.Thread(target=self._record_audio)
        self.record_thread.daemon = True
        self.record_thread.start()
        return True
    
    def _record_audio(self):
        """录音线程函数"""
        try:
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk
            )
            
            self.frames = []
            
            while self.recording:
                chunk_frames = []
                # 收集一段音频
                for _ in range(0, int(self.rate / self.chunk * 0.5)):  # 每0.5秒检查一次
                    if not self.recording:
                        break
                    try:
                        data = self.stream.read(self.chunk, exception_on_overflow=False)
                        chunk_frames.append(data)
                    except Exception as e:
                        print(f"读取音频数据失败: {e}")
                        self.recording = False
                        break
                
                if chunk_frames:
                    self.frames.extend(chunk_frames)
            
            # 清理
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
                
        except Exception as e:
            print(f"录音过程中出错: {e}")
            self.recording = False
    
    def stop_recording(self):
        """停止录音"""
        if not self.recording:
            return None
            
        self.recording = False
        
        # 等待录音线程结束
        if self.record_thread and self.record_thread.is_alive():
            self.record_thread.join(timeout=2.0)
        
        # 如果没有录音数据
        if not self.frames:
            return None
        
        # 保存录音
        return self._save_audio_file()
    
    def _save_audio_file(self):
        """保存录音文件，返回文件路径"""
        try:
            # 创建临时文件或保存文件
            if self.save_audio:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                audio_file = os.path.join(self.audio_dir, f"recording_{timestamp}.wav")
            else:
                temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                audio_file = temp_file.name
                temp_file.close()
            
            # 写入WAV文件
            wf = wave.open(audio_file, 'wb')
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.audio.get_sample_size(self.format))
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(self.frames))
            wf.close()
            
            return audio_file
            
        except Exception as e:
            print(f"保存音频文件失败: {e}")
            return None
    
    def get_audio_data_array(self):
        """将录音数据转换为numpy数组"""
        if not self.frames:
            return None
        
        audio_data = b''.join(self.frames)
        return np.frombuffer(audio_data, dtype=np.int16)
    
    def cleanup(self):
        """清理资源"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        
        self.audio.terminate()