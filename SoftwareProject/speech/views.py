# /Users/kalami/大三下/软件工程/小组作业/Vehicle-mounted-multimodal-intelligent-interaction-system/SoftwareProject/speech/views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from difflib import SequenceMatcher
from .models import VoiceCommand, SpeechRecord
from .core.transcriber import WhisperTranscriber
import json

def calculate_similarity(text1, text2):
    """计算两个文本的相似度"""
    return SequenceMatcher(None, text1, text2).ratio()

def find_best_match(text):
    """查找最匹配的指令"""
    commands = VoiceCommand.objects.filter(enabled=True)
    best_match = None
    highest_similarity = 0

    for command in commands:
        similarity = calculate_similarity(text.lower(), command.command.lower())
        if similarity > highest_similarity:
            highest_similarity = similarity
            best_match = command

    if best_match and highest_similarity >= best_match.similarity_threshold:
        return best_match, highest_similarity
    return None, highest_similarity

def execute_action(action):
    """执行指令对应的动作"""
    actions = {
        'adjust_temperature': lambda x: {'status': 'success', 'message': f'已调整温度到{x}度'},
        'play_music': lambda x: {'status': 'success', 'message': f'正在播放{x}'},
        'set_car_status': lambda x: {'status': 'success', 'message': f'已将车辆状态设置为{x}'},
    }
    
    action_name = action.split(':')[0]
    action_params = action.split(':')[1] if ':' in action else None
    
    if action_name in actions:
        return actions[action_name](action_params)
    return {'status': 'error', 'message': '不支持的动作'}

@csrf_exempt
@require_http_methods(["POST"])
def process_voice_command(request):
    """处理语音指令"""
    try:
        text = request.POST.get('text')
        if not text:
            return JsonResponse({'status': 'error', 'message': '缺少文本参数'})
        
        # 查找匹配的指令
        command, similarity = find_best_match(text)
        
        # 记录语音识别结果
        record = SpeechRecord.objects.create(
            original_text=text,
            matched_command=command,
            similarity_score=similarity
        )
        
        if command:
            # 执行动作
            result = execute_action(command.action)
            record.executed = True
            record.save()
            
            return JsonResponse({
                'status': 'success',
                'command': command.command,
                'action': command.action,
                'similarity': similarity,
                'result': result
            })
        else:
            return JsonResponse({
                'status': 'no_match',
                'message': '未找到匹配的指令',
                'similarity': similarity
            })
            
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

def speech_interface(request):
    """语音交互界面"""
    return render(request, 'speech_recognition/recognize.html')

def wake_word_redirect(request):
    """唤醒词检测后的重定向"""
    return render(request, 'speech_recognition/recognize.html')

@csrf_exempt
def process_speech_command(request):
    """处理语音指令"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            text = data.get('text', '').strip()
            
            if not text:
                return JsonResponse({'error': '文本为空'}, status=400)
            
            # 指令匹配逻辑
            action, confidence = match_command(text)
            
            return JsonResponse({
                'text': text,
                'action': action,
                'confidence': confidence,
                'status': 'success'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': '无效的JSON数据'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': '仅支持POST请求'}, status=405)

def match_command(text):
    """匹配语音指令"""
    import re
    text = text.lower().strip()
    
    # 定义指令模式和对应的动作
    command_patterns = [
        # 导航相关
        (r'(导航|去|前往|到).*(家|公司|医院|学校|超市)', '导航到目的地', 0.9),
        (r'(回家|回公司)', '导航回家', 0.95),
        (r'(最近的|附近的).*(加油站|停车场|餐厅|银行)', '搜索附近设施', 0.85),
        
        # 音乐控制
        (r'(播放|放|听).*(音乐|歌曲|歌)', '播放音乐', 0.9),
        (r'(暂停|停止).*(音乐|歌曲)', '暂停音乐', 0.95),
        (r'(下一首|切歌)', '下一首歌', 0.9),
        (r'(上一首|上首歌)', '上一首歌', 0.9),
        (r'(调大|增大|提高).*(音量|声音)', '增大音量', 0.85),
        (r'(调小|减小|降低).*(音量|声音)', '减小音量', 0.85),
        
        # 电话相关
        (r'(打电话|拨打|呼叫)', '拨打电话', 0.9),
        (r'(接电话|接听)', '接听电话', 0.95),
        (r'(挂断|结束通话)', '挂断电话', 0.95),
        
        # 空调控制
        (r'(打开|开启).*(空调|冷气)', '打开空调', 0.9),
        (r'(关闭|关掉).*(空调|冷气)', '关闭空调', 0.9),
        (r'(调高|升高|提高).*(温度)', '调高温度', 0.85),
        (r'(调低|降低|减少).*(温度)', '调低温度', 0.85),
        
        # 车窗控制
        (r'(打开|开启|摇下).*(车窗|窗户)', '打开车窗', 0.9),
        (r'(关闭|关上|摇上).*(车窗|窗户)', '关闭车窗', 0.9),
        
        # 信息查询
        (r'(天气|气温|温度)', '查询天气', 0.85),
        (r'(时间|几点|现在)', '查询时间', 0.9),
        (r'(路况|交通)', '查询路况', 0.85),
        (r'(新闻|资讯)', '播报新闻', 0.8),
        
        # 车辆控制
        (r'(锁车|锁门)', '锁定车辆', 0.95),
        (r'(解锁|开锁)', '解锁车辆', 0.95),
        (r'(启动|发动).*(引擎|发动机)', '启动引擎', 0.9),
        (r'(熄火|关闭引擎)', '关闭引擎', 0.9),
        
        # 通用控制
        (r'(帮助|帮我|怎么)', '显示帮助', 0.7),
        (r'(取消|算了|不用了)', '取消操作', 0.8),
    ]
    
    best_match = None
    best_confidence = 0
    
    for pattern, action, base_confidence in command_patterns:
        if re.search(pattern, text):
            # 计算匹配度（可以根据匹配的完整性调整）
            match_length = len(re.search(pattern, text).group())
            text_length = len(text)
            length_factor = min(match_length / text_length, 1.0)
            
            confidence = base_confidence * (0.7 + 0.3 * length_factor)
            
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = action
    
    if best_match:
        return best_match, best_confidence
    else:
        return '未识别的指令', 0.3