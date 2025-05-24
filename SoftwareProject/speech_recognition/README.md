
# Whisper 中文语音识别系统

一个基于OpenAI Whisper的中文语音识别系统，支持文件转录和实时麦克风转录，具有保存功能和唤醒词检测。

## 功能特性

- 中文语音转文字转录
- 实时麦克风录音与转录
- 音频文件批量转录
- 录音文件保存选项
- 转录文本保存选项
- 唤醒词检测功能
- 多设备支持（CPU、NVIDIA GPU、Apple Silicon）
- 与智能决策系统集成

## 环境配置

首先，创建一个conda环境并安装必要的依赖：

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

# 安装唤醒词检测库（可选）
pip install pvporcupine

# 安装键盘控制库（Windows/Linux）
pip install pynput
```

## 项目结构

```
whisper_chinese/
├── src/                   # 源代码目录
│   ├── __init__.py        # 使src成为一个包
│   ├── audio_recorder.py  # 音频录制模块
│   ├── transcriber.py     # 语音转录模块
│   ├── wake_word.py       # 唤醒词检测模块
│   └── utils.py           # 工具函数
│
├── bin/                   # 可执行脚本
│   ├── transcribe_file.py # 转录文件的脚本
│   └── transcribe_mic.py  # 实时麦克风转录脚本
│
├── config/                # 配置文件
│   └── default.json       # 默认配置
│
├── data/                  # 数据目录
│   ├── audio/             # 音频文件
│   ├── recordings/        # 保存的录音
│   └── transcripts/       # 保存的转录文本
│
├── models/                # 模型将自动下载到这里
├── README.md              # 项目说明
└── requirements.txt       # 项目依赖
```

## 使用说明

### 实时麦克风转录

```bash
# 激活环境
conda activate whisper_env

# 基本使用（自动选择设备）
python bin/transcribe_mic.py --model medium

# 使用唤醒词（小爱同学风格）
python bin/transcribe_mic.py --model tiny --wake_word "你好小智"

python bin/transcribe_mic.py --use_sr --wake_word "你好小智"
# 保存录音和转录文本
python bin/transcribe_mic.py --model medium --save_audio --save_transcript

# 指定设备
# Apple Silicon GPU (M1/M2/M3)
python bin/transcribe_mic.py --model medium --device mps

# NVIDIA GPU
python bin/transcribe_mic.py --model medium --device cuda

# 强制使用CPU
python bin/transcribe_mic.py --model small --device cpu
```

实时转录参数说明:
- `--model`: 模型大小，可选 tiny, base, small, medium, large
- `--device`: 运行设备，可选 cpu, cuda, mps, auto
- `--wake_word`: 唤醒词，留空则不使用唤醒功能
- `--save_audio`: 是否保存录音文件
- `--audio_dir`: 录音文件保存目录，默认为 data/recordings
- `--save_transcript`: 是否保存转录文本
- `--transcript_dir`: 转录文本保存目录，默认为 data/transcripts

使用键盘控制:
- `r`: 开始录音
- `s`: 停止录音
- `q`: 退出程序

### 转录音频文件

```bash
# 激活环境
conda activate whisper_env

# 转录单个音频文件
python bin/transcribe_file.py --audio data/audio/example.mp3 --model medium

# 保存转录文本
python bin/transcribe_file.py --audio data/audio/example.mp3 --model medium --save_transcript

# 将转录结果发送到决策中枢
python bin/transcribe_file.py --audio data/audio/example.mp3 --model medium --send_to_decision
```

文件转录参数说明:
- `--audio`: 要转录的音频文件路径
- `--model`: 模型大小，同上
- `--device`: 运行设备，同上
- `--save_transcript`: 是否保存转录文本
- `--transcript_dir`: 转录文本保存目录
- `--send_to_decision`: 是否将转录结果发送到决策中枢

## 不同模型大小对比

模型大小取决于您的设备性能和需要的准确率：

- `tiny`: 最小模型，约39M，适合低配置设备，准确率有限
- `base`: 基础模型，约74M，准确率适中
- `small`: 小型模型，约244M，中等准确率和性能
- `medium`: 中型模型，约769M，较高准确率，推荐使用
- `large`: 最大模型，约1.5GB，最高准确率，需要较高配置

对于中文语音识别，建议至少使用`medium`模型以获得良好的识别效果。

## 与智能决策中枢集成

本系统支持将转录文本发送到智能决策中枢，实现语音命令控制。您可以在`src/utils.py`中的`send_to_decision_center`函数中实现与决策系统的通信。

默认情况下，该函数只会打印转录文本，您可以根据实际需求进行修改，例如通过HTTP请求、WebSocket或消息队列等方式发送数据。

## 可能遇到的问题与解决方案

1. **CUDA错误**: 如果您有NVIDIA GPU但遇到CUDA错误，请确保安装了正确版本的PyTorch和CUDA。
   
2. **内存不足**: 如果内存不足，可以尝试使用较小的模型，如`small`或`base`。

3. **麦克风权限问题**: 确保您的系统允许Python访问麦克风。

4. **安装ffmpeg失败**: 如果conda安装ffmpeg失败，可以尝试系统级安装：
   - Ubuntu: `sudo apt-get install ffmpeg`
   - macOS: `brew install ffmpeg`
   - Windows: 下载二进制文件并添加到PATH

5. **唤醒词检测失败**: 确保已安装`pvporcupine`库，并使用支持的唤醒词。

## 自定义开发

如果您需要进一步扩展系统功能，可以修改以下文件：

- `src/audio_recorder.py`: 修改音频录制逻辑
- `src/transcriber.py`: 修改语音转录逻辑
- `src/wake_word.py`: 修改唤醒词检测逻辑
- `src/utils.py`: 修改决策中枢通信逻辑

## 许可证

本项目采用MIT许可证。Whisper模型由OpenAI提供，使用时请遵守相关条款。
