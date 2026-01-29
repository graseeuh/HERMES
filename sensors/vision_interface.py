"""
HERMES Vision Interface
Wrapper for MediaPipe and OpenCV for computer vision tasks.
"""

import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False


class DetectionType(Enum):
    """Types of detection available."""
    HANDS = "hands"
    FACE = "face"
    POSE = "pose"
    HOLISTIC = "holistic"


@dataclass
class HandLandmarks:
    """Hand landmark detection results."""
    landmarks: List[Tuple[float, float, float]]  # x, y, z for each of 21 landmarks
    handedness: str  # 'Left' or 'Right'
    confidence: float


@dataclass
class FaceLandmarks:
    """Face mesh detection results."""
    landmarks: List[Tuple[float, float, float]]  # 468 landmarks
    confidence: float


@dataclass
class PoseLandmarks:
    """Pose estimation results."""
    landmarks: List[Tuple[float, float, float]]  # 33 landmarks
    confidence: float


@dataclass
class DetectionResult:
    """Generic detection result container."""
    detection_type: DetectionType
    frame_shape: Tuple[int, int, int]
    hands: Optional[List[HandLandmarks]] = None
    face: Optional[FaceLandmarks] = None
    pose: Optional[PoseLandmarks] = None
    raw_results: Optional[Any] = None


