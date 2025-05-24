#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time
import threading
import argparse

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.audio_recorder import AudioRecorder
from src.transcriber import WhisperTranscriber
from src.wake_word import WakeWordDetector
from src.utils import is_mac, send_to_decision_center

# 检查平台
if is_mac():
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

class TranscriptionApp:
    """语音转录应用"""
    
    def __init__(self, args):
        """
        初始化应用
        
        参数:
            args: 命令行参数
        """
        self.running = True
        self.recording = False
        self.args = args  # 保存参数供后续使用
        
        # 创建音频录制器
        self.recorder = AudioRecorder(
            save_audio=args.save_audio,
            audio_dir=args.audio_dir
        )
        
        # 创建转录器
        self.transcriber = WhisperTranscriber(
            model_size=args.model,
            device=args.device,
            save_transcript=args.save_transcript,
            transcript_dir=args.transcript_dir
        )
        
        # 如果启用唤醒词，创建唤醒词检测器
        self.wake_word_detector = None
        if args.wake_word:
            self.wake_word_detector = WakeWordDetector(
                wake_word=args.wake_word,
                callback=self.start_recording
            )
        
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
                            self.start_recording()
                        elif key == STOP_KEY and self.recording:
                            print("\n按下了停止录音键 (s)")
                            self.stop_recording()
                        elif key == EXIT_KEY:
                            print("\n按下了退出程序键 (q)")
                            self.quit()
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
        
        import select
        while self.running:
            try:
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
                        self.quit()
                        break
            except Exception as e:
                print(f"输入处理错误: {e}")
                time.sleep(0.5)
    
    def start_recording(self):
        """开始录音"""
        if self.recording:
            return
            
        self.recording = True
        self.recorder.start_recording()
        print("===== 开始录音 =====")
        print("说话中...(输入 's' 停止录音, 输入 'q' 退出程序)")
    
    def stop_recording(self):
        """停止录音并转录"""
        if not self.recording:
            return
            
        print("===== 停止录音 =====")
        self.recording = False
        
        # 停止录音并获取音频文件路径
        audio_file = self.recorder.stop_recording()
        
        if audio_file:
            # 根据选择的转录方式进行转录
            if hasattr(self.args, 'use_sr') and self.args.use_sr:
                transcript, _ = self.transcriber.transcribe_with_speech_recognition(audio_file)
            else:
                transcript, _ = self.transcriber.transcribe(audio_file)
            
            # 如果有转录结果，发送到决策中枢
            if transcript:
                send_to_decision_center(transcript)
            
            # 如果不保存录音，删除临时文件
            if not self.recorder.save_audio:
                try:
                    os.unlink(audio_file)
                except Exception as e:
                    print(f"删除临时文件失败: {e}")
        
        print("准备进行下一次录音...")
        if use_pynput:
            print("按 'r' 开始新的录音, 按 'q' 退出程序")
        else:
            print("输入 'r' 开始新的录音, 输入 'q' 退出程序")
    
    def quit(self):
        """退出程序"""
        self.running = False
        self.stop_recording()
        
        # 停止唤醒词检测
        if self.wake_word_detector:
            self.wake_word_detector.cleanup()
        
        # 清理录音资源
        self.recorder.cleanup()
    
    def run(self):
        """主运行函数"""
        try:
            print("\n===== 语音转录系统已启动 =====")
            
            # 如果启用唤醒词，启动唤醒词检测
            if self.wake_word_detector:
                self.wake_word_detector.start()
            
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
            self.quit()
        except Exception as e:
            print(f"运行时出错: {e}")
        finally:
            if self.listener and hasattr(self.listener, 'running') and self.listener.running:
                self.listener.stop()
            print("\n程序已退出")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="使用Whisper实时转录麦克风输入的中文")
    parser.add_argument("--model", type=str, default="tiny", 
                      choices=["tiny", "base", "small", "medium", "large"],
                      help="Whisper模型大小")
    parser.add_argument("--device", type=str, default="auto",
                      choices=["cpu", "cuda", "mps", "auto"],
                      help="运行设备 (cpu, cuda, mps, auto)")
    parser.add_argument("--wake_word", type=str, default=WakeWordDetector.DEFAULT_WAKE_WORD,
                      help="唤醒词，留空则不使用唤醒功能")
    parser.add_argument("--save_audio", action="store_true", 
                      help="是否保存录音文件")
    parser.add_argument("--audio_dir", type=str, default="data/recordings",
                      help="录音文件保存目录")
    parser.add_argument("--save_transcript", action="store_true",
                      help="是否保存转录文字")
    parser.add_argument("--transcript_dir", type=str, default="data/transcripts",
                      help="转录文本保存目录")
    parser.add_argument("--use_sr", action="store_true",
                      help="使用speech_recognition替代whisper进行转录")
    
    args = parser.parse_args()
    
    app = TranscriptionApp(args)
    app.run()

if __name__ == "__main__":
    main()