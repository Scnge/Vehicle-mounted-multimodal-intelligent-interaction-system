#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
集成演示：同时进行手势识别和人脸疲劳检测
"""

import os
import sys
import threading
import datetime
import time
import cv2
import numpy as np
import dlib
import imutils
from playsound import playsound
import platform
import winsound  # Add winsound for more reliable Windows audio playback
from pydub import AudioSegment  # Add pydub for MP3 to WAV conversion
import tempfile  # For temporary WAV files
from imutils import face_utils
from scipy.spatial import distance as dist
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QImage, QPixmap, QTextCursor
from PyQt5.QtWidgets import QApplication, QMainWindow, QGraphicsScene, QMessageBox, QDesktopWidget
import logging
import json

# 创建一个自定义的JSON编码器来处理NumPy数据类型
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

# 确保可以导入两个项目的模块
sys.path.append(os.path.join(os.path.dirname(__file__), 'dynamic_gestures'))

# 导入dynamic_gestures项目的组件
from dynamic_gestures.onnx_models import HandDetection, HandClassification
from dynamic_gestures.main_controller import MainController
from dynamic_gestures.utils.enums import targets as gesture_targets
from dynamic_gestures.utils.drawer import Drawer as HandDrawer

# 导入VisionGuard项目的组件
# 这里我们直接从combined.py中复制相关类和函数

# 系统平台检测
system = platform.system()
if system != "Windows":
    import vlc

print("正在初始化集成演示系统...")
print("请等待界面启动...")

# 设置日志记录
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 创建日志记录器并设置日志级别
# 以当前日期命名日志文件
log_filename = os.path.join(log_dir, f"detection_log_{datetime.datetime.now().strftime('%Y%m%d')}.log")
detection_logger = logging.getLogger('detection')
detection_logger.setLevel(logging.INFO)

# 创建文件处理器
file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.setLevel(logging.INFO)

# 创建格式化器
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# 添加处理器到记录器
detection_logger.addHandler(file_handler)

# 记录系统启动信息
detection_logger.info("系统启动")

# 点头/摇头检测参数和光流法跟踪配置
lk_params = dict(winSize=(35, 35), maxLevel=3,
                 criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03))
NOD_THRESHOLD = 35        # 点头垂直位移阈值 (增加阈值减少误检测)
SHAKE_THRESHOLD = 10      # 摇头水平位移阈值
DIRECTION_CHANGES = 2     # 摇头方向变换次数阈值
DOMINANCE_RATIO = 2.0     # 主导方向比例阈值 (增加以要求更明确的垂直运动)
TRACKING_FRAMES = 15      # 光流轨迹帧数窗口
MIN_MOVE = 2              # 判定有效移动的最小像素
DISPLAY_DURATION = 45     # 检测到动作后文本显示持续帧数

def get_coords(p):
    """提取光流跟踪点的坐标"""
    try:
        return int(p[0][0][0]), int(p[0][0][1])
    except:
        return int(p[0][0]), int(p[0][1])

class GestureDetector:
    """手势（点头/摇头）检测器，维护光流跟踪点和运动分析"""
    def __init__(self):
        self.track_points = []               # 光流跟踪点历史
        self.direction_history = []          # 水平运动方向历史（用于判断摇头）
        self.gesture_status = {"nod": 0, "shake": 0}  # 动作状态计数，用于控制显示
        self.face_center = None              # 当前跟踪的人脸中心点
        self.lost_counter = 0               # 连续跟踪丢失计数
        self.debug_info = {}                # 调试信息
        self.last_gesture_time = 0          # 上次检测到手势的时间
        self.cooldown_period = 1.5          # 手势检测冷却期（秒）
        self.ready_for_detection = True     # 是否已准备好检测
        self.wait_after_detection = False   # 检测到点头摇头后的等待标志
        self.wait_until_time = 0            # 等待结束的时间点

    def update_tracking(self, new_point):
        """更新光流跟踪点位置历史"""
        self.track_points.append(new_point)
        if len(self.track_points) > TRACKING_FRAMES:
            self.track_points.pop(0)
        if len(self.track_points) >= 2:
            prev = self.track_points[-2]
            curr = self.track_points[-1]
            dx = curr[0][0][0] - prev[0][0][0]
            # 如果水平移动超过最小阈值，则记录方向（1=右移，-1=左移）
            if abs(dx) > MIN_MOVE:
                direction = 1 if dx > 0 else -1
                self.direction_history.append(direction)
                if len(self.direction_history) > 20:
                    self.direction_history = self.direction_history[-20:]

    def analyze_motion(self):
        """分析累计的轨迹位移，判断是否构成点头或摇头动作"""
        # 检查是否在冷却期内
        current_time = time.time()
        if current_time - self.last_gesture_time < self.cooldown_period:
            self.ready_for_detection = False
            return None
        else:
            self.ready_for_detection = True
            
        # 需要至少2个点才能计算运动
        if len(self.track_points) < 5:  # 增加所需最小点数
            return None
            
        start_point = self.track_points[0]
        end_point = self.track_points[-1]
        total_x = end_point[0][0][0] - start_point[0][0][0]
        total_y = end_point[0][0][1] - start_point[0][0][1]
        
        # 计算整体位移量
        total_displacement = np.sqrt(total_x**2 + total_y**2)
        
        # 保存调试信息
        self.debug_info = {
            'total_x': float(total_x),
            'total_y': float(total_y),
            'abs_x': float(abs(total_x)),
            'abs_y': float(abs(total_y)),
            'track_points': len(self.track_points),
            'dir_history': len(self.direction_history),
            'total_disp': float(total_displacement)
        }
        
        # 位移不足最小运动量，不判定为任何动作
        min_motion = max(NOD_THRESHOLD, SHAKE_THRESHOLD) * 0.6
        if abs(total_x) + abs(total_y) < min_motion:
            return None
            
        # 计算水平/垂直位移占比
        sum_xy = abs(total_x) + abs(total_y)
        x_ratio = abs(total_x) / sum_xy if sum_xy != 0 else 0
        y_ratio = abs(total_y) / sum_xy if sum_xy != 0 else 0
        is_x_dominant = x_ratio > (y_ratio * DOMINANCE_RATIO)
        is_y_dominant = y_ratio > (x_ratio * DOMINANCE_RATIO)
        
        # 过滤微小动作，避免轻微晃动导致的误判断
        if total_displacement < NOD_THRESHOLD * 0.8:
            return None
        
        # 判断点头：垂直方向位移占主导且超过阈值
        if is_y_dominant and abs(total_y) > NOD_THRESHOLD:
            # 检查Y方向运动是否足够明显
            if abs(total_y) > total_displacement * 0.7:
                self.last_gesture_time = current_time
                return "nod"
            
        # 判断摇头：水平方向位移占主导且超过阈值，且累计方向变换次数达到要求
        if is_x_dominant and abs(total_x) > SHAKE_THRESHOLD:
            dir_changes = sum(1 for i in range(1, len(self.direction_history))
                              if self.direction_history[i] != self.direction_history[i-1])
            if dir_changes >= DIRECTION_CHANGES:
                self.last_gesture_time = current_time
                return "shake"
                
        return None

    def reset_counters(self, detected_gesture):
        """检测到动作后重置计数器，触发显示计数"""
        # 保留最后一个跟踪点，方便继续跟踪
        last_point = None
        if self.track_points:
            last_point = self.track_points[-1].copy()
            
        if detected_gesture == "nod":
            self.gesture_status["nod"] = DISPLAY_DURATION
            self.direction_history = []  # 点头时清空方向变化历史
            self.track_points = []  # 重置跟踪点
        elif detected_gesture == "shake":
            self.gesture_status["shake"] = DISPLAY_DURATION
            self.direction_history = []  # 摇头后清空方向历史
            self.track_points = []  # 重置跟踪点
            
        # 设置2秒的等待期，在此期间不进行面部检测
        self.wait_after_detection = True
        self.wait_until_time = time.time() + 2.0  # 当前时间加2秒
            
        # 如果有保存的跟踪点，将其作为新起点
        if last_point is not None:
            self.track_points = [last_point]

class IntegratedUI(object):
    def __init__(self, MainWindow):
        self.qmessagebox = QMessageBox()
        MainWindow.setObjectName("MainWindow")
        # 居中窗口并设置初始大小
        self.desktop = QApplication.desktop()
        MainWindow.resize(1200, 800)
        screen = QDesktopWidget().screenGeometry()
        size = MainWindow.geometry()
        MainWindow.move((screen.width() - size.width()) // 2,
                        (screen.height() - size.height()) // 2)
        
        # 主布局设置
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.mainLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        
        # 创建选项卡控件
        self.tabWidget = QtWidgets.QTabWidget(self.centralwidget)
        
        # 只保留第一个选项卡：集成视图
        self.tab_integrated = QtWidgets.QWidget()
        self.tab_integrated_layout = QtWidgets.QHBoxLayout(self.tab_integrated)
        
        # 控制面板区域
        self.controlPanel = QtWidgets.QGroupBox("控制面板")
        self.controlPanel_layout = QtWidgets.QVBoxLayout(self.controlPanel)
        
        # 开始/停止按钮
        self.startButton = QtWidgets.QPushButton("开始检测")
        self.stopButton = QtWidgets.QPushButton("暂停")
        self.exportLogButton = QtWidgets.QPushButton("导出日志")
        self.saveFrontendDataButton = QtWidgets.QPushButton("保存前端数据")
        self.controlPanel_layout.addWidget(self.startButton)
        self.controlPanel_layout.addWidget(self.stopButton)
        self.controlPanel_layout.addWidget(self.exportLogButton)
        self.controlPanel_layout.addWidget(self.saveFrontendDataButton)
        
        # 功能选择区域
        self.featureGroup = QtWidgets.QGroupBox("功能选择")
        self.featureGroup_layout = QtWidgets.QVBoxLayout(self.featureGroup)
        
        # 人脸检测选项
        self.face_group = QtWidgets.QGroupBox("人脸检测")
        self.face_layout = QtWidgets.QVBoxLayout(self.face_group)
        self.checkBox_nod = QtWidgets.QCheckBox("点头检测")
        self.checkBox_shake = QtWidgets.QCheckBox("摇头检测")
        # 移除打哈欠检测选项，因为它与疲劳检测有重复
        self.checkBox_yawn = QtWidgets.QCheckBox("打哈欠检测")  # 创建但不添加到界面
        self.checkBox_blink = QtWidgets.QCheckBox("闭眼检测")
        self.checkBox_fatigue = QtWidgets.QCheckBox("疲劳检测")
        self.face_layout.addWidget(self.checkBox_nod)
        self.face_layout.addWidget(self.checkBox_shake)
        # 不再添加打哈欠检测选项
        # self.face_layout.addWidget(self.checkBox_yawn)
        self.face_layout.addWidget(self.checkBox_blink)
        self.face_layout.addWidget(self.checkBox_fatigue)
        
        # 点头检测灵敏度设置
        self.nodSensitivityLayout = QtWidgets.QHBoxLayout()
        self.nodSensitivityLabel = QtWidgets.QLabel("点头灵敏度:")
        self.nodSensitivitySlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.nodSensitivitySlider.setMinimum(20)  # 最小阈值
        self.nodSensitivitySlider.setMaximum(50)  # 最大阈值
        self.nodSensitivitySlider.setValue(NOD_THRESHOLD)  # 当前值
        self.nodSensitivitySlider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.nodSensitivitySlider.setTickInterval(5)
        self.nodSensitivityValueLabel = QtWidgets.QLabel(f"{NOD_THRESHOLD}")
        self.nodSensitivityLayout.addWidget(self.nodSensitivityLabel)
        self.nodSensitivityLayout.addWidget(self.nodSensitivitySlider)
        self.nodSensitivityLayout.addWidget(self.nodSensitivityValueLabel)
        self.face_layout.addLayout(self.nodSensitivityLayout)
        
        # 手势检测选项
        self.hand_group = QtWidgets.QGroupBox("手势检测")
        self.hand_layout = QtWidgets.QVBoxLayout(self.hand_group)
        self.checkBox_hand = QtWidgets.QCheckBox("启用手势检测")
        self.checkBox_hand_debug = QtWidgets.QCheckBox("显示手势调试信息")
        self.hand_layout.addWidget(self.checkBox_hand)
        self.hand_layout.addWidget(self.checkBox_hand_debug)
        
        # 手势保持时间设置
        self.holdTimeLayout = QtWidgets.QHBoxLayout()
        self.holdTimeLabel = QtWidgets.QLabel("手势保持时间 (秒):")
        self.holdTimeSlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.holdTimeSlider.setMinimum(1)
        self.holdTimeSlider.setMaximum(50)  # 0.1秒到5秒
        self.holdTimeSlider.setValue(10)  # 默认1秒
        self.holdTimeSlider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.holdTimeSlider.setTickInterval(5)
        self.holdTimeValueLabel = QtWidgets.QLabel("1.0")
        self.holdTimeLayout.addWidget(self.holdTimeLabel)
        self.holdTimeLayout.addWidget(self.holdTimeSlider)
        self.holdTimeLayout.addWidget(self.holdTimeValueLabel)
        self.hand_layout.addLayout(self.holdTimeLayout)
        
        # 添加到功能选择区域
        self.featureGroup_layout.addWidget(self.face_group)
        self.featureGroup_layout.addWidget(self.hand_group)
        
        # 状态输出面板
        self.logGroup = QtWidgets.QGroupBox("状态输出")
        self.logGroup_layout = QtWidgets.QVBoxLayout(self.logGroup)
        self.textBrowser = QtWidgets.QTextBrowser()
        self.logGroup_layout.addWidget(self.textBrowser)
        
        # 添加控件到控制面板
        self.controlPanel_layout.addWidget(self.featureGroup)
        self.controlPanel_layout.addWidget(self.logGroup)
        
        # 视频显示区域
        self.videoDisplay = QtWidgets.QLabel()
        self.videoDisplay.setMinimumSize(640, 480)
        self.videoDisplay.setAlignment(QtCore.Qt.AlignCenter)
        self.videoDisplay.setStyleSheet("border: 1px solid #CCCCCC;")
        
        # 将控件添加到集成视图
        self.tab_integrated_layout.addWidget(self.controlPanel, 1)
        self.tab_integrated_layout.addWidget(self.videoDisplay, 2)
        
        # 只添加集成视图选项卡
        self.tabWidget.addTab(self.tab_integrated, "集成视图")
        
        # 添加选项卡控件到主布局
        self.mainLayout.addWidget(self.tabWidget)
        
        # 设置中央部件
        MainWindow.setCentralWidget(self.centralwidget)
        
        # 菜单栏和状态栏
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1200, 26))
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        MainWindow.setStatusBar(self.statusbar)
        
        # 设置默认值
        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)
        
        # 初始化摄像头变量和控制标志
        self.cap = None
        self.CAMERA_STYLE = False
        
        # 设置样式
        self.setStyles()
        
        # 初始化人脸检测相关参数
        self.init_face_detection_params()
        
        # 初始化手势检测相关参数
        self.init_hand_detection_params()
        
        # 性能优化选项
        self.performanceGroup = QtWidgets.QGroupBox("性能优化")
        self.performanceLayout = QtWidgets.QVBoxLayout(self.performanceGroup)
        
        # 交替检测选项
        self.checkBox_alternating = QtWidgets.QCheckBox("使用交替检测模式(推荐)")
        self.checkBox_alternating.setChecked(True)
        self.checkBox_alternating.setToolTip("启用此选项可降低CPU使用率，防止程序卡死")
        self.performanceLayout.addWidget(self.checkBox_alternating)
        
        # 人脸框显示持续帧数控制
        self.faceBoxLayout = QtWidgets.QHBoxLayout()
        self.faceBoxLabel = QtWidgets.QLabel("人脸框持续帧数:")
        self.faceBoxSpinner = QtWidgets.QSpinBox()
        self.faceBoxSpinner.setMinimum(1)
        self.faceBoxSpinner.setMaximum(20)
        self.faceBoxSpinner.setValue(5)  # 默认持续5帧
        self.faceBoxSpinner.setToolTip("设置人脸框在交替检测模式下的持续显示帧数，值越大越稳定但可能影响性能")
        self.faceBoxLayout.addWidget(self.faceBoxLabel)
        self.faceBoxLayout.addWidget(self.faceBoxSpinner)
        self.performanceLayout.addLayout(self.faceBoxLayout)
        
        # 帧率控制
        self.frameRateLayout = QtWidgets.QHBoxLayout()
        self.frameRateLabel = QtWidgets.QLabel("处理帧率:")
        self.frameRateSpinner = QtWidgets.QSpinBox()
        self.frameRateSpinner.setMinimum(1)
        self.frameRateSpinner.setMaximum(30)
        self.frameRateSpinner.setValue(2)  # 默认每2帧处理一次
        self.frameRateLayout.addWidget(self.frameRateLabel)
        self.frameRateLayout.addWidget(self.frameRateSpinner)
        self.performanceLayout.addLayout(self.frameRateLayout)
        
        # 录制选项
        self.recordingLayout = QtWidgets.QHBoxLayout()
        self.checkBox_recording = QtWidgets.QCheckBox("启用录制")
        self.checkBox_recording.setToolTip("启用此选项将录制带有检测标记的视频")
        self.recordButton = QtWidgets.QPushButton("开始录制")
        self.recordButton.setEnabled(False)
        self.recordingLayout.addWidget(self.checkBox_recording)
        self.recordingLayout.addWidget(self.recordButton)
        self.performanceLayout.addLayout(self.recordingLayout)
        
        # 添加性能优化组到控制面板
        self.controlPanel_layout.addWidget(self.performanceGroup)
        
        # 连接信号在connectSignals函数中统一处理，这里不需要重复连接
        # self.checkBox_alternating.stateChanged.connect(self.toggle_alternating_mode)
        # self.checkBox_recording.stateChanged.connect(self.toggle_recording_enabled)
        # self.recordButton.clicked.connect(self.toggle_recording)
        # self.holdTimeSlider.valueChanged.connect(self.update_hold_time)
        # self.nodSensitivitySlider.valueChanged.connect(self.update_nod_sensitivity)
        # self.exportLogButton.clicked.connect(self.export_logs)
        
        # 所有UI组件创建完毕后，才连接信号
        self.connectSignals()

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "手势识别和疲劳检测系统"))
        # 默认全部选中
        self.checkBox_nod.setChecked(True)
        self.checkBox_shake.setChecked(True)
        self.checkBox_yawn.setChecked(True)  # 虽然不显示但默认仍然启用打哈欠检测，因为它是疲劳检测的一部分
        self.checkBox_blink.setChecked(True)
        self.checkBox_fatigue.setChecked(True)
        self.checkBox_hand.setChecked(True)
        self.checkBox_hand_debug.setChecked(True)

    def connectSignals(self):
        # 绑定按钮事件
        self.startButton.clicked.connect(self.start_camera)
        self.stopButton.clicked.connect(self.stop_camera)
        self.nodSensitivitySlider.valueChanged.connect(self.update_nod_sensitivity)
        self.holdTimeSlider.valueChanged.connect(self.update_hold_time)
        self.exportLogButton.clicked.connect(self.export_logs)
        self.checkBox_alternating.stateChanged.connect(self.toggle_alternating_mode)
        self.checkBox_recording.stateChanged.connect(self.toggle_recording_enabled)
        self.recordButton.clicked.connect(self.toggle_recording)
        self.saveFrontendDataButton.clicked.connect(self.save_frontend_data)
        self.faceBoxSpinner.valueChanged.connect(self.update_face_box_frames)
        
    def setStyles(self):
        # 设置现代化样式
        self.centralwidget.setStyleSheet("font: 10pt 'Microsoft YaHei'; background-color: #F5F5F5;")
        self.startButton.setStyleSheet("background-color: #4CAF50; color: white; font: 9pt 'Microsoft YaHei'; padding: 5px 10px; border: none; border-radius: 5px;")
        self.stopButton.setStyleSheet("background-color: #FFA500; color: white; font: 9pt 'Microsoft YaHei'; padding: 5px 10px; border: none; border-radius: 5px;")
        self.exportLogButton.setStyleSheet("background-color: #2196F3; color: white; font: 9pt 'Microsoft YaHei'; padding: 5px 10px; border: none; border-radius: 5px;")
        self.saveFrontendDataButton.setStyleSheet("background-color: #9C27B0; color: white; font: 9pt 'Microsoft YaHei'; padding: 5px 10px; border: none; border-radius: 5px;")
        self.textBrowser.setStyleSheet("background-color: #FFFFFF; font: 9pt 'Microsoft YaHei';")
        
        group_style = "QGroupBox { font: bold 10pt 'Microsoft YaHei'; border: 1px solid #CCCCCC; border-radius: 5px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; top: 5px; }"
        self.controlPanel.setStyleSheet(group_style)
        self.featureGroup.setStyleSheet(group_style)
        self.face_group.setStyleSheet(group_style)
        self.hand_group.setStyleSheet(group_style)
        self.logGroup.setStyleSheet(group_style)

    def save_frontend_data(self):
        """手动保存当前前端数据并输出摘要"""
        try:
            self.frontend_data['timestamp'] = datetime.datetime.now().isoformat()
            self.frontend_data['manual_save'] = True
            self.update_frontend_data()
            
            # 创建专用的前端数据快照
            snapshot_file = os.path.join(self.frontend_data_dir, f"snapshot_{int(time.time())}.json")
            with open(snapshot_file, 'w', encoding='utf-8') as f:
                json.dump(self.frontend_data, f, indent=4, ensure_ascii=False, cls=NumpyEncoder)
                
            # 打印数据摘要
            event_count = len(self.frontend_data['last_events'])
            self.log_message(f"前端数据已保存！当前有 {event_count} 个事件记录，持续累积中。")
            self.log_message(f"文件位置: {self.frontend_data_file} 和 {snapshot_file}")
            
            # 显示当前检测状态
            status_info = []
            if self.frontend_data['face_detected']:
                status_info.append("人脸已检测")
            if self.frontend_data['hand_detected']:
                status_info.append("手势已检测")
            status_info.append(f"疲劳度: {self.frontend_data['fatigue_level']}%")
            
            self.log_message(f"当前状态: {', '.join(status_info)}")
            
        except Exception as e:
            self.log_message(f"保存前端数据时出错: {str(e)}")

    def export_logs(self):
        """导出日志到CSV文件"""
        try:
            # 日志导出路径
            export_dir = "exported_logs"
            if not os.path.exists(export_dir):
                os.makedirs(export_dir)
                
            # 生成导出文件名
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            export_file = os.path.join(export_dir, f"detection_log_export_{timestamp}.csv")
            
            # 从日志文件中提取数据
            detection_data = []
            
            # 检查日志文件是否存在
            if not os.path.exists(log_filename):
                self.log_message(f"找不到日志文件: {log_filename}")
                return
                
            # 读取日志文件
            with open(log_filename, 'r', encoding='utf-8') as f:
                for line in f:
                    # 尝试提取JSON数据
                    try:
                        # 跳过非JSON行
                        if ' - INFO - {' not in line:
                            continue
                            
                        # 提取JSON部分
                        json_part = line.split(' - INFO - ', 1)[1]
                        # 使用自定义解析器确保所有数据类型正确处理
                        log_entry = json.loads(json_part)
                        
                        # 添加基本字段
                        entry = {
                            'timestamp': log_entry.get('timestamp', ''),
                            'event_type': log_entry.get('event_type', ''),
                        }
                        
                        # 添加详细信息
                        details = log_entry.get('details', {})
                        for key, value in details.items():
                            if isinstance(value, (dict, list)):
                                entry[key] = json.dumps(value)
                            else:
                                entry[key] = value
                                
                        detection_data.append(entry)
                    except Exception as e:
                        print(f"解析日志行时出错: {str(e)}")
                        continue
            
            # 导出为CSV
            if not detection_data:
                self.log_message("日志中没有检测到有效数据")
                return
                
            # 获取所有可能的列名
            all_keys = set()
            for entry in detection_data:
                all_keys.update(entry.keys())
                
            # 将数据写入CSV
            with open(export_file, 'w', encoding='utf-8', newline='') as f:
                import csv
                writer = csv.DictWriter(f, fieldnames=sorted(list(all_keys)))
                writer.writeheader()
                writer.writerows(detection_data)
                
            self.log_message(f"日志已成功导出到: {export_file}")
            detection_logger.info(f"日志导出: {export_file}")
            
        except Exception as e:
            self.log_message(f"导出日志时出错: {str(e)}")
            detection_logger.error(f"导出日志失败: {str(e)}")

    def init_face_detection_params(self):
        """初始化人脸检测相关参数"""
        # 面部特征索引点
        self.lStart, self.lEnd = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
        self.rStart, self.rEnd = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]
        self.mStart, self.mEnd = face_utils.FACIAL_LANDMARKS_IDXS["mouth"]
        
        # 疲劳检测参数
        self.EYE_AR_THRESH = 0.24  # 眼睛长宽比阈值
        self.AR_CONSEC_FRAMES = 60  # 闭眼判定连续帧数阈值
        self.MAR_THRESH = 0.5  # 打哈欠嘴部长宽比阈值（从0.6降低到0.5，更容易检测）
        self.MOUTH_AR_CONSEC_FRAMES = 15  # 打哈欠连续帧数阈值（从30降低到15）
        
        # 计数器
        self.COUNTER = 0  # 闭眼计数器
        self.mCOUNTER = 0  # 打哈欠计数器
        self.TOTAL = 0  # 闭眼总次数
        self.mTOTAL = 0  # 打哈欠总次数
        self.oCOUNTER = 0  # 脱离范围计数器
        
        # 状态标志
        self.shutEye = False
        self.ifYawming = False
        self.ifTired = False
        self.ifNoFace = False
        
        # 检测器
        self.detector = None
        self.predictor = None
        
        # 手势检测器
        self.gesture_detector = None
        
        # 前一帧灰度图
        self.prev_gray = None
        
        # 哈欠时间记录
        self.timeOfTheLastOfYawns = datetime.datetime(2022, 12, 31)
        self.timeOfTheFirstOfYawns = datetime.datetime(2022, 12, 31)
        
        # 疲劳判断参数
        self.Number_Of_Yawns_Judged_As_Fatigue = 4  # 判断为疲劳的哈欠次数
        self.NOYJAF_Time = 180  # 判断疲劳的时间窗口(秒)
        
        # 性能优化标志
        self.use_alternating_detection = True  # 是否使用交替检测模式
        
        # 录制相关参数
        self.is_recording = False
        self.video_writer = None
        self.recording_start_time = None
        
        # 添加人脸框持久显示参数
        self.last_face_box = None
        self.face_box_valid_frames = 5  # 人脸框保持显示的帧数
        
        # 前端数据交互相关参数
        self.frontend_data_dir = "frontend_data"
        if not os.path.exists(self.frontend_data_dir):
            os.makedirs(self.frontend_data_dir)
        self.frontend_data_file = os.path.join(self.frontend_data_dir, "detection_data.json")
        
        # 尝试加载已有的前端数据，如果不存在则创建新的
        try:
            if os.path.exists(self.frontend_data_file):
                with open(self.frontend_data_file, 'r', encoding='utf-8') as f:
                    self.frontend_data = json.load(f)
                    # 更新当前时间戳，但保留历史事件
                    self.frontend_data['timestamp'] = datetime.datetime.now().isoformat()
                    self.frontend_data['system_status'] = "已加载历史数据"
                    self.log_message(f"已加载历史前端数据，包含 {len(self.frontend_data.get('last_events', []))} 个历史事件")
            else:
                # 文件不存在，创建新的数据结构
                self.frontend_data = {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "face_detected": False,
                    "hand_detected": False,
                    "face_box": None,
                    "last_events": [],  # 事件记录，不限制数量
                    "fatigue_level": 0,  # 0-100的疲劳程度
                    "ear": 0,  # 眼睛长宽比
                    "mar": 0,  # 嘴部长宽比
                    "current_gesture": None,  # 当前检测到的手势
                    "system_status": "初始化"
                }
                self.update_frontend_data()  # 初始化前端数据文件
        except Exception as e:
            self.log_message(f"加载前端数据时出错: {str(e)}，将创建新的数据文件")
            # 文件格式错误或读取失败，创建新的数据结构
            self.frontend_data = {
                "timestamp": datetime.datetime.now().isoformat(),
                "face_detected": False,
                "hand_detected": False,
                "face_box": None,
                "last_events": [],  # 事件记录，不限制数量
                "fatigue_level": 0,  # 0-100的疲劳程度
                "ear": 0,  # 眼睛长宽比
                "mar": 0,  # 嘴部长宽比
                "current_gesture": None,  # 当前检测到的手势
                "system_status": "初始化"
            }
            self.update_frontend_data()  # 初始化前端数据文件

    def init_hand_detection_params(self):
        """初始化手势检测相关参数"""
        # 手势检测模型路径
        self.detector_path = "models/hand_detector.onnx"
        self.classifier_path = "models/crops_classifier.onnx"
        
        # 手势检测器
        self.hand_controller = None
        self.hand_drawer = None
        
        # 手势持续时间检测
        self.current_gesture = None       # 当前检测到的手势
        self.gesture_start_time = 0       # 手势开始时间
        self.gesture_hold_time = 1.0      # 手势需要保持的时间(秒) - 将在UI中设置
        self.reported_gestures = set()    # 已播报过的手势，避免重复播报
        
        # 检查模型文件是否存在
        if not os.path.exists(self.detector_path) or not os.path.exists(self.classifier_path):
            self.log_message("警告：手势检测模型文件不存在，请检查路径")
            self.checkBox_hand.setChecked(False)
            self.checkBox_hand.setEnabled(False)

    def log_message(self, message):
        """将消息添加到日志区域"""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S ', time.localtime())
        self.textBrowser.append(timestamp + message)
        self.textBrowser.moveCursor(self.textBrowser.textCursor().End)
        
    def log_detection(self, event_type, details=None):
        """记录检测事件到日志文件
        
        参数:
        - event_type: 事件类型 (如 'nod', 'shake', 'hand_gesture', 'fatigue', 'yawn', 'sleep')
        - details: 事件的详细信息 (字典形式)
        """
        if details is None:
            details = {}
            
        # 添加基本信息
        log_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'event_type': event_type,
            'details': details
        }
        
        # 转换为JSON并记录
        try:
            # 使用自定义编码器处理NumPy类型
            json_data = json.dumps(log_data, ensure_ascii=False, cls=NumpyEncoder)
            detection_logger.info(json_data)
            
            # 更新前端数据
            current_time = datetime.datetime.now().isoformat()
            event_info = {
                'timestamp': current_time,
                'event_type': event_type,
                'details': details
            }
            
            # 添加到事件列表的开头，不限制事件数量，持续积累
            self.frontend_data['last_events'].insert(0, event_info)
            
            # 更新时间戳
            self.frontend_data['timestamp'] = current_time
            
            # 更新与事件相关的特定数据
            if event_type == 'nod' or event_type == 'shake':
                self.frontend_data['head_gesture'] = event_type
            elif event_type == 'hand_gesture' and 'gesture_name' in details:
                self.frontend_data['current_gesture'] = details['gesture_name']
            elif event_type == 'fatigue':
                self.frontend_data['fatigue_level'] = 75  # 较高的疲劳度
            elif event_type == 'yawn':
                self.frontend_data['fatigue_level'] = min(self.frontend_data['fatigue_level'] + 10, 100)  # 增加疲劳度
                if 'mar' in details:
                    self.frontend_data['mar'] = details['mar']
            elif event_type == 'blink' or event_type == 'sleep':
                if 'ear' in details:
                    self.frontend_data['ear'] = details['ear']
                if event_type == 'sleep':
                    self.frontend_data['fatigue_level'] = 100  # 睡眠状态为最高疲劳度
            
            # 保存更新后的前端数据
            self.update_frontend_data()
            
        except Exception as e:
            detection_logger.error(f"日志记录失败: {str(e)}")
            print(f"日志记录失败: {str(e)}")

    def start_camera(self):
        """启动摄像头处理线程"""
        if self.CAMERA_STYLE:
            return  # 如果摄像头已在运行，则不重复打开
        
        self.log_message("正在启动摄像头...")
        import _thread
        _thread.start_new_thread(self.process_camera, ())

    def stop_camera(self):
        """停止摄像头采集"""
        if self.CAMERA_STYLE:
            # 如果正在录制，先停止录制
            if self.is_recording:
                self.stop_recording()
                self.recordButton.setText("开始录制")
            
            self.CAMERA_STYLE = False
            if hasattr(self, 'cap') and self.cap is not None:
                self.cap.release()
            self.log_message("摄像头已停止")

    def load_models(self):
        """加载所需的所有模型"""
        try:
            # 加载人脸检测器和68点特征预测模型
            self.detector = dlib.get_frontal_face_detector()
            model_path = "models/shape_predictor_68_face_landmarks.dat"
            if not os.path.exists(model_path):
                self.log_message(f"错误：找不到人脸特征点模型文件: {model_path}")
                self.checkBox_nod.setChecked(False)
                self.checkBox_shake.setChecked(False)
                self.checkBox_yawn.setChecked(False)
                self.checkBox_blink.setChecked(False)
                self.checkBox_fatigue.setChecked(False)
            else:
                self.predictor = dlib.shape_predictor(model_path)
                self.log_message("人脸特征点模型加载成功")
            
            # 初始化手势检测器
            if self.checkBox_hand.isChecked():
                if os.path.exists(self.detector_path) and os.path.exists(self.classifier_path):
                    self.hand_controller = MainController(self.detector_path, self.classifier_path)
                    self.hand_drawer = HandDrawer()
                    self.log_message("手势检测模型加载成功")
                else:
                    self.log_message("错误：手势检测模型文件不存在")
                    self.checkBox_hand.setChecked(False)
            
            # 初始化点头/摇头检测器
            self.gesture_detector = GestureDetector()
            
            return True
        except Exception as e:
            self.log_message(f"模型加载错误: {str(e)}")
            return False

    def toggle_alternating_mode(self, state):
        """切换交替检测模式"""
        self.use_alternating_detection = (state == QtCore.Qt.Checked)
        self.log_message(f"交替检测模式: {'开启' if self.use_alternating_detection else '关闭'}")

    def toggle_recording_enabled(self, state):
        """启用或禁用录制按钮"""
        self.recordButton.setEnabled(state == QtCore.Qt.Checked)
        if state != QtCore.Qt.Checked and self.is_recording:
            self.toggle_recording()  # 如果取消选中复选框且正在录制，则停止录制

    def toggle_recording(self):
        """切换录制状态"""
        if not self.is_recording:
            # 开始录制
            self.start_recording()
            self.recordButton.setText("停止录制")
        else:
            # 停止录制
            self.stop_recording()
            self.recordButton.setText("开始录制")

    def start_recording(self):
        """开始录制视频"""
        if not self.CAMERA_STYLE:
            self.log_message("无法开始录制：摄像头未启动")
            return
        
        try:
            # 创建recordings目录（如果不存在）
            if not os.path.exists("recordings"):
                os.makedirs("recordings")
            
            # 创建带有时间戳的文件名
            timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
            filename = f"recordings/recording_{timestamp}.mp4"
            
            # 获取视频分辨率
            if hasattr(self, 'cap') and self.cap is not None:
                width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            else:
                width, height = 640, 480
            
            # 设置视频编解码器和写入器
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # 或使用 'XVID'
            self.video_writer = cv2.VideoWriter(filename, fourcc, 20.0, (width, height))
            
            self.is_recording = True
            self.recording_start_time = time.time()
            self.log_message(f"开始录制视频: {filename}")
        except Exception as e:
            self.log_message(f"录制启动失败: {str(e)}")
            self.is_recording = False
            self.video_writer = None

    def stop_recording(self):
        """停止录制视频"""
        if self.is_recording and self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None
            self.is_recording = False
            
            duration = time.time() - self.recording_start_time
            self.log_message(f"视频录制已停止，持续时间: {duration:.1f}秒")

    def process_camera(self):
        """处理摄像头图像的主线程函数，整合两个项目的功能"""
        # 加载所需模型
        if not self.load_models():
            self.log_message("模型加载失败，无法启动检测")
            return
        
        # 打开摄像头
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            self.log_message("摄像头打开失败")
            return
        
        self.CAMERA_STYLE = True
        self.log_message("摄像头已打开，开始检测")
        
        # 初始化计时器
        self.time_start = time.perf_counter()
        
        # 用于控制处理帧率的变量
        process_every_n_frames = self.frameRateSpinner.value()  # 每隔N帧处理一次，减少CPU负载
        frame_count = 0
        last_error_time = 0  # 用于限制错误日志频率
        
        # 交替检测控制
        detection_mode = 0  # 0: 面部检测, 1: 手势检测
        
        # 检测到物体的状态跟踪
        face_detected = False
        hand_detected = False
        last_face_time = time.time()
        last_hand_time = time.time()
        no_detection_reported = False
        
        # 主循环处理摄像头图像
        while self.cap.isOpened() and self.CAMERA_STYLE:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    continue
                
                frame_count += 1
                if frame_count % process_every_n_frames != 0:
                    # 显示原始帧，但跳过处理
                    self.update_display(frame)
                    cv2.waitKey(1)
                    continue
                
                # 获取当前的处理帧率设置
                process_every_n_frames = self.frameRateSpinner.value()
                
                # 调整图像大小以加快处理速度
                frame = imutils.resize(frame, width=640)
                
                # 创建帧的副本，用于各种处理
                display_frame = frame.copy()
                
                # 转换为灰度图用于各种检测
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # 减少点头/摇头显示持续时间的计数器，不管当前是什么检测模式
                if self.gesture_detector and hasattr(self.gesture_detector, 'gesture_status'):
                    if self.gesture_detector.gesture_status["nod"] > 0:
                        self.gesture_detector.gesture_status["nod"] -= 1
                    if self.gesture_detector.gesture_status["shake"] > 0:
                        self.gesture_detector.gesture_status["shake"] -= 1
                
                # 使用交替检测模式时，每一帧只执行一种检测
                if self.use_alternating_detection:
                    if detection_mode == 0:
                        # 1. 人脸检测和疲劳分析
                        if (self.checkBox_nod.isChecked() or self.checkBox_shake.isChecked() or 
                            self.checkBox_yawn.isChecked() or self.checkBox_blink.isChecked() or 
                            self.checkBox_fatigue.isChecked()):
                            
                            # 检测人脸
                            faces = self.detector(gray, 0)
                            
                            if len(faces) > 0:
                                # 保存当前人脸框用于持续显示
                                face = faces[0]
                                x, y, w, h = face.left(), face.top(), face.right() - face.left(), face.bottom() - face.top()
                                self.last_face_box = (x, y, w, h)
                                self.face_box_valid_frames = self.faceBoxSpinner.value()  # 使用控件的值
                                
                                # 更新前端数据中的人脸框信息
                                self.frontend_data['face_detected'] = True
                                self.frontend_data['face_box'] = [x, y, w, h]
                                self.frontend_data['system_status'] = "正在检测人脸"
                                
                                # 处理第一个检测到的人脸
                                self.process_face(frame, display_frame, gray, faces)
                                face_detected = True
                                last_face_time = time.time()
                                no_detection_reported = False
                            else:
                                # 没有检测到人脸
                                face_detected = False
                                self.frontend_data['face_detected'] = False
                    else:
                        # 2. 手势检测
                        if self.checkBox_hand.isChecked() and self.hand_controller is not None:
                            hand_result = self.process_hands(frame, display_frame)
                            hand_detected = hand_result is not None and len(hand_result) > 0
                            
                            # 更新前端数据中的手部检测状态
                            self.frontend_data['hand_detected'] = hand_detected
                            if hand_detected:
                                self.frontend_data['system_status'] = "正在检测手势"
                                last_hand_time = time.time()
                                no_detection_reported = False
                                
                            # 即使在手势检测模式下，也显示上一帧的人脸框
                            if self.last_face_box is not None and self.face_box_valid_frames > 0:
                                x, y, w, h = self.last_face_box
                                cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                                self.face_box_valid_frames -= 1  # 减少有效帧计数
                    
                    # 每10帧更新一次前端数据文件（降低I/O开销）
                    if frame_count % 10 == 0:
                        self.update_frontend_data()
                    
                    # 检查是否需要播放"脱离范围"提示
                    current_time = time.time()
                    if (not face_detected and not hand_detected and 
                        current_time - last_face_time > 3 and 
                        current_time - last_hand_time > 3 and
                        not no_detection_reported):
                        self.log_message("脱离识别范围!!!")
                        self.frontend_data['system_status'] = "脱离识别范围"
                        self.frontend_data['face_detected'] = False
                        self.frontend_data['hand_detected'] = False
                        self.update_frontend_data()  # 立即更新状态
                        t = threading.Thread(target=self.play_sound, args=("noface",))
                        t.start()
                        no_detection_reported = True
                        
                    # 切换检测模式
                    detection_mode = 1 - detection_mode
                else:
                    # 不使用交替检测，同时执行两种检测
                    face_detected = False
                    hand_detected = False
                    
                    # 1. 人脸检测和疲劳分析
                    if (self.checkBox_nod.isChecked() or self.checkBox_shake.isChecked() or 
                        self.checkBox_yawn.isChecked() or self.checkBox_blink.isChecked() or 
                        self.checkBox_fatigue.isChecked()):
                        
                        # 检测人脸
                        faces = self.detector(gray, 0)
                        
                        if len(faces) > 0:
                            # 更新前端数据中的人脸框信息
                            face = faces[0]
                            x, y, w, h = face.left(), face.top(), face.right() - face.left(), face.bottom() - face.top()
                            self.frontend_data['face_detected'] = True
                            self.frontend_data['face_box'] = [x, y, w, h]
                            self.frontend_data['system_status'] = "正在检测人脸"
                            
                            # 处理第一个检测到的人脸
                            self.process_face(frame, display_frame, gray, faces)
                            face_detected = True
                            last_face_time = time.time()
                            no_detection_reported = False
                        else:
                            # 没有检测到人脸
                            face_detected = False
                            self.frontend_data['face_detected'] = False
                    
                    # 2. 手势检测
                    if self.checkBox_hand.isChecked() and self.hand_controller is not None:
                        hand_result = self.process_hands(frame, display_frame)
                        hand_detected = hand_result is not None and len(hand_result) > 0
                        
                        # 更新前端数据中的手部检测状态
                        self.frontend_data['hand_detected'] = hand_detected
                        if hand_detected:
                            self.frontend_data['system_status'] = "正在检测手势"
                            last_hand_time = time.time()
                            no_detection_reported = False
                    
                    # 每10帧更新一次前端数据文件
                    if frame_count % 10 == 0:
                        self.update_frontend_data()
                
                # 更新界面显示
                self.update_display(display_frame)
                
                # 录制处理帧
                if self.is_recording and self.video_writer is not None:
                    try:
                        # 添加录制指示器
                        rec_indicator = "● REC"
                        text_size = cv2.getTextSize(rec_indicator, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
                        cv2.putText(display_frame, rec_indicator, 
                                   (display_frame.shape[1] - text_size[0] - 10, 30),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                        
                        # 添加时间戳
                        if self.recording_start_time is not None:
                            rec_time = time.time() - self.recording_start_time
                            timestamp = f"{int(rec_time // 60):02d}:{int(rec_time % 60):02d}"
                            cv2.putText(display_frame, timestamp, 
                                       (display_frame.shape[1] - 70, 60),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                        
                        # 写入帧
                        self.video_writer.write(display_frame)
                    except Exception as e:
                        self.log_message(f"录制帧时出错: {str(e)}")
                
                # 在图像上标注当前模式
                if self.use_alternating_detection:
                    mode_text = "面部检测模式" if detection_mode == 0 else "手势检测模式"
                    cv2.putText(display_frame, mode_text, (10, display_frame.shape[0] - 10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                
                # 延时以控制处理速度
                cv2.waitKey(1)
                
            except Exception as e:
                current_time = time.time()
                # 限制错误日志频率，避免刷屏
                if current_time - last_error_time > 5:  # 每5秒最多记录一次同类错误
                    print(f"处理错误: {str(e)}")
                    self.log_message(f"处理发生错误: {str(e)[:50]}")
                    last_error_time = current_time
                
                # 短暂休息，让系统有时间恢复
                time.sleep(0.1)
        
        # 关闭摄像头
        if self.cap is not None:
            self.cap.release()
            
    def process_face(self, frame, display_frame, gray, faces):
        """处理检测到的人脸"""
        # 取第一个人脸进行处理
        face = faces[0]
        
        # 绘制人脸边界框，使用更明显的红色矩形
        x, y, w, h = face.left(), face.top(), face.right() - face.left(), face.bottom() - face.top()
        cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
        
        # 在画面上显示检测到的人脸数量
        cv2.putText(display_frame, f"FACES: {len(faces)}", (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.putText(display_frame, f"COUNTER: {self.COUNTER}", (300, 30),
                  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # 提取人脸特征点
        shape = self.predictor(frame, face)
        
        # 绘制所有68个特征点 - 更大更明显
        for i in range(68):
            cv2.circle(display_frame, (shape.part(i).x, shape.part(i).y), 3, (0, 255, 0), -1, 8)
        
        # 转换特征点格式用于后续处理
        shape = face_utils.shape_to_np(shape)
        
        # 绘制面部轮廓线 - 增加详细度
        # 脸部轮廓 (0-16)
        for i in range(16):
            cv2.line(display_frame, (shape[i][0], shape[i][1]), 
                    (shape[i+1][0], shape[i+1][1]), (0, 255, 0), 1)
            
        # 左眉毛 (17-21)
        for i in range(17, 21):
            cv2.line(display_frame, (shape[i][0], shape[i][1]), 
                    (shape[i+1][0], shape[i+1][1]), (0, 255, 0), 1)
            
        # 右眉毛 (22-26)
        for i in range(22, 26):
            cv2.line(display_frame, (shape[i][0], shape[i][1]), 
                    (shape[i+1][0], shape[i+1][1]), (0, 255, 0), 1)
            
        # 鼻梁 (27-30)
        for i in range(27, 30):
            cv2.line(display_frame, (shape[i][0], shape[i][1]), 
                    (shape[i+1][0], shape[i+1][1]), (0, 255, 0), 1)
            
        # 鼻子底部 (31-35)
        for i in range(31, 35):
            cv2.line(display_frame, (shape[i][0], shape[i][1]), 
                    (shape[i+1][0], shape[i+1][1]), (0, 255, 0), 1)
        cv2.line(display_frame, (shape[35][0], shape[35][1]), 
                (shape[31][0], shape[31][1]), (0, 255, 0), 1)
            
        # 左眼 (36-41)
        for i in range(36, 41):
            cv2.line(display_frame, (shape[i][0], shape[i][1]), 
                    (shape[i+1][0], shape[i+1][1]), (0, 255, 0), 1)
        cv2.line(display_frame, (shape[41][0], shape[41][1]), 
                (shape[36][0], shape[36][1]), (0, 255, 0), 1)
            
        # 右眼 (42-47)
        for i in range(42, 47):
            cv2.line(display_frame, (shape[i][0], shape[i][1]), 
                    (shape[i+1][0], shape[i+1][1]), (0, 255, 0), 1)
        cv2.line(display_frame, (shape[47][0], shape[47][1]), 
                (shape[42][0], shape[42][1]), (0, 255, 0), 1)
            
        # 嘴唇外围 (48-59)
        for i in range(48, 59):
            cv2.line(display_frame, (shape[i][0], shape[i][1]), 
                    (shape[i+1][0], shape[i+1][1]), (0, 255, 0), 1)
        cv2.line(display_frame, (shape[59][0], shape[59][1]), 
                (shape[48][0], shape[48][1]), (0, 255, 0), 1)
            
        # 嘴唇内围 (60-67)
        for i in range(60, 67):
            cv2.line(display_frame, (shape[i][0], shape[i][1]), 
                    (shape[i+1][0], shape[i+1][1]), (0, 255, 0), 1)
        cv2.line(display_frame, (shape[67][0], shape[67][1]), 
                (shape[60][0], shape[60][1]), (0, 255, 0), 1)
        
        # 左眼轮廓
        leftEye = shape[self.lStart:self.lEnd]
        leftEyeHull = cv2.convexHull(leftEye)
        cv2.drawContours(display_frame, [leftEyeHull], -1, (0, 255, 0), 2)
        
        # 右眼轮廓
        rightEye = shape[self.rStart:self.rEnd]
        rightEyeHull = cv2.convexHull(rightEye)
        cv2.drawContours(display_frame, [rightEyeHull], -1, (0, 255, 0), 2)
        
        # 嘴部轮廓
        mouth = shape[self.mStart:self.mEnd]
        mouthHull = cv2.convexHull(mouth)
        cv2.drawContours(display_frame, [mouthHull], -1, (0, 255, 0), 2)
        
        # 点头/摇头检测
        if self.checkBox_nod.isChecked() or self.checkBox_shake.isChecked():
            # 检查是否在等待期内
            if self.gesture_detector.wait_after_detection:
                current_time = time.time()
                if current_time >= self.gesture_detector.wait_until_time:
                    # 等待期结束，重置等待标志
                    self.gesture_detector.wait_after_detection = False
                    self.log_message("点头/摇头检测恢复")
                # 等待期内不显示任何文字提示
            else:
                # 不在等待期内，进行正常检测
                self.process_head_gesture(frame, display_frame, gray, face)
        
        # 打哈欠检测
        if self.checkBox_yawn.isChecked():
            self.process_yawn(frame, display_frame, shape)
        
        # 闭眼检测
        if self.checkBox_blink.isChecked():
            self.process_blink(frame, display_frame, shape)
        
        # 疲劳状态检测
        if self.checkBox_fatigue.isChecked():
            self.check_fatigue_status()
    
    def process_head_gesture(self, frame, display_frame, gray, face):
        """处理头部姿态（点头/摇头）检测"""
        # 如果在等待期内，直接返回不进行检测
        if self.gesture_detector.wait_after_detection:
            return
            
        # 提取人脸区域
        x = face.left(); y = face.top()
        w = face.right() - face.left(); h = face.bottom() - face.top()
        
        # 如果未初始化跟踪点或跟踪中断超过5帧，则重新初始化跟踪点
        if self.gesture_detector.face_center is None or self.gesture_detector.lost_counter > 5:
            face_center = (x + w // 2, y + h // 2 + h // 5)
            self.gesture_detector.face_center = face_center
            self.gesture_detector.track_points = [np.array([[face_center]], np.float32)]
            self.gesture_detector.lost_counter = 0
            self.prev_gray = gray.copy()
        else:
            self.gesture_detector.lost_counter = 0
            
        # 光流跟踪
        if self.gesture_detector.track_points and self.prev_gray is not None:
            try:
                # 计算光流跟踪的新位置
                new_points, st, err = cv2.calcOpticalFlowPyrLK(
                    self.prev_gray, gray, self.gesture_detector.track_points[-1], None, **lk_params)
                
                if new_points is not None:
                    self.gesture_detector.update_tracking(new_points)
                    self.prev_gray = gray.copy()
                    
                    # 分析运动轨迹判断动作
                    gesture = self.gesture_detector.analyze_motion()
                    
                    # 根据选中选项过滤未启用的手势检测
                    if gesture == "nod" and not self.checkBox_nod.isChecked():
                        gesture = None
                    if gesture == "shake" and not self.checkBox_shake.isChecked():
                        gesture = None
                        
                    # 处理检测到的手势
                    if gesture:
                        self.log_message("检测到" + ("点头" if gesture == "nod" else "摇头"))
                        
                        # 记录到日志文件
                        gesture_details = {
                            'motion_data': {
                                k: float(v) if isinstance(v, (np.integer, np.floating)) else v 
                                for k, v in self.gesture_detector.debug_info.items()
                            },
                            'threshold': float(NOD_THRESHOLD if gesture == "nod" else SHAKE_THRESHOLD)
                        }
                        self.log_detection(gesture, gesture_details)
                        
                        t = threading.Thread(target=self.play_sound, args=(gesture,))
                        t.start()
                        self.gesture_detector.reset_counters(gesture)
            except Exception as e:
                print(f"跟踪错误: {str(e)}")
                self.gesture_detector.track_points = []
                self.gesture_detector.face_center = None
        
        # 在画面上显示检测结果
        if self.gesture_detector.gesture_status["nod"] > 0:
            cv2.putText(display_frame, "NODDING", (50, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
        if self.gesture_detector.gesture_status["shake"] > 0:
            cv2.putText(display_frame, "SHAKING", (50, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 0, 0), 3)
        
        # 调试信息不再在图像上显示
        if self.checkBox_hand_debug.isChecked():
            # 不再绘制跟踪点
            pass
    
    def process_yawn(self, frame, display_frame, shape):
        """处理打哈欠检测"""
        # 提取嘴部特征点
        mouth = shape[self.mStart:self.mEnd]
        # 计算嘴部长宽比
        mar = self.mouth_aspect_ratio(mouth)
        
        # 更新前端数据，即使没有触发事件
        self.frontend_data['mar'] = float(mar)
        
        # 绘制嘴部轮廓 - 使用更粗的线条
        mouthHull = cv2.convexHull(mouth)
        
        # 始终绘制嘴部轮廓，而不仅在调试模式下
        cv2.drawContours(display_frame, [mouthHull], -1, (0, 255, 0), 2)
        
        # 在画面上显示MAR值
        cv2.putText(display_frame, "MAR: {:.2f}".format(mar), (20, 100),
                  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                  
        # 检测打哈欠
        if mar > self.MAR_THRESH:
            self.mCOUNTER += 1
        if mar < self.MAR_THRESH:
            self.mCOUNTER = 0
        else:
            if self.mCOUNTER >= self.MOUTH_AR_CONSEC_FRAMES:
                self.ifYawming = True
                
        if self.ifYawming:
            if self.mTOTAL == 0:
                self.timeOfTheFirstOfYawns = datetime.datetime.now()
            if self.mTOTAL == self.Number_Of_Yawns_Judged_As_Fatigue - 1:
                self.timeOfTheLastOfYawns = datetime.datetime.now()
            if mar < self.MAR_THRESH:
                self.ifYawming = False
                self.mTOTAL += 1
                self.log_message("打哈欠")
                
                # 记录到日志文件
                yawn_details = {
                    'counter': self.mTOTAL,
                    'mar': float(mar),  # 确保mar是可JSON序列化的
                    'threshold': float(self.MAR_THRESH),
                    'frames_count': self.mCOUNTER
                }
                self.log_detection('yawn', yawn_details)
                
                # 播放打哈欠提示音
                t = threading.Thread(target=self.play_sound, args=("yawn",))
                t.start()
            
            # 显示打哈欠文本 - 使用更大的字体和更粗的线条
            cv2.putText(display_frame, "YAWNING", (50, 160), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
    
    def process_blink(self, frame, display_frame, shape):
        """处理眨眼/闭眼检测"""
        # 提取左右眼特征点
        leftEye = shape[self.lStart:self.lEnd]
        rightEye = shape[self.rStart:self.rEnd]
        
        # 计算眼睛长宽比
        leftEAR = self.eye_aspect_ratio(leftEye)
        rightEAR = self.eye_aspect_ratio(rightEye)
        ear = (leftEAR + rightEAR) / 2.0
        
        # 更新前端数据，即使没有触发事件
        self.frontend_data['ear'] = float(ear)
        
        # 绘制眼睛轮廓 - 使用更粗的线条
        leftEyeHull = cv2.convexHull(leftEye)
        rightEyeHull = cv2.convexHull(rightEye)
        
        # 始终绘制眼睛轮廓，而不仅在调试模式下
        cv2.drawContours(display_frame, [leftEyeHull], -1, (0, 255, 0), 2)
        cv2.drawContours(display_frame, [rightEyeHull], -1, (0, 255, 0), 2)
        
        # 在画面上显示EAR值
        cv2.putText(display_frame, "EAR: {:.2f}".format(ear), (20, 70),
                  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # 检测闭眼
        self.time_end = time.perf_counter()
        self.time_reduce = self.time_end - self.time_start
        
        if ear < self.EYE_AR_THRESH:
            self.COUNTER += 1
        else:
            # 如果有足够的闭眼帧数，记录眨眼事件
            if self.COUNTER >= 5 and self.COUNTER < self.AR_CONSEC_FRAMES:  # 正常眨眼
                blink_details = {
                    'frames_count': self.COUNTER,
                    'ear': float(ear),
                    'threshold': float(self.EYE_AR_THRESH)
                }
                self.log_detection('blink', blink_details)
            
            self.COUNTER = 0
            
        if self.COUNTER >= self.AR_CONSEC_FRAMES:
            self.shutEye = True
            
        # 在调试模式下显示眼睛状态信息
        if self.checkBox_hand_debug.isChecked():
            cv2.putText(display_frame, f"COUNTER: {self.COUNTER}", (300, 30),
                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    
    def check_fatigue_status(self):
        """综合判断疲劳状态"""
        # 如果闭眼时间过长，判定为睡觉
        if self.shutEye:
            self.log_message("睡觉")
            
            # 记录到日志文件
            sleep_details = {
                'frames_count': self.COUNTER,
                'threshold_frames': self.AR_CONSEC_FRAMES,
                'duration': float(self.time_reduce)
            }
            self.log_detection('sleep', sleep_details)
            
            t = threading.Thread(target=self.play_sound, args=("sleep",))
            t.start()
            self.shutEye = False
            self.COUNTER = 0
            
        # 根据短时间内的哈欠次数判断疲劳
        if (self.mTOTAL >= self.Number_Of_Yawns_Judged_As_Fatigue and
            (0 < (self.timeOfTheLastOfYawns - self.timeOfTheFirstOfYawns).seconds < self.NOYJAF_Time)):
            self.log_message("疲劳")
            
            # 记录到日志文件
            fatigue_details = {
                'yawn_count': self.mTOTAL,
                'threshold_count': self.Number_Of_Yawns_Judged_As_Fatigue,
                'time_window': (self.timeOfTheLastOfYawns - self.timeOfTheFirstOfYawns).seconds,
                'max_time_window': self.NOYJAF_Time,
                'first_yawn_time': self.timeOfTheFirstOfYawns.isoformat(),
                'last_yawn_time': self.timeOfTheLastOfYawns.isoformat()
            }
            self.log_detection('fatigue', fatigue_details)
            
            t = threading.Thread(target=self.play_sound, args=("tired",))
            t.start()
            # 重置相关计数
            self.TOTAL = 0
            self.mTOTAL = 0
            self.ifTired = False
    
    def handle_no_face(self, display_frame):
        """处理未检测到人脸的情况"""
        # 增加未检测到人脸的计数
        self.oCOUNTER += 1
        
        if self.checkBox_hand_debug.isChecked():
            cv2.putText(display_frame, "No Face", (20, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 1, cv2.LINE_AA)
        
        # 点头/摇头检测器状态更新
        if self.checkBox_nod.isChecked() or self.checkBox_shake.isChecked():
            # 计数跟踪丢失帧数
            self.gesture_detector.lost_counter += 1
            self.gesture_detector.face_center = None
            if self.gesture_detector.lost_counter > 5:
                self.gesture_detector.track_points = []
    
    def process_hands(self, frame, display_frame):
        """处理手势检测"""
        try:
            # 使用MainController进行手部检测和手势识别
            # MainController返回三个值：边界框、跟踪ID、手势标签
            bboxes, track_ids, labels = self.hand_controller(frame)
            
            # 检查是否有检测到的手势
            if bboxes is not None and len(bboxes) > 0:
                # 获取第一个检测到的手势（如果有多个，只处理第一个）
                current_detected_gesture = None
                gesture_box = None
                
                for i, box in enumerate(bboxes):
                    # 绘制检测结果
                    if self.checkBox_hand_debug.isChecked():
                        # 绘制手势边界框
                        x1, y1, x2, y2 = map(int, box[:4])
                        cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    
                    # 处理检测到的手势
                    if labels[i] is not None:
                        # 获取手势名称 - 使用gesture_targets列表获取手势名称
                        gesture_index = labels[i]
                        if 0 <= gesture_index < len(gesture_targets):
                            gesture_name = gesture_targets[gesture_index]
                            current_detected_gesture = gesture_name
                            gesture_box = box.copy()  # 创建副本以避免引用问题
                            break  # 只处理第一个检测到的手势
                
                # 手势持续时间检测
                current_time = time.time()
                
                # 如果检测到了手势
                if current_detected_gesture is not None:
                    # 在画面上显示手势名称
                    x1, y1 = map(int, gesture_box[:2])
                    cv2.putText(display_frame, f"Gesture: {current_detected_gesture}",
                               (x1, y1 - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    
                    # 如果是新的手势或者之前没有手势
                    if self.current_gesture != current_detected_gesture:
                        self.current_gesture = current_detected_gesture
                        self.gesture_start_time = current_time
                        hold_time = 0
                    else:
                        # 计算手势已经保持的时间
                        hold_time = current_time - self.gesture_start_time
                    
                    # 绘制手势保持进度条
                    x1, y1, x2, y2 = map(int, gesture_box[:4])
                    progress = min(1.0, hold_time / self.gesture_hold_time)
                    
                    # 计算进度条宽度
                    bar_width = int((x2 - x1) * progress)
                    
                    # 绘制进度条背景
                    cv2.rectangle(display_frame, 
                                 (x1, y2 + 5), 
                                 (x2, y2 + 15), 
                                 (100, 100, 100), 
                                 -1)
                    
                    # 绘制进度
                    if progress < 1.0:
                        # 进行中 - 蓝色
                        bar_color = (255, 128, 0)  # 橙色
                    else:
                        # 完成 - 绿色
                        bar_color = (0, 255, 0)
                    
                    cv2.rectangle(display_frame, 
                                 (x1, y2 + 5), 
                                 (x1 + bar_width, y2 + 15), 
                                 bar_color, 
                                 -1)
                    
                    # 在调试模式下显示手势保持时间
                    if self.checkBox_hand_debug.isChecked():
                        cv2.putText(display_frame, f"Hold: {hold_time:.1f}s / {self.gesture_hold_time:.1f}s",
                                   (x1, y2 + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    
                    # 检查手势是否已经保持足够长的时间且未播报过
                    gesture_key = f"{current_detected_gesture}_{int(current_time/10)}"  # 每10秒允许相同手势再次播报
                    if hold_time >= self.gesture_hold_time and gesture_key not in self.reported_gestures:
                        # 添加手势名称到日志
                        self.log_message(f"检测到手势: {current_detected_gesture} (已保持{hold_time:.1f}秒)")
                        
                        # 记录到日志文件
                        # 将NumPy数组转换为Python列表
                        bbox = [float(x) for x in gesture_box[:4]]
                        gesture_details = {
                            'gesture_name': current_detected_gesture,
                            'hold_time': float(hold_time),
                            'bbox': bbox,
                            'hold_threshold': float(self.gesture_hold_time)
                        }
                        self.log_detection('hand_gesture', gesture_details)
                        
                        # 播放手势声音（使用线程避免阻塞主线程）
                        t = threading.Thread(target=self.play_sound, args=(f"gesture_{current_detected_gesture}",))
                        t.start()
                        
                        # 标记为已播报
                        self.reported_gestures.add(gesture_key)
                        
                        # 定期清理过旧的已播报手势记录
                        if len(self.reported_gestures) > 100:
                            self.reported_gestures = set(list(self.reported_gestures)[-50:])
                else:
                    # 没有检测到手势，重置状态
                    self.current_gesture = None
            else:
                # 没有检测到任何手，重置状态
                self.current_gesture = None
            
            return bboxes
        except Exception as e:
            self.log_message(f"手势检测错误: {str(e)}")
            return None
    
    def update_display(self, frame):
        """更新界面显示"""
        # 转换图像格式用于Qt显示
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        # 只更新主视图
        self.videoDisplay.setPixmap(QPixmap.fromImage(qt_image))
    
    def play_sound(self, sound_type):
        """播放声音提示"""
        # 定义声音文件路径，优先使用WAV格式
        sound_files = {
            # 人脸检测声音
            "nod": "sounds/Nod",
            "shake": "sounds/Shake",
            "tired": "sounds/Tired",
            "sleep": "sounds/Sleep",
            "noface": "sounds/NoFace",
            "yawn": "sounds/Tired"
        }
        
        # 检查是否是手势声音
        if sound_type.startswith("gesture_"):
            # 提取手势名称并查找对应声音文件
            gesture_name = sound_type[8:]  # 去掉"gesture_"前缀
            base_sound_file = f"sounds/gestures/{gesture_name}"
        else:
            base_sound_file = sound_files.get(sound_type)
            
        if not base_sound_file:
            self.log_message(f"未定义的声音类型: {sound_type}")
            return
            
        # 优先尝试WAV文件，如果没有则使用MP3
        wav_file = f"{base_sound_file}.wav"
        
        # 检查WAV文件是否存在
        if os.path.exists(wav_file):
            sound_file = wav_file
        else:
            # WAV文件不存在，使用系统提示音
            if system == "Windows":
                winsound.MessageBeep(0)
            self.log_message(f"找不到声音文件: {wav_file}")
            return
        
        try:
            if system == "Windows":
                # 使用异步模式播放，避免主线程阻塞
                winsound.PlaySound(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                player = vlc.MediaPlayer(sound_file)
                player.play()
        except Exception as e:
            print(f"音频播放错误: {str(e)}")
            # 如果失败，只记录错误但不阻止程序继续运行
            self.log_message(f"无法播放声音: {sound_type}")

    def eye_aspect_ratio(self, eye):
        """计算眼睛的长宽比"""
        A = dist.euclidean(eye[1], eye[5])
        B = dist.euclidean(eye[2], eye[4])
        C = dist.euclidean(eye[0], eye[3])
        ear = (A + B) / (2.0 * C)
        return ear
    
    def mouth_aspect_ratio(self, mouth):
        """计算嘴部的长宽比"""
        A = np.linalg.norm(mouth[2] - mouth[9])
        B = np.linalg.norm(mouth[4] - mouth[7])
        C = np.linalg.norm(mouth[0] - mouth[6])
        mar = (A + B) / (2.0 * C)
        # 在调试模式下打印MAR值
        if self.checkBox_hand_debug.isChecked():
            print(f"当前MAR值: {mar}")
        return mar

    def update_hold_time(self, value):
        """更新手势保持时间"""
        # 将滑块值转换为秒数（除以10以获得小数）
        seconds = value / 10.0
        # 更新标签显示
        self.holdTimeValueLabel.setText(f"{seconds:.1f}")
        # 更新手势保持时间
        self.gesture_hold_time = seconds
        self.log_message(f"手势保持时间已更新为 {seconds:.1f} 秒")

    def update_nod_sensitivity(self, value):
        """更新点头检测灵敏度"""
        global NOD_THRESHOLD  # 使用全局变量
        NOD_THRESHOLD = value
        self.nodSensitivityValueLabel.setText(f"{value}")
        self.log_message(f"点头检测阈值已调整为: {value} (值越大越不灵敏)")
        
        # 如果已经创建了检测器，更新其相关参数
        if hasattr(self, 'gesture_detector') and self.gesture_detector is not None:
            # 重置检测器状态，避免误检测
            self.gesture_detector.track_points = []
            self.gesture_detector.direction_history = []
            
    def update_face_box_frames(self, value):
        """更新人脸框持续显示帧数"""
        self.face_box_valid_frames = value
        self.log_message(f"人脸框持续显示帧数已更新为: {value}")

    def update_frontend_data(self):
        """更新前端数据文件，静默模式，不输出任何信息"""
        try:
            with open(self.frontend_data_file, 'w', encoding='utf-8') as f:
                json.dump(self.frontend_data, f, indent=4, ensure_ascii=False, cls=NumpyEncoder)
            # 不输出任何日志信息
        except Exception as e:
            # 只有错误情况才记录日志
            detection_logger.error(f"保存前端数据时出错: {str(e)}")
            # 不向UI输出错误信息

# 主程序入口
if __name__ == "__main__":
    # 尝试注册QTextCursor类型以解决Qt警告，但不影响程序运行
    try:
        # 不同版本的PyQt5可能有不同的注册方法
        from PyQt5.QtCore import qRegisterMetaType
        qRegisterMetaType('QTextCursor')
    except (ImportError, AttributeError):
        # 忽略错误，这只是用于解决警告，不影响程序功能
        print("注意: 无法注册QTextCursor类型，这可能导致一些Qt警告，但不影响功能")
    
    # 创建QT应用
    app = QApplication(sys.argv)
    
    # 创建主窗口
    MainWindow = QMainWindow()
    
    # 创建并设置UI
    ui = IntegratedUI(MainWindow)
    
    # 显示窗口
    MainWindow.show()
    
    # 在日志中显示启动消息
    ui.log_message("集成系统已启动")
    ui.log_message("请点击\"开始检测\"按钮开始识别")
    
    # 执行应用程序
    sys.exit(app.exec_()) 