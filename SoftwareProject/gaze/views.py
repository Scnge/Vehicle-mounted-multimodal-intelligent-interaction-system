#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
视线追踪 API
该模块提供一个 API 接口，用于处理视线追踪请求。
该接口接收一个包含图像数据的 POST 请求，并返回预测的 pitch 和 yaw 值。
"""

# gaze/views.py
import json, base64, io, traceback, time
from PIL import Image
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
import sys
@csrf_exempt
def gaze_api(request):
    print("\n=== gaze_api called", time.strftime('%H:%M:%S'), "===")

    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    try:
        data = json.loads(request.body)
        img_b64 = data["image"].split(",")[-1]
        img = Image.open(io.BytesIO(base64.b64decode(img_b64)))
    except Exception as e:
        print("SERVER ERROR:", e)           # 用 print 而非 traceback
        import traceback, sys
        traceback.print_exc(file=sys.stdout)   # 重定向到 stdout
        sys.stdout.flush()
        return JsonResponse({"error": "server"}, status=500)

    try:
        from .services import predict
        pitch, yaw = predict(img)
        print("pitch, yaw ->", pitch, yaw)
        return JsonResponse({
            "pitch": float(pitch),
            "yaw":   float(yaw)
        })
        #return JsonResponse({"pitch": pitch, "yaw": yaw})
    except Exception:
        traceback.print_exc(file=sys.stdout)          # ⬅️ 关键：把完整栈打出来
        sys.stdout.flush()  
        return JsonResponse({"error": "server err"}, status=500)

def gaze_live(request):
    return render(request, "gaze/gaze_live.html")

from django.shortcuts import render
from django.http import HttpResponse

def start_demo(request):
    from .services import run_demo_camera
    run_demo_camera()
    return HttpResponse(
        "已启动摄像头窗口，"
        "按 ESC 可关闭窗口."
    )

