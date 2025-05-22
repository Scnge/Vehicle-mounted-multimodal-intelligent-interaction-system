import mediapipe as mp
import cv2
import numpy as np
from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import render

# 全局参数
max_hands = 2
detection_confidence = 50
tracking_confidence = 50
landmark_color = (0, 0, 255)  # BGR
box_color = (0, 255, 0)      # BGR
box_thickness = 2
landmark_size = 2

class VideoStream:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            min_detection_confidence=detection_confidence/100,
            min_tracking_confidence=tracking_confidence/100
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

    def __del__(self):
        self.cap.release()
        self.hands.close()

    def update_params(self):
        global max_hands, detection_confidence, tracking_confidence
        self.hands.close()
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            min_detection_confidence=detection_confidence/100,
            min_tracking_confidence=tracking_confidence/100
        )

    def get_frame(self):
        success, image = self.cap.read()
        if not success:
            return None

        image = cv2.flip(image, 1)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self.hands.process(image_rgb)
        
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                self.mp_drawing.draw_landmarks(
                    image,
                    hand_landmarks,
                    self.mp_hands.HAND_CONNECTIONS,
                    self.mp_drawing.DrawingSpec(color=landmark_color, thickness=landmark_size, circle_radius=landmark_size),
                    self.mp_drawing.DrawingSpec(color=box_color, thickness=box_thickness)
                )
                self.draw_hand_box(image, hand_landmarks.landmark, box_color, box_thickness)

        ret, jpeg = cv2.imencode('.jpg', image)
        return jpeg.tobytes()

    def draw_hand_box(self, image, landmarks, color, thickness):
        x_min, y_min = min([landmark.x for landmark in landmarks]), min([landmark.y for landmark in landmarks])
        x_max, y_max = max([landmark.x for landmark in landmarks]), max([landmark.y for landmark in landmarks])
        
        h, w, _ = image.shape
        x_min, y_min = int(x_min * w), int(y_min * h)
        x_max, y_max = int(x_max * w), int(y_max * h)
        
        cv2.rectangle(image, (x_min, y_min), (x_max, y_max), color, thickness)

def index(request):
    return render(request, 'gesture/index.html')

def video_feed(request):
    return StreamingHttpResponse(
        gen(VideoStream()),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )

def update_params(request):
    global max_hands, detection_confidence, tracking_confidence, landmark_color, box_color, box_thickness, landmark_size
    
    if request.method == 'POST':
        max_hands = int(request.POST.get('max_hands', max_hands))
        detection_confidence = int(request.POST.get('detection_confidence', detection_confidence))
        tracking_confidence = int(request.POST.get('tracking_confidence', tracking_confidence))
        box_thickness = int(request.POST.get('box_thickness', box_thickness))
        landmark_size = int(request.POST.get('landmark_size', landmark_size))
        
        # 更新颜色
        landmark_color = (
            int(request.POST.get('landmark_b', landmark_color[0])),
            int(request.POST.get('landmark_g', landmark_color[1])),
            int(request.POST.get('landmark_r', landmark_color[2]))
        )
        box_color = (
            int(request.POST.get('box_b', box_color[0])),
            int(request.POST.get('box_g', box_color[1])),
            int(request.POST.get('box_r', box_color[2]))
        )
        
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'})

def gen(video_stream):
    while True:
        frame = video_stream.get_frame()
        if frame is None:
            break
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')