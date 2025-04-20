# Whisper 中文语音识别配置教程

我将为您提供一个完整的教程，使用conda环境配置OpenAI的Whisper模型进行中文语音识别。

## 环境配置

首先，我们需要创建一个conda环境并安装必要的依赖：

```bash
# 创建新的conda环境
conda create -n whisper_env python=3.9
conda activate whisper_env

# 安装PyTorch (具体版本可能需要根据您的CUDA版本调整)
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia

# 安装Whisper
pip install -U openai-whisper

# 安装音频处理依赖
conda install ffmpeg
pip install setuptools-rust
pip install pyaudio
```

## 文件目录结构

以下是建议的项目目录结构：

```
whisper_chinese/
├── audio/                 # 存放音频文件
│   └── example.mp3        # 示例音频文件
├── transcripts/           # 存放转录结果
│   └── example.txt        # 示例转录文件
├── models/                # 模型将自动下载到这里
├── transcribe_file.py     # 转录音频文件的脚本
├── transcribe_mic_fixed.py      # 从麦克风实时转录的脚本
└── requirements.txt       # 项目依赖
```



## 使用说明

### 转录音频文件

```bash
# 激活环境
conda activate whisper_env

# 转录音频文件
python transcribe_file.py --audio audio/example.mp3 --model medium
```

参数说明:
- `--audio`: 要转录的音频文件路径
- `--model`: 模型大小，可选 tiny, base, small, medium, large（越大准确率越高，但需要更多内存）
- `--output_dir`: 转录文本保存目录

### 实时麦克风转录

```bash
# 激活环境
conda activate whisper_env

# 启动实时转录
# 使用Apple Silicon GPU (M1/M2/M3)
python transcribe_mic_fixed.py --model small --device mps

# 自动选择最佳设备
python transcribe_mic_fixed.py --model small --device auto

# 使用NVIDIA GPU
python transcribe_mic_fixed.py --model small --device cuda

# 强制使用CPU
python transcribe_mic_fixed.py --model small --device cpu
```

参数说明:
- `--model`: 模型大小，同上

## 不同模型大小对比

模型大小取决于您的设备性能和需要的准确率：

- `tiny`: 最小模型，约39M，适合低配置设备，准确率有限
- `base`: 基础模型，约74M，准确率适中
- `small`: 小型模型，约244M，中等准确率和性能
- `medium`: 中型模型，约769M，较高准确率，推荐使用
- `large`: 最大模型，约1.5GB，最高准确率，需要较高配置

对于中文语音识别，建议至少使用`medium`模型以获得良好的识别效果。

## 可能遇到的问题与解决方案

1. **CUDA错误**: 如果您有NVIDIA GPU但遇到CUDA错误，请确保安装了正确版本的PyTorch和CUDA。
   
2. **内存不足**: 如果内存不足，可以尝试使用较小的模型，如`small`或`base`。

3. **麦克风权限问题**: 确保您的系统允许Python访问麦克风。

4. **安装ffmpeg失败**: 如果conda安装ffmpeg失败，可以尝试系统级安装：
   - Ubuntu: `sudo apt-get install ffmpeg`
   - macOS: `brew install ffmpeg`
   - Windows: 下载二进制文件并添加到PATH

现在您已经拥有完整的Whisper中文语音识别配置和代码。祝您使用愉快！