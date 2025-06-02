from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from difflib import SequenceMatcher
from .models import VoiceCommand

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
    # 这里实现具体的动作执行逻辑
    actions = {
        'adjust_temperature': lambda x: {'status': 'success', 'message': f'已调整温度到{x}度'},
        'play_music': lambda x: {'status': 'success', 'message': f'正在播放{x}'},
        'set_car_status': lambda x: {'status': 'success', 'message': f'已将车辆状态设置为{x}'},
        # 添加更多动作处理函数
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
            return JsonResponse({'status': 'error', 'message': '未接收到语音文本'})

        command, similarity = find_best_match(text)
        if not command:
            return JsonResponse({
                'status': 'error',
                'message': '未找到匹配的指令',
                'similarity': similarity
            })

        result = execute_action(command.action)
        result.update({
            'command': command.command,
            'similarity': similarity
        })

        return JsonResponse(result)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'处理指令时出错: {str(e)}'
        })