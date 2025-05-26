import os
import sys
import platform
import json

def get_platform_info():
    """获取平台信息"""
    return {
        "system": platform.system(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor()
    }

def is_mac():
    """检查是否为macOS"""
    return platform.system() == 'Darwin'

def load_config(config_file="config/default.json"):
    """加载配置文件"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"配置文件 {config_file} 不存在，将使用默认配置")
        return {}
    except json.JSONDecodeError:
        print(f"配置文件 {config_file} 格式错误，将使用默认配置")
        return {}

def parse_command(text):
    """解析语音指令"""
    # 预定义的指令和对应的操作
    commands = {
        '温度': {
            '升高': lambda x: f'已将温度升高到{x}度',
            '调高': lambda x: f'已将温度升高到{x}度',
            '降低': lambda x: f'已将温度降低到{x}度',
            '调低': lambda x: f'已将温度降低到{x}度',
            '设置': lambda x: f'已将温度设置为{x}度'
        },
        '音乐': {
            '播放': lambda x: f'正在播放{x}',
            '暂停': lambda _: '音乐已暂停',
            '继续': lambda _: '音乐继续播放',
            '停止': lambda _: '音乐已停止',
            '下一首': lambda _: '播放下一首',
            '上一首': lambda _: '播放上一首'
        },
        '车窗': {
            '打开': lambda _: '已打开车窗',
            '关闭': lambda _: '已关闭车窗'
        },
        '空调': {
            '打开': lambda _: '已打开空调',
            '关闭': lambda _: '已关闭空调'
        }
    }

    # 提取数字
    number = None
    for word in text.split():
        if word.isdigit():
            number = int(word)
            break

    # 遍历指令匹配
    for device, actions in commands.items():
        if device in text:
            for action, func in actions.items():
                if action in text:
                    return func(number) if number else func(None)

    return None

def send_to_decision_center(text):
    """将转录文本发送给决策中枢"""
    try:
        # 解析指令
        result = parse_command(text)
        
        if result:
            print(f"✅ {result}")
            return True
        else:
            print(f"❌ 未能识别指令: {text}")
            return False
            
    except Exception as e:
        print(f"❌ 处理指令时出错: {e}")
        return False