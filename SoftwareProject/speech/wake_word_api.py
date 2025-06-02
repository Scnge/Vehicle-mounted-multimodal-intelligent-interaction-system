import os
import time
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

@csrf_exempt
@require_http_methods(["GET"])
def check_wake_word_status(request):
    """检查唤醒词检测状态"""
    try:
        wake_word_flag_path = os.path.join(settings.BASE_DIR, 'wake_word_detected.flag')
        
        if os.path.exists(wake_word_flag_path):
            # 读取标志文件的时间戳
            with open(wake_word_flag_path, 'r') as f:
                timestamp = float(f.read().strip())
            
            # 检查是否是最近5秒内的检测
            current_time = time.time()
            if current_time - timestamp <= 5:
                # 删除标志文件，避免重复触发
                os.remove(wake_word_flag_path)
                return JsonResponse({
                    'wake_word_detected': True,
                    'timestamp': timestamp
                })
            else:
                # 过期的标志文件，删除它
                os.remove(wake_word_flag_path)
                
        return JsonResponse({'wake_word_detected': False})
        
    except Exception as e:
        return JsonResponse({
            'wake_word_detected': False,
            'error': str(e)
        })