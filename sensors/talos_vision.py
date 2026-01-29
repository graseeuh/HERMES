import cv2
import mediapipe as mp
import os
import time
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# 1. Path Management (Absolute path to avoid Windows errors)
current_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(current_dir, 'blaze_face_short_range.tflite')

# 2. Setup Modern Tasks Configuration
BaseOptions = mp.tasks.BaseOptions
FaceDetector = mp.tasks.vision.FaceDetector
FaceDetectorOptions = mp.tasks.vision.FaceDetectorOptions
VisionRunningMode = mp.tasks.vision.RunningMode

options = FaceDetectorOptions(
    base_options=BaseOptions(model_asset_path=model_path),
    running_mode=VisionRunningMode.VIDEO
)

# 3. Initialize Camera (Brio 101)
cap = cv2.VideoCapture(0)

# 4. Launch the Sentinel
with FaceDetector.create_from_options(options) as detector:
    print("TALOS Sentinel: Online and Scanning for CEO Christian Gracia...")
    
    while cap.isOpened():
        success, frame = cap.read()
        if not success: continue

        # Convert OpenCV BGR to MediaPipe RGB Image
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
        
        # Calculate Frame Timestamp (Required for VIDEO mode)
        frame_timestamp_ms = int(time.time() * 1000)
        
        # Run Detection
        detection_result = detector.detect_for_video(mp_image, frame_timestamp_ms)

        # 5. Logic: Visual Feedback and Alerts
        if detection_result.detections:
            print(f"HERMES: {len(detection_result.detections)} face(s) in proximity.")
            
            # Simple bounding box drawing logic
            for detection in detection_result.detections:
                bbox = detection.bounding_box
                start_point = int(bbox.origin_x), int(bbox.origin_y)
                end_point = int(bbox.origin_x + bbox.width), int(bbox.origin_y + bbox.height)
                cv2.rectangle(frame, start_point, end_point, (0, 255, 0), 2)

        cv2.imshow('TALOS Sentinel Feed', frame)
        
        if cv2.waitKey(5) & 0xFF == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()