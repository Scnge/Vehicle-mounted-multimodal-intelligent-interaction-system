import threading
import time
import numpy as np
import pyaudio

class WakeWordDetector:
    """唤醒词检测模块"""
    
    def __init__(self, wake_word="你好小智", callback=None,
                 format=pyaudio.paInt16, channels=1, rate=16000, chunk=1024):
        """
        初始化唤醒词检测器
        
        参数:
            wake_word: 唤醒词
            callback: 检测到唤醒词时的回调函数
            format: 音频格式
            channels: 声道数
            rate: 采样率
            chunk: 每次读取的帧数
        """
        self.wake_word = wake_word
        self.callback = callback
        self.format = format
        self.channels = channels
        self.rate = rate
        self.chunk = chunk
        
        self.listening = False
        self.listen_thread = None
        self.audio = pyaudio.PyAudio()
        
        # 尝试加载唤醒词检测库
        try:
            import pvporcupine
            
            # 使用默认唤醒词或创建自定义唤醒词
            if wake_word in pvporcupine.KEYWORDS:
                self.porcupine = pvporcupine.create(keywords=[wake_word])
            else:
                # 这里应该使用自定义唤醒词的路径
                print(f"警告: 使用默认唤醒词 'porcupine'，因为 '{wake_word}' 不是可用的关键词")
                self.porcupine = pvporcupine.create(keywords=["porcupine"])
            
            self.enabled = True
            print(f"唤醒词设置成功: '{wake_word}'")
            
        except ImportError:
            print("未安装唤醒词检测库，将不使用唤醒词功能")
            print("如需使用唤醒词功能，请运行: pip install pvporcupine")
            self.enabled = False
            
        except Exception as e:
            print(f"初始化唤醒词检测器失败: {e}")
            self.enabled = False
    
    def start(self):
        """开始监听唤醒词"""
        if not self.enabled:
            print("唤醒词功能未启用")
            return False
            
        if self.listening:
            return True
            
        self.listening = True
        self.listen_thread = threading.Thread(target=self._listen)
        self.listen_thread.daemon = True
        self.listen_thread.start()
        print(f"开始监听唤醒词: '{self.wake_word}'")
        return True
    
    def _listen(self):
        """监听线程"""
        try:
            stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk
            )
            
            while self.listening:
                pcm = stream.read(self.chunk, exception_on_overflow=False)
                pcm_data = np.frombuffer(pcm, dtype=np.int16)
                
                # 检测唤醒词
                if hasattr(self, 'porcupine'):
                    keyword_index = self.porcupine.process(pcm_data)
                    
                    if keyword_index >= 0:
                        print(f"\n检测到唤醒词: '{self.wake_word}'")
                        if self.callback:
                            self.callback()
                
            stream.stop_stream()
            stream.close()
            
        except Exception as e:
            print(f"唤醒词监听错误: {e}")
            self.listening = False
    
    def stop(self):
        """停止监听"""
        self.listening = False
        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=1.0)
    
    def cleanup(self):
        """清理资源"""
        self.stop()
        if hasattr(self, 'porcupine'):
            self.porcupine.delete()
        self.audio.terminate()