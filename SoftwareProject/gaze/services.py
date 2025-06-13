#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gaze/services.py
---------------------------------
L2CS‑Net 视线识别
· predict(img_pil) ── 网页 /gaze/api/ 使用
· run_demo_camera() ── /gaze/start/ 触发本地摄像头窗口（含人脸框+红色箭头+FPS）
   └ 窗口标题为中文：   L2CS‑Net 视线识别  (ESC退出)
"""

import sys, time
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image

# ────────────────────────────
# 1. 让 Python 能 import L2CS_Net
# ────────────────────────────
BASE_DIR  = Path(__file__).resolve().parent.parent
L2CS_PATH = BASE_DIR / "L2CS_Net"
if str(L2CS_PATH) not in sys.path:
    sys.path.insert(0, str(L2CS_PATH))

# ────────────────────────────
# 2. 全局懒加载占位
# ────────────────────────────
_PIPELINE = None           # type: ignore
_DEVICE   = None
_WEIGHTS  = L2CS_PATH / "models" / "L2CSNet_gaze360.pkl"   # ← 换成你的权重

# ────────────────────────────
# 3. 内部：加载 Pipeline
# ────────────────────────────
def _load_pipeline():
    global _PIPELINE, _DEVICE
    import torch
    from l2cs import select_device, Pipeline

    _DEVICE = select_device("cpu", batch_size=1)           # "cuda:0" 可用 GPU
    print(f"[gaze] loading weights from {_WEIGHTS}")
    _PIPELINE = Pipeline(weights=_WEIGHTS,
                         arch="ResNet50",
                         device=_DEVICE)
    print(f"[gaze] Pipeline loaded ({_DEVICE})")

# ────────────────────────────
# 4. 供网页流式调用
# ────────────────────────────
def predict(img_pil: Image.Image) -> Tuple[float, float]:
    global _PIPELINE
    if _PIPELINE is None:
        t0 = time.perf_counter(); _load_pipeline()
        print(f"[gaze] pipeline init {time.perf_counter()-t0:.1f}s")

    import cv2
    img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    result = _PIPELINE.step(img_cv)        # GazeResultContainer | None
    if result is None:
        return 0.0, 0.0

    pitch = float(np.asarray(result.pitch).item())
    yaw   = float(np.asarray(result.yaw).item())
    return pitch, yaw

# ────────────────────────────
# 5. demo 摄像头线程（含中文标题）
# ────────────────────────────
def run_demo_camera():
    """后台线程：摄像头 + 人脸框 + 视线箭头 + FPS + 中文标题"""
    import threading, cv2
    from l2cs import render          # 官方可视化
    import ctypes                    # Win32 API 改标题

    def _worker():
        print("[demo] 🚀 摄像头线程启动")
        WIN_NAME = "L2CS-Net"                         # 初始 ASCII 名
        cv2.namedWindow(WIN_NAME, cv2.WINDOW_NORMAL)

        # —— 把标题改成中文（仅 Windows 生效） ——
        hwnd = ctypes.windll.user32.FindWindowW(None, WIN_NAME)
        if hwnd:
            ctypes.windll.user32.SetWindowTextW(
                hwnd, "视线识别"
            )

        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            print("[demo] ❌ 无法打开摄像头"); return

        while True:
            start_t = time.time()
            ret, frame = cap.read()
            if not ret:
                print("[demo] ❌ 读取帧失败"); break

            global _PIPELINE
            if _PIPELINE is None:
                _load_pipeline()

            frame = render(frame, _PIPELINE.step(frame))   # 箭头+框
            fps = 1.0 / (time.time() - start_t)

            cv2.putText(frame, f"FPS:{fps:.1f}", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
            cv2.imshow(WIN_NAME, frame)
            if cv2.waitKey(1) & 0xFF == 27:                # ESC
                break

        cap.release()
        cv2.destroyAllWindows()
        print("[demo] 🛑 线程结束")

    threading.Thread(target=_worker, daemon=True).start()
