import cv2
import mediapipe as mp
import pyttsx3
import time
import os
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# 1. Initialize Voice Engine
engine = pyttsx3.init()
engine.setProperty('rate', 175)

def speak(text):
    print(f"HERMES: {text}")
    engine.say(text)
    engine.runAndWait()

# 2. Setup Modern Vision Path
current_dir = os.path.dirname(os.path.abspath(__file__))
# Ensure you have blaze_face_short_range.tflite in your sensors folder
model_path = os.path.join(current_dir, 'blaze_face_short_range.tflite')

BaseOptions = mp.tasks.BaseOptions
FaceDetector = mp.tasks.vision.FaceDetector
FaceDetectorOptions = mp.tasks.vision.FaceDetectorOptions
VisionRunningMode = mp.tasks.vision.RunningMode

options = FaceDetectorOptions(
    base_options=BaseOptions(model_asset_path=model_path),
    running_mode=VisionRunningMode.VIDEO
)

# 3. Sentinel State
last_greeting_time = 0
cooldown = 15  # 15 seconds of silence between greetings

cap = cv2.VideoCapture(0)

# 4. Launch the Sentinel
with FaceDetector.create_from_options(options) as detector:
    print("TALOS Sentinel: Online. Awaiting CEO...")
    
    while cap.isOpened():
        success, frame = cap.read()
        if not success: continue

        # Convert to MediaPipe Image format
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
        timestamp_ms = int(time.time() * 1000)
        
        # Run Detection
        detection_result = detector.detect_for_video(mp_image, timestamp_ms)
        current_time = time.time()

        if detection_result.detections:
            # If a face is found and we are off cooldown
            if (current_time - last_greeting_time) > cooldown:
                speak("Identity confirmed. Hello Christian. HERMES systems are standing by.")
                last_greeting_time = current_time

        cv2.imshow('TALOS Feed', frame)
        if cv2.waitKey(5) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()