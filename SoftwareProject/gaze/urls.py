from django.urls import path
from .views import gaze_api, gaze_live, start_demo

urlpatterns = [
    path("api/",  gaze_api,  name="gaze_api"),   # /gaze/api/
    path("live/", gaze_live, name="gaze_live"),  # /gaze/live/
    path("start/", start_demo, name="gaze_start"), # /gaze/start/
]