class VisionInterface:
    """
    Interface for computer vision operations using MediaPipe and OpenCV.
    """

    # MediaPipe hand landmark indices
    HAND_LANDMARKS = {
        'WRIST': 0,
        'THUMB_CMC': 1, 'THUMB_MCP': 2, 'THUMB_IP': 3, 'THUMB_TIP': 4,
        'INDEX_MCP': 5, 'INDEX_PIP': 6, 'INDEX_DIP': 7, 'INDEX_TIP': 8,
        'MIDDLE_MCP': 9, 'MIDDLE_PIP': 10, 'MIDDLE_DIP': 11, 'MIDDLE_TIP': 12,
        'RING_MCP': 13, 'RING_PIP': 14, 'RING_DIP': 15, 'RING_TIP': 16,
        'PINKY_MCP': 17, 'PINKY_PIP': 18, 'PINKY_DIP': 19, 'PINKY_TIP': 20
    }

    def __init__(self):
        """Initialize the vision interface."""
        self._camera: Optional[Any] = None
        self._mp_hands: Optional[Any] = None
        self._mp_face_mesh: Optional[Any] = None
        self._mp_pose: Optional[Any] = None
        self._mp_holistic: Optional[Any] = None

        self._check_dependencies()

    def _check_dependencies(self) -> None:
        """Check if required dependencies are available."""
        if not CV2_AVAILABLE:
            print("Warning: OpenCV (cv2) not available. Vision features limited.")
        if not MEDIAPIPE_AVAILABLE:
            print("Warning: MediaPipe not available. Detection features limited.")

    def init_camera(self, camera_index: int = 0) -> bool:
        """
        Initialize camera capture.

        Args:
            camera_index: Camera device index (0 for default webcam)

        Returns:
            True if camera initialized successfully
        """
        if not CV2_AVAILABLE:
            return False

        self._camera = cv2.VideoCapture(camera_index)
        return self._camera.isOpened()

    def release_camera(self) -> None:
        """Release the camera resource."""
        if self._camera is not None:
            self._camera.release()
            self._camera = None

    def capture_frame(self) -> Optional[np.ndarray]:
        """
        Capture a single frame from the camera.

        Returns:
            Frame as numpy array (BGR format) or None if failed
        """
        if self._camera is None or not self._camera.isOpened():
            return None

        ret, frame = self._camera.read()
        return frame if ret else None

    def init_hand_detection(
        self,
        max_hands: int = 2,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5
    ) -> bool:
        """
        Initialize MediaPipe hand detection.

        Args:
            max_hands: Maximum number of hands to detect
            min_detection_confidence: Minimum detection confidence
            min_tracking_confidence: Minimum tracking confidence

        Returns:
            True if initialized successfully
        """
        if not MEDIAPIPE_AVAILABLE:
            return False

        self._mp_hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        return True

    def init_face_mesh(
        self,
        max_faces: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5
    ) -> bool:
        """Initialize MediaPipe face mesh detection."""
        if not MEDIAPIPE_AVAILABLE:
            return False

        self._mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=max_faces,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        return True

    def init_pose_estimation(
        self,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5
    ) -> bool:
        """Initialize MediaPipe pose estimation."""
        if not MEDIAPIPE_AVAILABLE:
            return False

        self._mp_pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        return True

    def detect_hands(self, frame: np.ndarray) -> DetectionResult:
        """
        Detect hands in a frame.

        Args:
            frame: BGR image frame

        Returns:
            DetectionResult with hand landmarks
        """
        result = DetectionResult(
            detection_type=DetectionType.HANDS,
            frame_shape=frame.shape
        )

        if self._mp_hands is None:
            return result

        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._mp_hands.process(rgb_frame)

        if results.multi_hand_landmarks:
            hands = []
            for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                landmarks = [
                    (lm.x, lm.y, lm.z)
                    for lm in hand_landmarks.landmark
                ]

                handedness = 'Unknown'
                confidence = 0.0
                if results.multi_handedness and idx < len(results.multi_handedness):
                    classification = results.multi_handedness[idx].classification
                    if classification and len(classification) > 0:
                        handedness = classification[0].label
                        confidence = classification[0].score

                hands.append(HandLandmarks(
                    landmarks=landmarks,
                    handedness=handedness,
                    confidence=confidence
                ))

            result.hands = hands
            result.raw_results = results

        return result

    def detect_face(self, frame: np.ndarray) -> DetectionResult:
        """
        Detect face mesh in a frame.

        Args:
            frame: BGR image frame

        Returns:
            DetectionResult with face landmarks
        """
        result = DetectionResult(
            detection_type=DetectionType.FACE,
            frame_shape=frame.shape
        )

        if self._mp_face_mesh is None:
            return result

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._mp_face_mesh.process(rgb_frame)

        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                landmarks = [
                    (lm.x, lm.y, lm.z)
                    for lm in face_landmarks.landmark
                ]
                result.face = FaceLandmarks(
                    landmarks=landmarks,
                    confidence=1.0  # Face mesh doesn't provide confidence
                )
                break  # Take first face only

            result.raw_results = results

        return result

    def detect_pose(self, frame: np.ndarray) -> DetectionResult:
        """
        Detect pose in a frame.

        Args:
            frame: BGR image frame

        Returns:
            DetectionResult with pose landmarks
        """
        result = DetectionResult(
            detection_type=DetectionType.POSE,
            frame_shape=frame.shape
        )

        if self._mp_pose is None:
            return result

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._mp_pose.process(rgb_frame)

        if results.pose_landmarks:
            landmarks = [
                (lm.x, lm.y, lm.z)
                for lm in results.pose_landmarks.landmark
            ]
            result.pose = PoseLandmarks(
                landmarks=landmarks,
                confidence=1.0
            )
            result.raw_results = results

        return result

    def is_thumbs_up(self, hand: HandLandmarks) -> bool:
        """
        Check if a hand is making a thumbs up gesture.

        Args:
            hand: HandLandmarks to analyze

        Returns:
            True if thumbs up detected
        """
        if len(hand.landmarks) != 21:
            return False

        # Get relevant landmarks
        thumb_tip = hand.landmarks[self.HAND_LANDMARKS['THUMB_TIP']]
        thumb_mcp = hand.landmarks[self.HAND_LANDMARKS['THUMB_MCP']]
        index_tip = hand.landmarks[self.HAND_LANDMARKS['INDEX_TIP']]
        index_mcp = hand.landmarks[self.HAND_LANDMARKS['INDEX_MCP']]
        middle_tip = hand.landmarks[self.HAND_LANDMARKS['MIDDLE_TIP']]
        ring_tip = hand.landmarks[self.HAND_LANDMARKS['RING_TIP']]
        pinky_tip = hand.landmarks[self.HAND_LANDMARKS['PINKY_TIP']]
        wrist = hand.landmarks[self.HAND_LANDMARKS['WRIST']]

        # Thumb should be extended upward (tip above mcp)
        thumb_up = thumb_tip[1] < thumb_mcp[1]

        # Other fingers should be curled (tips below their mcps)
        fingers_curled = (
            index_tip[1] > index_mcp[1] and
            middle_tip[1] > wrist[1] and
            ring_tip[1] > wrist[1] and
            pinky_tip[1] > wrist[1]
        )

        return thumb_up and fingers_curled

    def draw_landmarks(
        self,
        frame: np.ndarray,
        result: DetectionResult
    ) -> np.ndarray:
        """
        Draw detection landmarks on a frame.

        Args:
            frame: BGR image frame
            result: DetectionResult to visualize

        Returns:
            Frame with landmarks drawn
        """
        if not MEDIAPIPE_AVAILABLE or not CV2_AVAILABLE:
            return frame

        output = frame.copy()
        mp_drawing = mp.solutions.drawing_utils

        if result.detection_type == DetectionType.HANDS and result.raw_results:
            if result.raw_results.multi_hand_landmarks:
                for hand_landmarks in result.raw_results.multi_hand_landmarks:
                    mp_drawing.draw_landmarks(
                        output,
                        hand_landmarks,
                        mp.solutions.hands.HAND_CONNECTIONS
                    )

        elif result.detection_type == DetectionType.FACE and result.raw_results:
            if result.raw_results.multi_face_landmarks:
                for face_landmarks in result.raw_results.multi_face_landmarks:
                    mp_drawing.draw_landmarks(
                        output,
                        face_landmarks,
                        mp.solutions.face_mesh.FACEMESH_TESSELATION
                    )

        elif result.detection_type == DetectionType.POSE and result.raw_results:
            if result.raw_results.pose_landmarks:
                mp_drawing.draw_landmarks(
                    output,
                    result.raw_results.pose_landmarks,
                    mp.solutions.pose.POSE_CONNECTIONS
                )

        return output

    def cleanup(self) -> None:
        """Release all resources."""
        self.release_camera()

        if self._mp_hands:
            self._mp_hands.close()
            self._mp_hands = None

        if self._mp_face_mesh:
            self._mp_face_mesh.close()
            self._mp_face_mesh = None

        if self._mp_pose:
            self._mp_pose.close()
            self._mp_pose = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()
        return False
