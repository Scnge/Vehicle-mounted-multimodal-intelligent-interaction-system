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

def send_to_decision_center(text):
    """将转录文本发送给决策中枢"""
    try:
        # 这里可以根据实际情况实现与决策中枢的通信
        print(f"发送文本到决策中枢: {text}")
        
        # 示例：通过HTTP发送
        # import requests
        # response = requests.post("http://localhost:8000/decision", json={"text": text})
        # print(f"决策中枢响应: {response.json()}")
        
        return True
    except Exception as e:
        print(f"发送到决策中枢时出错: {e}")
        return False