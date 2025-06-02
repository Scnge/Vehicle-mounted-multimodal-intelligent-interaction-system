# /Users/kalami/大三下/软件工程/小组作业/Vehicle-mounted-multimodal-intelligent-interaction-system/SoftwareProject/speech/models.py
from django.db import models

class VoiceCommand(models.Model):
    """语音指令模型"""
    command = models.CharField(max_length=200, verbose_name="指令文本")
    action = models.CharField(max_length=100, verbose_name="执行动作")
    similarity_threshold = models.FloatField(default=0.7, verbose_name="相似度阈值")
    enabled = models.BooleanField(default=True, verbose_name="是否启用")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "语音指令"
        verbose_name_plural = "语音指令"
    
    def __str__(self):
        return self.command

class SpeechRecord(models.Model):
    """语音识别记录"""
    original_text = models.TextField(verbose_name="识别文本")
    matched_command = models.ForeignKey(VoiceCommand, on_delete=models.SET_NULL, null=True, blank=True)
    similarity_score = models.FloatField(default=0.0, verbose_name="匹配度")
    executed = models.BooleanField(default=False, verbose_name="是否执行")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "语音记录"
        verbose_name_plural = "语音记录"