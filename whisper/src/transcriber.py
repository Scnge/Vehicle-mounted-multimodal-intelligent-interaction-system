import os
import whisper
import torch
import time

class WhisperTranscriber:
    """Whisper语音转录模块"""
    
    def __init__(self, model_size="tiny", device="auto",
                 save_transcript=False, transcript_dir="transcripts",
                 language="zh"):
        """
        初始化Whisper转录器
        
        参数:
            model_size: Whisper模型大小 (tiny, base, small, medium, large)
            device: 使用的设备 ("cpu", "cuda", "mps", "auto")
            save_transcript: 是否保存转录文本
            transcript_dir: 转录文本保存目录
            language: 转录语言
        """
        self.model_size = model_size
        self.save_transcript = save_transcript
        self.transcript_dir = transcript_dir
        self.language = language
        
        # 创建转录目录
        if self.save_transcript:
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
        
        # 检查MPS (Apple Silicon GPU)
        mps_available = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        if mps_available:
            available_devices.append("mps")
            print(f"MPS (Apple Silicon GPU) 可用: {mps_available}")
        
        print(f"可用设备: {', '.join(available_devices)}")
        
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
            
            # 使用whisper轻量级选项以加快速度
            result = self.model.transcribe(
                audio_file,
                language=self.language,
                task="transcribe",
                verbose=False,
                fp16=False,  # 确保使用FP32
                without_timestamps=True  # 不需要时间戳以加快速度
            )
            
            transcript_text = result["text"].strip()
            transcript_file = None
            
            # 只在有文本时处理
            if transcript_text:
                print(f"\n转录结果: {transcript_text}")
                
                # 保存转录文本
                if self.save_transcript:
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    transcript_file = os.path.join(self.transcript_dir, f"transcript_{timestamp}.txt")
                    
                    with open(transcript_file, "w", encoding="utf-8") as f:
                        f.write(transcript_text)
                    print(f"转录文本已保存到: {transcript_file}")
            else:
                print("\n未检测到有效语音内容")
            
            return transcript_text, transcript_file
                
        except Exception as e:
            print(f"转录时出错: {e}")
            return None, None