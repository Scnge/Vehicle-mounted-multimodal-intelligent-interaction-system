#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
import time
import numpy as np
import pyaudio
import tempfile
import os
import wave
from collections import deque
import audioop

class WakeWordDetector:
    """免费的唤醒词检测模块 - 专门检测'你好小智'"""
    DEFAULT_WAKE_WORD = "你好小智"
    def __init__(self, wake_word="你好小智", callback=None,
                 format=pyaudio.paInt16, channels=1, rate=16000, chunk=1024,
                 sensitivity=0.6):
        """
        初始化唤醒词检测器
        
        参数:
            wake_word: 唤醒词（目前支持"你好小智"）
            callback: 检测到唤醒词时的回调函数
            format: 音频格式
            channels: 声道数
            rate: 采样率
            chunk: 每次读取的帧数
            sensitivity: 检测灵敏度 (0.0-1.0)
        """
        self.wake_word = wake_word
        self.callback = callback
        self.format = format
        self.channels = channels
        self.rate = rate
        self.chunk = chunk
        self.sensitivity = sensitivity
        
        self.listening = False
        self.listen_thread = None
        self.audio = pyaudio.PyAudio()
        self.enabled = False
        
        # 音频缓冲区用于连续检测
        self.audio_buffer = deque(maxlen=int(self.rate * 3 / self.chunk))  # 3秒缓冲
        self.detection_buffer = []
        
        # 初始化检测方法
        self._init_speech_recognition()
        
        if not self.enabled:
            self._init_simple_pattern_detection()
    
    def _init_speech_recognition(self):
        """尝试使用语音识别库进行唤醒词检测"""
        try:
            import speech_recognition as sr
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            
            # 校准环境噪音
            print("正在校准环境噪音...")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            
            self.enabled = True
            self.detection_method = "speech_recognition"
            print(f"✅ 使用语音识别检测唤醒词: '{self.wake_word}'")
            
        except ImportError:
            print("speech_recognition 库未安装")
            print("安装方法: pip install SpeechRecognition pyaudio")
        except Exception as e:
            print(f"初始化语音识别失败: {e}")
    
    def _init_simple_pattern_detection(self):
        """使用简单的音频模式检测作为备用方案"""
        self.detection_method = "pattern"
        
        # 语音活动检测参数
        self.energy_threshold = 2000
        self.zero_crossing_threshold = 50
        self.min_speech_duration = 0.5  # 最短语音时长
        self.max_speech_duration = 3.0  # 最长语音时长
        
        # 检测状态
        self.speech_started = False
        self.speech_start_time = 0
        self.last_detection_time = 0
        self.detection_cooldown = 3.0  # 检测冷却时间
        
        self.enabled = True
        print(f"✅ 使用音频模式检测唤醒词: '{self.wake_word}'")
        print("💡 提示: 请清晰地说出唤醒词，避免背景噪音")
    
    def start(self):
        """开始监听唤醒词"""
        if not self.enabled:
            print("❌ 唤醒词功能未启用")
            return False
        
        if self.listening:
            return True
        
        self.listening = True
        self.listen_thread = threading.Thread(target=self._listen)
        self.listen_thread.daemon = True
        self.listen_thread.start()
        
        print(f"🎧 开始监听唤醒词 ({self.detection_method}): '{self.wake_word}'")
        return True
    
    def _listen(self):
        """监听线程"""
        if self.detection_method == "speech_recognition":
            self._listen_with_speech_recognition()
        else:
            self._listen_with_pattern_detection()
    
    def _listen_with_speech_recognition(self):
        """使用语音识别进行监听"""
        import speech_recognition as sr
        
        print("🎤 语音识别监听已启动...")
        
        while self.listening:
            try:
                # 设置较短的超时时间，避免阻塞太久
                with self.microphone as source:
                    # 监听音频，超时1秒
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=3)
                
                try:
                    # 使用Google Web Speech API（免费但有限制）
                    text = self.recognizer.recognize_google(audio, language='zh-CN')
                    print(f"🔍 识别到: {text}")
                    
                    # 检查是否包含唤醒词
                    if self._check_wake_word_match(text):
                        print(f"🎯 检测到唤醒词: '{self.wake_word}'")
                        self._trigger_callback()
                        
                except sr.UnknownValueError:
                    # 无法识别语音，继续监听
                    pass
                except sr.RequestError as e:
                    print(f"⚠️ 语音识别服务错误: {e}")
                    # 切换到备用方案
                    print("🔄 切换到音频模式检测...")
                    self._init_simple_pattern_detection()
                    self._listen_with_pattern_detection()
                    break
                    
            except sr.WaitTimeoutError:
                # 超时继续监听
                if not self.listening:
                    break
            except Exception as e:
                if self.listening:
                    print(f"⚠️ 监听错误: {e}")
                break
        
        print("🛑 语音识别监听已停止")
    
    def _listen_with_pattern_detection(self):
        """使用音频模式检测进行监听"""
        try:
            stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk,
                input_device_index=None
            )
            
            print("🎤 音频模式监听已启动...")
            
            while self.listening:
                try:
                    pcm = stream.read(self.chunk, exception_on_overflow=False)
                    pcm_data = np.frombuffer(pcm, dtype=np.int16)
                    
                    # 检测语音活动
                    if self._detect_speech_pattern(pcm_data):
                        print(f"🎯 检测到疑似唤醒词模式")
                        self._trigger_callback()
                    
                    time.sleep(0.01)
                    
                except Exception as e:
                    if self.listening:
                        print(f"⚠️ 读取音频错误: {e}")
                    break
            
            stream.stop_stream()
            stream.close()
            
        except Exception as e:
            print(f"❌ 音频模式监听错误: {e}")
        finally:
            print("🛑 音频模式监听已停止")
    
    def _check_wake_word_match(self, text):
        """检查识别的文本是否匹配唤醒词"""
        text = text.replace(" ", "").lower()
        wake_word = self.wake_word.replace(" ", "").lower()
        
        # 精确匹配
        if wake_word in text:
            return True
        
        # 模糊匹配（处理识别错误）
        variations = [
            "你好小智", "你好小知", "你好小志", "你好小制",
            "你小智", "你小知", "你小志", "你小制",
            "好小智", "好小知", "好小志", "好小制",
            "小智", "小知", "小志", "小制"
        ]
        
        for variation in variations:
            if variation.lower() in text:
                return True
        
        return False
    
    def _detect_speech_pattern(self, pcm_data):
        """基于音频特征检测语音模式"""
        current_time = time.time()
        
        # 计算音频特征
        energy = np.sum(pcm_data.astype(np.float32) ** 2) / len(pcm_data)
        zero_crossings = self._count_zero_crossings(pcm_data)
        
        # 检测语音开始
        if not self.speech_started and energy > self.energy_threshold:
            if zero_crossings > self.zero_crossing_threshold:
                self.speech_started = True
                self.speech_start_time = current_time
                self.detection_buffer = [pcm_data]
                return False
        
        # 收集语音数据
        elif self.speech_started:
            self.detection_buffer.append(pcm_data)
            speech_duration = current_time - self.speech_start_time
            
            # 检测语音结束或超时
            if (energy < self.energy_threshold * 0.5 or 
                speech_duration > self.max_speech_duration):
                
                self.speech_started = False
                
                # 检查语音时长是否合适
                if (self.min_speech_duration <= speech_duration <= self.max_speech_duration and
                    current_time - self.last_detection_time > self.detection_cooldown):
                    
                    # 分析语音特征
                    if self._analyze_speech_features():
                        self.last_detection_time = current_time
                        return True
                
                self.detection_buffer = []
        
        return False
    
    def _count_zero_crossings(self, signal):
        """计算零交叉率"""
        zero_crossings = 0
        for i in range(1, len(signal)):
            if (signal[i] >= 0) != (signal[i-1] >= 0):
                zero_crossings += 1
        return zero_crossings
    
    def _analyze_speech_features(self):
        """分析语音特征判断是否为目标唤醒词"""
        if not self.detection_buffer:
            return False
        
        # 合并音频数据
        combined_audio = np.concatenate(self.detection_buffer)
        
        # 计算整体特征
        total_energy = np.sum(combined_audio.astype(np.float32) ** 2) / len(combined_audio)
        total_zero_crossings = self._count_zero_crossings(combined_audio)
        
        # 简单的特征匹配（可以根据实际情况调整阈值）
        # "你好小智" 通常有4个音节，能量分布相对均匀
        
        # 分析能量分布
        segment_size = len(combined_audio) // 4
        segment_energies = []
        
        for i in range(4):
            start = i * segment_size
            end = start + segment_size if i < 3 else len(combined_audio)
            segment = combined_audio[start:end]
            if len(segment) > 0:
                segment_energy = np.sum(segment.astype(np.float32) ** 2) / len(segment)
                segment_energies.append(segment_energy)
        
        if len(segment_energies) >= 3:
            # 检查是否有相对均匀的能量分布（多音节特征）
            energy_variance = np.var(segment_energies)
            mean_energy = np.mean(segment_energies)
            
            # 根据经验调整的阈值
            if (mean_energy > self.energy_threshold * 0.8 and
                energy_variance < mean_energy * 0.5 and
                total_zero_crossings > len(combined_audio) * 0.1):
                return True
        
        return False
    
    def _trigger_callback(self):
        """触发回调函数"""
        if self.callback:
            try:
                # 在新线程中执行回调，避免阻塞监听
                callback_thread = threading.Thread(target=self.callback)
                callback_thread.daemon = True
                callback_thread.start()
            except Exception as e:
                print(f"❌ 执行回调函数时出错: {e}")
    
    def stop(self):
        """停止监听"""
        print("🛑 正在停止唤醒词监听...")
        self.listening = False
        
        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=2.0)
            if self.listen_thread.is_alive():
                print("⚠️ 监听线程未能正常停止")
    
    def cleanup(self):
        """清理资源"""
        self.stop()
        
        try:
            self.audio.terminate()
            print("✅ PyAudio 资源已清理")
        except Exception as e:
            print(f"⚠️ 清理 PyAudio 资源时出错: {e}")
    
    def set_sensitivity(self, sensitivity):
        """设置检测灵敏度"""
        self.sensitivity = max(0.0, min(1.0, sensitivity))
        
        # 调整阈值
        if self.detection_method == "pattern":
            base_threshold = 3000
            self.energy_threshold = base_threshold * (1.0 - self.sensitivity)
            print(f"🔧 检测灵敏度已设置为: {self.sensitivity}")
            print(f"🔧 能量阈值调整为: {self.energy_threshold}")
        else:
            print(f"🔧 检测灵敏度已设置为: {self.sensitivity}")
    
    def test_microphone(self):
        """测试麦克风是否正常工作"""
        print("🎤 正在测试麦克风...")
        try:
            stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk
            )
            
            print("💬 请说话测试麦克风...")
            energies = []
            
            for i in range(50):  # 测试约5秒
                data = stream.read(self.chunk, exception_on_overflow=False)
                pcm_data = np.frombuffer(data, dtype=np.int16)
                energy = np.sum(pcm_data.astype(np.float32) ** 2) / len(pcm_data)
                energies.append(energy)
                
                if i % 10 == 0:  # 每秒显示一次
                    print(f"📊 音频能量: {energy:.2f}")
                
                time.sleep(0.1)
            
            stream.stop_stream()
            stream.close()
            
            avg_energy = np.mean(energies)
            max_energy = np.max(energies)
            
            print("✅ 麦克风测试完成")
            print(f"📈 平均能量: {avg_energy:.2f}")
            print(f"📈 最大能量: {max_energy:.2f}")
            
            if max_energy > 1000:
                print("✅ 麦克风工作正常")
            else:
                print("⚠️ 麦克风可能有问题，能量值过低")
            
        except Exception as e:
            print(f"❌ 麦克风测试失败: {e}")


