#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.transcriber import WhisperTranscriber
from src.utils import send_to_decision_center

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="使用Whisper转录音频文件")
    parser.add_argument("--audio", type=str, required=True,
                      help="音频文件路径")
    parser.add_argument("--model", type=str, default="tiny", 
                      choices=["tiny", "base", "small", "medium", "large"],
                      help="Whisper模型大小")
    parser.add_argument("--device", type=str, default="auto",
                      choices=["cpu", "cuda", "mps", "auto"],
                      help="运行设备 (cpu, cuda, mps, auto)")
    parser.add_argument("--save_transcript", action="store_true",
                      help="是否保存转录文字")
    parser.add_argument("--transcript_dir", type=str, default="data/transcripts",
                      help="转录文本保存目录")
    parser.add_argument("--send_to_decision", action="store_true",
                      help="是否将转录结果发送到决策中枢")
    
    args = parser.parse_args()
    
    # 检查音频文件是否存在
    if not os.path.isfile(args.audio):
        print(f"错误: 音频文件 '{args.audio}' 不存在")
        return
    
    # 创建转录器
    transcriber = WhisperTranscriber(
        model_size=args.model,
        device=args.device,
        save_transcript=args.save_transcript,
        transcript_dir=args.transcript_dir
    )
    
    # 转录音频
    print(f"正在转录 '{args.audio}'...")
    transcript, transcript_file = transcriber.transcribe(args.audio)
    
    if transcript:
        print(f"\n转录完成: {transcript}")
        
        if transcript_file:
            print(f"转录文本已保存到: {transcript_file}")
        
        # 如果需要，发送到决策中枢
        if args.send_to_decision:
            send_to_decision_center(transcript)
    else:
        print("转录失败或未检测到语音内容")

if __name__ == "__main__":
    main()