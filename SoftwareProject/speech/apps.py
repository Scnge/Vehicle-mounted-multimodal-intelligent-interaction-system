#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
语音识别应用配置
该模块负责初始化语音识别服务，并在应用启动时自动加载。
"""

# speech/apps.py
from django.apps import AppConfig
import threading
import time

class SpeechConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'speech'
    
    def ready(self):
        """应用准备就绪时启动语音识别服务"""
        # 延迟启动，避免在迁移等操作时启动
        def delayed_start():
            time.sleep(3)
            try:
                from .services import SpeechRecognitionService
                service = SpeechRecognitionService()
                service.start()
            except Exception as e:
                print(f"语音识别服务启动失败: {e}")
        
        # 在后台线程中启动
        thread = threading.Thread(target=delayed_start, daemon=True)
        thread.start()