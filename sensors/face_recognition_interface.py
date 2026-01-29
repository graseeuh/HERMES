"""
HERMES Face Recognition Interface
Wrapper for the face_recognition library to identify enrolled users.
Uses CNN model with CUDA acceleration when available (e.g., RTX 4060 Ti).
"""

import pickle
from pathlib import Path
from typing import Optional
import numpy as np

try:
    import face_recognition
except ImportError:
    raise ImportError(
        "face_recognition library not installed. "
        "Install with: pip install face_recognition dlib"
    )


def _check_cuda_available() -> bool:
    """Check if CUDA is available for dlib/face_recognition."""
    try:
        import dlib
        return dlib.DLIB_USE_CUDA and dlib.cuda.get_num_devices() > 0
    except Exception:
        return False


class FaceRecognitionInterface:
    """
    Face recognition wrapper for HERMES.
    Handles enrollment and recognition of faces.
    Uses CNN model with GPU acceleration when CUDA is available.
    """

    def __init__(
        self,
        encodings_path: Optional[str] = None,
        tolerance: float = 0.6,
        model: Optional[str] = None
    ):
        """
        Initialize the face recognition interface.

        Args:
            encodings_path: Path to store face encodings. Defaults to data/face_encodings.pkl
            tolerance: How strict the face matching is. Lower = stricter. Default 0.6
            model: Face detection model - 'cnn' (GPU) or 'hog' (CPU).
                   Defaults to 'cnn' if CUDA available, else 'hog'.
        """
        if encodings_path is None:
            # Default to data/face_encodings.pkl relative to project root
            project_root = Path(__file__).parent.parent
            self.encodings_path = project_root / "data" / "face_encodings.pkl"
        else:
            self.encodings_path = Path(encodings_path)

        # Ensure data directory exists
        self.encodings_path.parent.mkdir(parents=True, exist_ok=True)

        self.tolerance = tolerance
        self.encodings: dict[str, list[np.ndarray]] = {}

        # Determine face detection model
        self.cuda_available = _check_cuda_available()
        if model is not None:
            self.model = model
        else:
            # Default to CNN if CUDA is available (leverages GPU)
            self.model = 'cnn' if self.cuda_available else 'hog'

        if self.cuda_available:
            print(f"CUDA detected - using CNN model with GPU acceleration")
        else:
            print(f"CUDA not available - using {self.model.upper()} model (CPU)")

        # Load existing encodings if available
        self._load_encodings()

    def _load_encodings(self) -> None:
        """Load face encodings from disk with robust error handling."""
        self.encodings = {}

        if not self.encodings_path.exists():
            print("No existing face encodings found (first run)")
            return

        # Check if file is empty
        if self.encodings_path.stat().st_size == 0:
            print("Encodings file is empty, starting fresh")
            return

        try:
            with open(self.encodings_path, 'rb') as f:
                loaded_data = pickle.load(f)

            # Validate loaded data
            if not isinstance(loaded_data, dict):
                print(f"Warning: Invalid encodings format, starting fresh")
                return

            # Validate each entry
            valid_encodings = {}
            for name, enc_list in loaded_data.items():
                if isinstance(name, str) and isinstance(enc_list, list) and len(enc_list) > 0:
                    valid_encodings[name] = enc_list

            self.encodings = valid_encodings

            if self.encodings:
                print(f"Loaded {len(self.encodings)} enrolled face(s)")
            else:
                print("No valid encodings found in file")

        except pickle.UnpicklingError as e:
            print(f"Warning: Corrupted encodings file, starting fresh: {e}")
            self.encodings = {}
        except EOFError:
            print("Warning: Incomplete encodings file, starting fresh")
            self.encodings = {}
        except Exception as e:
            print(f"Warning: Could not load encodings ({type(e).__name__}): {e}")
            self.encodings = {}

    def _save_encodings(self) -> None:
        """Save face encodings to disk."""
        # Ensure directory exists
        self.encodings_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.encodings_path, 'wb') as f:
                pickle.dump(self.encodings, f)
        except Exception as e:
            print(f"Error saving encodings: {e}")
            raise

    def enroll_face(self, name: str, image: np.ndarray) -> bool:
        """
        Enroll a face with the given name using CNN model for better accuracy.

        Args:
            name: Name to associate with this face
            image: RGB image array containing a face

        Returns:
            True if enrollment successful, False otherwise
        """
        try:
            # Find face locations using CNN model (GPU accelerated)
            face_locations = face_recognition.face_locations(image, model=self.model)

            if not face_locations:
                print("No face detected in image")
                return False

            if len(face_locations) > 1:
                print(f"Warning: {len(face_locations)} faces detected, using the first one")

            # Get encoding for the first face
            encodings = face_recognition.face_encodings(image, face_locations)

            if not encodings:
                print("Could not encode face")
                return False

            encoding = encodings[0]

            # Add to our stored encodings
            if name not in self.encodings:
                self.encodings[name] = []

            self.encodings[name].append(encoding)
            self._save_encodings()

            print(f"Enrolled face for '{name}' ({len(self.encodings[name])} sample(s) total)")
            return True

        except Exception as e:
            print(f"Error during face enrollment: {e}")
            return False

    def recognize_face(self, image: np.ndarray) -> Optional[str]:
        """
        Recognize a face in the given image using CNN model for better accuracy.

        Args:
            image: RGB image array containing a face

        Returns:
            Name of recognized person, or None if no match
        """
        if not self.encodings:
            return None

        try:
            # Find faces using CNN model (GPU accelerated)
            face_locations = face_recognition.face_locations(image, model=self.model)

            if not face_locations:
                return None

            # Get encodings for detected faces
            face_encodings = face_recognition.face_encodings(image, face_locations)

            if not face_encodings:
                return None

            # Check each detected face against enrolled faces
            for face_encoding in face_encodings:
                # Compare against all enrolled faces
                for name, stored_encodings in self.encodings.items():
                    # Check if this face matches any of the stored encodings for this name
                    matches = face_recognition.compare_faces(
                        stored_encodings,
                        face_encoding,
                        tolerance=self.tolerance
                    )

                    if any(matches):
                        # Calculate average distance for confidence
                        distances = face_recognition.face_distance(stored_encodings, face_encoding)
                        avg_distance = np.mean(distances)
                        confidence = 1 - avg_distance
                        print(f"Recognized {name} (confidence: {confidence:.2%})")
                        return name

            return None

        except Exception as e:
            print(f"Error during face recognition: {e}")
            return None

    def get_enrolled_names(self) -> list[str]:
        """
        Get list of all enrolled user names.

        Returns:
            List of enrolled names
        """
        return list(self.encodings.keys())

    def remove_enrollment(self, name: str) -> bool:
        """
        Remove all face encodings for a given name.

        Args:
            name: Name to remove

        Returns:
            True if removed, False if name wasn't enrolled
        """
        if name in self.encodings:
            del self.encodings[name]
            self._save_encodings()
            print(f"Removed enrollment for '{name}'")
            return True
        return False

    def clear_all_enrollments(self) -> None:
        """Remove all enrolled faces."""
        self.encodings = {}
        self._save_encodings()
        print("Cleared all face enrollments")

    def get_model_info(self) -> dict:
        """Get information about the current model configuration."""
        return {
            'model': self.model,
            'cuda_available': self.cuda_available,
            'tolerance': self.tolerance,
            'enrolled_count': len(self.encodings),
            'encodings_path': str(self.encodings_path)
        }
