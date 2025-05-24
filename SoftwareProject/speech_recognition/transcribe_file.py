import os
import whisper
import argparse
import time

def main():
    parser = argparse.ArgumentParser(description="使用Whisper转录音频文件为中文文本")
    parser.add_argument("--audio", type=str, required=True, help="音频文件路径")
    parser.add_argument("--model", type=str, default="medium", 
                        choices=["tiny", "base", "small", "medium", "large"], 
                        help="Whisper模型大小")
    parser.add_argument("--output_dir", type=str, default="transcripts", 
                        help="转录输出目录")
    
    args = parser.parse_args()
    
    # 确保输出目录存在
    os.makedirs(args.output_dir, exist_ok=True)
    
    # 加载模型(第一次运行会自动下载预训练模型)
    print(f"加载 Whisper {args.model} 模型...")
    model = whisper.load_model(args.model)
    
    # 转录音频文件
    print(f"转录文件: {args.audio}")
    start_time = time.time()
    
    # 设置选项以优化中文识别
    result = model.transcribe(
        args.audio,
        language="zh",  # 指定语言为中文
        task="transcribe",
        verbose=True
    )
    
    # 计算处理时间
    process_time = time.time() - start_time
    audio_path = os.path.basename(args.audio)
    filename = os.path.splitext(audio_path)[0]
    
    # 保存转录文本
    output_path = os.path.join(args.output_dir, f"{filename}.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result["text"])
    
    print(f"转录完成! 用时: {process_time:.2f} 秒")
    print(f"结果已保存至: {output_path}")
    print(f"转录文本: {result['text']}")

if __name__ == "__main__":
    main()