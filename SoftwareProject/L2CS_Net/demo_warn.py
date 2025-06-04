#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L2CS-Net 实时视线监测 + 驾驶员偏离告警 Demo
"""
import argparse
import pathlib
import numpy as np
import cv2
import time
import threading
import os

import torch
import torch.backends.cudnn as cudnn

from playsound import playsound       # pip install playsound
from batch_face.face_detection import RetinaFace  # 若用自定义别名环境，无需改动
from l2cs import select_device, Pipeline, render

CWD = pathlib.Path.cwd()

def play_audio(path):
    """非阻塞播放告警音"""
    playsound(path)

def parse_args():
    parser = argparse.ArgumentParser(
        description='L2CS-Net 实时视线监测 + 驾驶员偏离告警')
    parser.add_argument('--device',   type=str, default='cpu',
                        help='运行设备: cpu | cuda:0')
    parser.add_argument('--snapshot', type=str,
                        default=str(CWD / 'models' / 'L2CSNet_gaze360.pkl'),
                        help='模型快照路径 (.pkl)')
    parser.add_argument('--cam',      type=int, default=0,
                        help='摄像头索引')
    parser.add_argument('--yaw_th',   type=float, default=15.0,
                        help='左右偏离阈值 (°)')
    parser.add_argument('--pitch_th', type=float, default=10.0,
                        help='上下偏离阈值 (°)')
    parser.add_argument('--alert_t',  type=int, default=10,
                        help='持续偏离多少秒后报警 (s)')
    parser.add_argument('--audio',    type=str, default='Notice.mp3',
                        help='告警音频文件路径')
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    # 检查告警音频
    if not os.path.isfile(args.audio):
        raise FileNotFoundError(f"找不到告警音频: {args.audio}")

    cudnn.enabled = True
    device = select_device(args.device, batch_size=1)

    # 初始化视线估计管道
    gaze_pipeline = Pipeline(
        weights=pathlib.Path(args.snapshot),
        arch='ResNet50',
        device=device
    )

    # 摄像头初始化（DirectShow 模式）
    cap = cv2.VideoCapture(args.cam, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise IOError(f"无法打开摄像头 {args.cam}")

    alert_start = None
    alert_active = False

    print("Starting driver-monitor demo. Press 'q' to exit.")
    with torch.no_grad():
        while True:
            start_time = time.time()
            ret, frame = cap.read()
            if not ret:
                print("Failed to obtain frame")
                time.sleep(0.1)
                continue

            # 推理
            results = gaze_pipeline.step(frame)
            # 渲染视线箭头
            frame = render(frame, results)

            # 提取多脸场景下最可信的 pitch & yaw
            pitch_arr = results.pitch         # np.ndarray
            yaw_arr   = results.yaw
            scores    = results.scores        # confidence array
            if scores is None or len(scores) == 0:
                # 未检测到人脸，跳过偏离检测
                cv2.imshow('Demo', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue
            # 选最大置信度的索引
            idx = int(np.argmax(scores))
            pitch = float(pitch_arr[idx])
            yaw   = float(yaw_arr[idx])

            # 偏离判断
            off_road = abs(yaw) > args.yaw_th or abs(pitch) > args.pitch_th
            if off_road and alert_start is None:
                alert_start = time.time()
            if not off_road:
                alert_start = None
                alert_active = False
            if alert_start and not alert_active:
                if time.time() - alert_start >= args.alert_t:
                    threading.Thread(target=play_audio, args=(args.audio,), daemon=True).start()
                    alert_active = True

            # 叠加FPS
            fps = 1.0 / max((time.time() - start_time), 1e-8)
            cv2.putText(frame, f'FPS: {fps:.1f}', (10, 20),
                        cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (0, 255, 0), 1,
                        cv2.LINE_AA)
            # 叠加警告文字
            if alert_active:
                cv2.putText(frame, '警告，请目视前方', (50, 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3,
                            cv2.LINE_AA)

            cv2.imshow('Demo', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()