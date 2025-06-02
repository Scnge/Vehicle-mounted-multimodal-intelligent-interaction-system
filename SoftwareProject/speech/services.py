# speech/services.py
import threading
import time
import os
from django.conf import settings
from .core.wake_word import WakeWordDetector
from .core.audio_recorder import AudioRecorder
from .core.transcriber import WhisperTranscriber
from .views import find_best_match, execute_action
from .models import SpeechRecord

class SpeechRecognitionService:
    """语音识别后台服务"""
    
    def __init__(self):
        self.running = False
        self.wake_word_detector = None
        self.recorder = None
        self.transcriber = None
        
    def start(self):
        """启动语音识别服务"""
        if self.running:
            return
            
        try:
            # 初始化组件
            self.recorder = AudioRecorder(save_audio=False)
            self.transcriber = WhisperTranscriber(
                model_size="tiny",
                device="auto",
                save_transcript=False
            )
            
            # 创建唤醒词检测器
            self.wake_word_detector = WakeWordDetector(
                wake_word="你好小智",
                callback=self._on_wake_word_detected
            )
            
            # 启动唤醒词检测
            if self.wake_word_detector.start():
                self.running = True
                print("🎤 语音识别服务已启动")
            else:
                print("❌ 语音识别服务启动失败")
                
        except Exception as e:
            print(f"❌ 语音识别服务初始化失败: {e}")
    
    def _on_wake_word_detected(self):
        """检测到唤醒词时的回调"""
        print("🎯 检测到唤醒词，触发页面跳转...")
        
        # 创建唤醒词检测标志文件，用于通知前端跳转
        try:
            wake_word_flag_path = os.path.join(settings.BASE_DIR, 'wake_word_detected.flag')
            with open(wake_word_flag_path, 'w') as f:
                f.write(str(time.time()))
            print("✅ 唤醒词检测标志已创建")
        except Exception as e:
            print(f"❌ 创建唤醒词标志文件失败: {e}")
        
        # 开始录音
        self.recorder.start_recording()
        time.sleep(3)  # 录音3秒
        
        # 停止录音并转录
        audio_file = self.recorder.stop_recording()
        if audio_file:
            transcript, _ = self.transcriber.transcribe(audio_file)
            if transcript:
                self._process_command(transcript)
    
    def _process_command(self, text):
        """处理语音指令"""
        try:
            # 查找匹配的指令
            command, similarity = find_best_match(text)
            
            # 记录语音识别结果
            record = SpeechRecord.objects.create(
                original_text=text,
                matched_command=command,
                similarity_score=similarity
            )
            
            if command:
                # 执行动作
                result = execute_action(command.action)
                record.executed = True
                record.save()
                print(f"✅ 执行指令: {command.command} -> {result['message']}")
            else:
                print(f"❌ 未找到匹配的指令: {text}")
                
        except Exception as e:
            print(f"❌ 处理语音指令时出错: {e}")
    
    def stop(self):
        """停止语音识别服务"""
        self.running = False
        if self.wake_word_detector:
            self.wake_word_detector.stop()
        print("🛑 语音识别服务已停止")