import os
import whisper
import torch
import time
import json
from datetime import datetime

class WhisperTranscriber:
    """Whisper语音转录模块"""
    
    def __init__(self, model_size="tiny", device="auto",
                 save_transcript=False, transcript_dir="data/transcripts",
                 language="zh", save_json=True):
        """
        初始化Whisper转录器
        
        参数:
            model_size: Whisper模型大小 (tiny, base, small, transcriber = WhisperTranscriber(model_size="medium", device="auto") large)
            device: 使用的设备 ("cpu", "cuda", "mps", "auto")
            save_transcript: 是否保存转录文本
            transcript_dir: 转录文本保存目录
            language: 转录语言
            save_json: 是否保存JSON格式的转录结果
        """
        self.model_size = model_size
        self.save_transcript = save_transcript
        self.transcript_dir = transcript_dir
        self.language = language
        self.save_json = save_json
        
        # 创建转录目录
        # 确保使用whisper目录下的路径
        whisper_dir = os.path.dirname(os.path.dirname(__file__))
        self.transcript_dir = os.path.join(whisper_dir, "data", "transcripts")
        if self.save_transcript or self.save_json:
            os.makedirs(self.transcript_dir, exist_ok=True)
        
        # 检查设备可用性
        self.device = self._check_device(device)
        
        # 加载模型
        self._load_model()
    
    def _check_device(self, device):
        """检查并选择设备"""
        print(f"加载 Whisper {self.model_size} 模型...")
        
        import torch
        available_devices = []
        
        # 检查CPU
        available_devices.append("cpu")
        
        # 检查CUDA (NVIDIA GPU)
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            available_devices.append("cuda")
            cuda_device_name = torch.cuda.get_device_name(0) if cuda_available else "无"
            cuda_device_count = torch.cuda.device_count() if cuda_available else 0
            print(f"CUDA可用: {cuda_available}, 设备: {cuda_device_name}, 数量: {cuda_device_count}")
        
     
        
        # 自动选择设备或使用指定设备
        chosen_device = device
        if device == "auto":
            if "cuda" in available_devices:
                chosen_device = "cuda"
                print("自动选择CUDA设备")
            elif "mps" in available_devices:
                chosen_device = "mps" 
                print("自动选择MPS设备")
            else:
                chosen_device = "cpu"
                print("自动选择CPU设备")
        
        # 检查指定设备是否可用
        if chosen_device not in available_devices:
            print(f"警告: 请求的设备 '{chosen_device}' 不可用，将使用CPU替代")
            chosen_device = "cpu"
        
        print(f"将使用设备: {chosen_device}")
        return chosen_device
    
    def _load_model(self):
        """加载Whisper模型"""
        try:
            # 如果使用CPU，限制线程数以避免过度使用
            if self.device == "cpu":
                torch.set_num_threads(2)
            
            # 加载模型
            self.model = whisper.load_model(self.model_size, device=self.device)
            print("模型加载完成！")
        except Exception as e:
            print(f"模型加载失败: {e}")
            raise
    
    def transcribe(self, audio_file):
        """
        转录音频文件
        
        参数:
            audio_file: 音频文件路径
            
        返回:
            (str, str): (转录文本, 保存的文本文件路径(如果有))
        """
        try:
            print("转录中...")
            
            # 使用whisper平衡配置
            result = self.model.transcribe(
                audio_file,
                language=self.language,
                task="transcribe",
                verbose=False,
                fp16=True,  # 使用FP16加速
                without_timestamps=True,  # 不需要时间戳以加快速度
                beam_size=3,  # 适中的beam search大小，提高准确性
                best_of=2,  # 增加候选数量以提高准确性
                temperature=0.2  # 适当增加采样温度，提高多样性
            )
            
            transcript_text = result["text"].strip()
            transcript_file = None
            json_file = None
            
            # 只在有文本时处理
            if transcript_text:
                print(f"\n转录结果: {transcript_text}")
                
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                
                # 保存转录文本
                if self.save_transcript:
                    transcript_file = os.path.join(self.transcript_dir, f"transcript_{timestamp}.txt")
                    
                    with open(transcript_file, "w", encoding="utf-8") as f:
                        f.write(transcript_text)
                    print(f"转录文本已保存到: {transcript_file}")
                
                # 保存JSON格式的转录结果
                if self.save_json:
                    json_file = os.path.join(self.transcript_dir, f"voice_input_{timestamp}.json")
                    
                    # 准备JSON数据
                    json_data = {
                        "timestamp": datetime.now().isoformat(),
                        "audio_file": audio_file,
                        "transcript": transcript_text,
                        "sectionpart": "voice",
                        "model_info": {
                            "model_size": self.model_size,
                            "device": self.device,
                            "language": self.language
                        }
                    }
                    
                    with open(json_file, "w", encoding="utf-8") as f:
                        json.dump(json_data, f, ensure_ascii=False, indent=2)
                    print(f"JSON转录结果已保存到: {json_file}")
            else:
                print("\n未检测到有效语音内容")
            
            return transcript_text, transcript_file
                
        except Exception as e:
            print(f"转录时出错: {e}")
            return None, None
    
    def transcribe_with_speech_recognition(self, audio_file):
        """使用speech_recognition进行音频转录
        
        参数:
            audio_file: 音频文件路径
            
        返回:
            (str, str): (转录文本, 保存的文本文件路径(如果有))
        """
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            
            print("使用speech_recognition转录中...")
            
            # 读取音频文件
            with sr.AudioFile(audio_file) as source:
                # 调整环境噪音
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                # 录制音频
                audio = recognizer.record(source)
            
            # 使用Google Speech Recognition进行识别
            transcript_text = recognizer.recognize_google(audio, language=self.language)
            transcript_file = None
            json_file = None
            
            # 只在有文本时处理
            if transcript_text:
                print(f"\n转录结果: {transcript_text}")
                
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                
                # 保存转录文本
                if self.save_transcript:
                    transcript_file = os.path.join(self.transcript_dir, f"sr_transcript_{timestamp}.txt")
                    
                    with open(transcript_file, "w", encoding="utf-8") as f:
                        f.write(transcript_text)
                    print(f"转录文本已保存到: {transcript_file}")
                
                # 保存JSON格式的转录结果
                if self.save_json:
                    json_file = os.path.join(self.transcript_dir, f"sr_voice_input_{timestamp}.json")
                    
                    # 准备JSON数据
                    json_data = {
                        "timestamp": datetime.now().isoformat(),
                        "audio_file": audio_file,
                        "transcript": transcript_text,
                        "sectionpart": "voice",
                        "model_info": {
                            "model_type": "speech_recognition",
                            "engine": "google",
                            "language": self.language
                        }
                    }
                    
                    with open(json_file, "w", encoding="utf-8") as f:
                        json.dump(json_data, f, ensure_ascii=False, indent=2)
                    print(f"JSON转录结果已保存到: {json_file}")
            else:
                print("\n未检测到有效语音内容")
            
            return transcript_text, transcript_file
                
        except sr.UnknownValueError:
            print("无法识别语音内容")
            return None, None
        except sr.RequestError as e:
            print(f"请求Google Speech Recognition服务失败: {e}")
            return None, None
        except Exception as e:
            print(f"转录时出错: {e}")
            return None, None
            