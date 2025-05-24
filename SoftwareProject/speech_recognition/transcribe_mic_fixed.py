import whisper
import pyaudio
import wave
import numpy as np
import os
import tempfile
import time
import threading
import sys
import platform

# 检查平台
is_mac = platform.system() == 'Darwin'

# 根据平台选择键盘输入方式
if is_mac:
    # 在macOS上使用简单的输入方法
    print("检测到macOS系统，将使用简单的键盘输入方式")
    use_pynput = False
else:
    try:
        from pynput import keyboard
        use_pynput = True
    except ImportError:
        print("未安装pynput库，将使用简单的键盘输入方式")
        print("如需使用更好的键盘控制，请运行: pip install pynput")
        use_pynput = False

# 音频参数配置
FORMAT = pyaudio.paInt16
CHANNELS = 1  # 声道数，1为单声道
RATE = 16000
CHUNK = 1024  # 每次读取的帧数
RECORD_SECONDS = 5

class WhisperTranscriber:
    def __init__(self, model_size="tiny", device="auto"):
        """
        初始化Whisper转录器
        
        参数:
            model_size: Whisper模型大小 (tiny, base, small, medium, large)
            device: 使用的设备 ("cpu", "cuda", "mps", "auto")
        """
        print(f"加载 Whisper {model_size} 模型...")
        
        # 检查设备可用性
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
            else:
                chosen_device = "cpu"
                print("自动选择CPU设备")
        
        # 检查指定设备是否可用
        if chosen_device not in available_devices:
            print(f"警告: 请求的设备 '{chosen_device}' 不可用，将使用CPU替代")
            chosen_device = "cpu"
        
        print(f"将使用设备: {chosen_device}")
        
        try:
            # 如果使用CPU，限制线程数以避免过度使用
            if chosen_device == "cpu":
                torch.set_num_threads(2)
            
            # 加载模型
            self.model = whisper.load_model(model_size, device=chosen_device)
            print("模型加载完成！")
        except Exception as e:
            print(f"模型加载失败: {e}")
            sys.exit(1)
        
        try:
            self.audio = pyaudio.PyAudio()
            self.recording = False
            self.running = True
            self.stream = None
            self.frames = []
            self.record_thread = None
            self.transcribe_thread = None
        except Exception as e:
            print(f"初始化PyAudio失败: {e}")
            sys.exit(1)
        
        # 如果使用pynput，初始化键盘监听器
        self.listener = None
        if use_pynput:
            self.start_keyboard_listener()
    
    def start_keyboard_listener(self):
        """启动键盘监听"""
        if use_pynput:
            try:
                # 定义控制键
                START_KEY = keyboard.KeyCode.from_char('r')  # 'r' 键开始录音
                STOP_KEY = keyboard.KeyCode.from_char('s')   # 's' 键停止录音
                EXIT_KEY = keyboard.KeyCode.from_char('q')   # 'q' 键退出程序
                
                def on_key_press(key):
                    try:
                        if key == START_KEY and not self.recording:
                            print("\n按下了开始录音键 (r)")
                            if self.record_thread is None or not self.record_thread.is_alive():
                                self.start_recording()
                        elif key == STOP_KEY and self.recording:
                            print("\n按下了停止录音键 (s)")
                            self.stop_recording()
                        elif key == EXIT_KEY:
                            print("\n按下了退出程序键 (q)")
                            self.running = False
                            self.stop_recording()
                            return False  # 停止监听
                    except AttributeError:
                        pass  # 忽略特殊键
                
                self.listener = keyboard.Listener(on_press=on_key_press)
                self.listener.start()
                print("键盘监听已启动")
            except Exception as e:
                print(f"启动键盘监听失败: {e}")
                use_pynput = False
    
    def handle_simple_input(self):
        """简单的控制台输入处理（不使用pynput时）"""
        print("\n输入控制命令：")
        print(" r - 开始录音")
        print(" s - 停止录音")
        print(" q - 退出程序")
        
        while self.running:
            try:
                import select
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    cmd = sys.stdin.readline().strip().lower()
                    if cmd == 'r' and not self.recording:
                        print("\n开始录音")
                        self.start_recording()
                    elif cmd == 's' and self.recording:
                        print("\n停止录音")
                        self.stop_recording()
                    elif cmd == 'q':
                        print("\n退出程序")
                        self.running = False
                        self.stop_recording()
                        break
            except Exception as e:
                print(f"输入处理错误: {e}")
                time.sleep(0.5)
    
    def start_recording(self):
        """开始录音"""
        if self.recording:
            return
            
        self.recording = True
        self.record_thread = threading.Thread(target=self.record_audio)
        self.record_thread.daemon = True
        self.record_thread.start()
        print("===== 开始录音 =====")
        print("说话中...(输入 's' 停止录音, 输入 'q' 退出程序)")
    
    def record_audio(self):
        """录音线程函数"""
        try:
            self.stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            
            self.frames = []
            
            while self.recording:
                chunk_frames = []
                # 收集一段音频
                for _ in range(0, int(RATE / CHUNK * 0.5)):  # 每0.5秒检查一次
                    if not self.recording:
                        break
                    try:
                        data = self.stream.read(CHUNK, exception_on_overflow=False)
                        chunk_frames.append(data)
                    except Exception as e:
                        print(f"读取音频数据失败: {e}")
                        self.recording = False
                        break
                
                if chunk_frames:
                    self.frames.extend(chunk_frames)
            
            # 录音结束，处理完整的录音
            if self.frames:
                self.process_complete_recording()
            
            # 清理
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
            
        except Exception as e:
            print(f"录音过程中出错: {e}")
            self.recording = False
    
    def process_complete_recording(self):
        """处理完整的录音"""
        if not self.frames:
            print("没有录音数据")
            return
            
        try:
            print("处理录音...")
            
            # 保存完整录音的临时文件
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_filename = f.name
            
            wf = wave.open(temp_filename, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(self.frames))
            wf.close()
            
            # 转录完整录音（在新线程中进行）
            self.transcribe_thread = threading.Thread(
                target=self.transcribe_audio, 
                args=(temp_filename,)
            )
            self.transcribe_thread.daemon = True
            self.transcribe_thread.start()
            
        except Exception as e:
            print(f"处理录音时出错: {e}")
    
    def transcribe_audio(self, audio_file):
        """转录音频文件"""
        try:
            print("转录中...")
            
            # 使用whisper轻量级选项以加快速度
            result = self.model.transcribe(
                audio_file,
                language="zh",
                task="transcribe",
                verbose=False,
                fp16=False,  # 确保使用FP32
                without_timestamps=True  # 不需要时间戳以加快速度
            )
            
            # 只在有文本时打印结果
            if result["text"].strip():
                print(f"\n转录结果: {result['text']}")
                print("-" * 50)
            else:
                print("\n未检测到有效语音内容")
                print("-" * 50)
            
            # 删除临时文件
            try:
                os.unlink(audio_file)
            except Exception as e:
                print(f"删除临时文件失败: {e}")
            
            print("转录完成。准备进行下一次录音...")
            if use_pynput:
                print("按 'r' 开始新的录音, 按 'q' 退出程序")
            else:
                print("输入 'r' 开始新的录音, 输入 'q' 退出程序")
                
        except Exception as e:
            print(f"转录时出错: {e}")
    
    def stop_recording(self):
        """停止录音"""
        if not self.recording:
            return
            
        print("===== 停止录音 =====")
        self.recording = False
        
        # 等待录音线程结束
        if self.record_thread and self.record_thread.is_alive():
            self.record_thread.join(timeout=2.0)
    
    def run(self):
        """主运行函数"""
        try:
            print("\n===== 语音转录系统已启动 =====")
            
            if use_pynput:
                print("按 'r' 开始录音")
                print("按 's' 停止录音")
                print("按 'q' 退出程序")
                
                # 如果使用pynput，主线程只需等待
                while self.running:
                    time.sleep(0.1)  # 降低CPU使用率
            else:
                # 如果不使用pynput，使用简单的输入处理
                self.handle_simple_input()
                
        except KeyboardInterrupt:
            print("\n用户中断程序")
            self.running = False
            self.stop_recording()
        except Exception as e:
            print(f"运行时出错: {e}")
        finally:
            if self.listener and self.listener.running:
                self.listener.stop()
            self.audio.terminate()
            print("\n程序已退出")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="使用Whisper实时转录麦克风输入的中文")
    parser.add_argument("--model", type=str, default="tiny", 
                      choices=["tiny", "base", "small", "medium", "large"],
                      help="Whisper模型大小")
    parser.add_argument("--device", type=str, default="auto",
                      choices=["cpu", "cuda", "mps", "auto"],
                      help="运行设备 (cpu, cuda, mps, auto)")
    
    args = parser.parse_args()
    
    transcriber = WhisperTranscriber(model_size=args.model, device=args.device)
    transcriber.run()