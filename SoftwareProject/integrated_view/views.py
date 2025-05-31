from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import subprocess
import sys
import os
import threading
import json
from django.shortcuts import render

def integrated_home(request):
    return render(request, 'integrated/welcome.html')  # 使用你准备的模板路径


@csrf_exempt
def launch_demo(request):
    """启动integrated_demo程序"""
    if request.method == 'POST':
        try:
            # 获取integrated_demo.py的路径
            demo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                   'integrated_demo', 'integrated_demo.py')
            
            # 使用线程启动程序，避免阻塞Django
            def run_demo():
                subprocess.Popen([sys.executable, demo_path], 
                               cwd=os.path.dirname(demo_path))
            
            thread = threading.Thread(target=run_demo)
            thread.daemon = True
            thread.start()
            
            return JsonResponse({'status': 'success', 'message': '程序已启动'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': '无效的请求方法'})

@csrf_exempt
def get_detection_data(request):
    """获取检测数据用于前端显示"""
    try:
        data_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                'integrated_demo', 'frontend_data', 'detection_data.json')
        
        if os.path.exists(data_file):
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return JsonResponse(data)
        else:
            return JsonResponse({'status': 'error', 'message': '数据文件不存在'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}) 
    
