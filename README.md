# Vehicle-mounted-multimodal-intelligent-interaction-system

## 项目介绍
这是一个基于Django框架开发的车载多模态智能交互系统，支持语音识别和手势识别等多种交互方式。


## 环境配置

### 系统要求
- Python 3.9+
- MySQL 5.7+
- CUDA（可选，用于GPU加速）

### 使用Conda配置环境


 创建并激活Conda环境
```bash
# 1. 创建并激活conda环境
conda create -n vehicle_system python=3.9
conda activate vehicle_system

# 2. 安装系统依赖
brew install portaudio ffmpeg pkg-config mysql-connector-c mysql

# 3. 安装PyTorch（建议使用conda安装以获得更好的性能）
conda install pytorch torchvision torchaudio -c pytorch

# 4. 安装其他Python包
pip install -r requirements.txt
```