# 辅助函数
def list_audio_devices():
    """列出可用的音频设备"""
    audio = pyaudio.PyAudio()
    print("🎧 可用的音频输入设备:")
    
    for i in range(audio.get_device_count()):
        device_info = audio.get_device_info_by_index(i)
        if device_info['maxInputChannels'] > 0:
            print(f"  📱 设备 {i}: {device_info['name']} (输入通道: {device_info['maxInputChannels']})")
    
    audio.terminate()


def install_dependencies():
    """显示安装依赖的说明"""
    print("📦 安装唤醒词检测依赖")
    print("=" * 50)
    print("必需依赖:")
    print("pip install pyaudio numpy")
    print()
    print("可选依赖（推荐，提升准确性）:")
    print("pip install SpeechRecognition")
    print()
    print("如果遇到 pyaudio 安装问题:")
    print("macOS: brew install portaudio && pip install pyaudio")
    print("Ubuntu: sudo apt-get install portaudio19-dev && pip install pyaudio")
    print("Windows: pip install pipwin && pipwin install pyaudio")


# 测试函数
def test_wake_word_detector(wake_word="你好小智", test_duration=30):
    """测试唤醒词检测器"""
    def on_wake_word():
        print("🎉 检测到唤醒词回调被触发!")
        print(f"✨ 成功检测到: '{wake_word}'")
    
    print(f"🧪 开始测试唤醒词检测器")
    print(f"🎯 目标唤醒词: '{wake_word}'")
    print(f"⏱️ 测试时长: {test_duration}秒")
    
    detector = WakeWordDetector(
        wake_word=wake_word,
        callback=on_wake_word,
        sensitivity=0.6
    )
    
    try:
        detector.start()
        
        print(f"💬 请清晰地说出: '{wake_word}'")
        print("🔇 保持环境相对安静以提高检测准确性")
        
        for remaining in range(test_duration, 0, -1):
            if remaining % 10 == 0:
                print(f"⏰ 剩余测试时间: {remaining}秒")
            time.sleep(1)
        
    except KeyboardInterrupt:
        print("\n⛔ 用户中断测试")
    finally:
        detector.cleanup()
        print("✅ 测试完成")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="免费唤醒词检测器 - 专门检测'你好小智'")
    parser.add_argument("--wake_word", type=str, default="你好小智",
                       help="测试用的唤醒词")
    parser.add_argument("--test_duration", type=int, default=30,
                       help="测试持续时间(秒)")
    parser.add_argument("--list_devices", action="store_true",
                       help="列出可用的音频设备")
    parser.add_argument("--test_mic", action="store_true",
                       help="测试麦克风")
    parser.add_argument("--install", action="store_true",
                       help="显示依赖安装说明")
    parser.add_argument("--sensitivity", type=float, default=0.6,
                       help="检测灵敏度 (0.0-1.0)")
    
    args = parser.parse_args()
    
    if args.install:
        install_dependencies()
    elif args.list_devices:
        list_audio_devices()
    elif args.test_mic:
        detector = WakeWordDetector()
        detector.test_microphone()
        detector.cleanup()
    else:
        test_wake_word_detector(args.wake_word, args.test_duration)