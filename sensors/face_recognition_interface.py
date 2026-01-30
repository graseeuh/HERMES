"""
HERMES Face Recognition Interface
Wrapper for the face_recognition library to identify enrolled users.
Uses CNN model with CUDA acceleration when available (e.g., RTX 4060 Ti).

Security Note:
- Face encodings are stored using numpy's .npz format (secure, no code execution)
- Biometric data is encrypted at rest using Fernet symmetric encryption
- Encryption key stored in system keyring (Windows Credential Manager)
- Previous pickle format (.pkl) is automatically migrated and deleted
"""

import base64
import json
import os
import secrets
from pathlib import Path
from typing import Optional
import numpy as np

# Encryption support
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

# Keyring for secure key storage
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False


# Constants for key management
KEYRING_SERVICE = "HERMES_FaceRecognition"
KEYRING_KEY_NAME = "encryption_key"

try:
    import face_recognition
except ImportError:
    raise ImportError(
        "face_recognition library not installed. "
        "Install with: pip install face_recognition dlib"
    )


def _get_or_create_encryption_key() -> Optional[bytes]:
    """
    Get or create the encryption key for face encodings.

    Key storage priority:
    1. System keyring (Windows Credential Manager, macOS Keychain, etc.)
    2. Environment variable HERMES_FACE_KEY (base64 encoded)
    3. Generate and store new key

    Returns:
        Fernet key bytes or None if encryption not available
    """
    if not CRYPTO_AVAILABLE:
        return None

    # Try to get from keyring first (most secure)
    if KEYRING_AVAILABLE:
        try:
            stored_key = keyring.get_password(KEYRING_SERVICE, KEYRING_KEY_NAME)
            if stored_key:
                return base64.urlsafe_b64decode(stored_key.encode())
        except (keyring.errors.KeyringError, ValueError):
            pass  # Fall through to other methods

    # Try environment variable
    env_key = os.environ.get('HERMES_FACE_KEY')
    if env_key:
        try:
            return base64.urlsafe_b64decode(env_key.encode())
        except ValueError:
            pass

    # Generate new key and try to store it
    new_key = Fernet.generate_key()

    if KEYRING_AVAILABLE:
        try:
            keyring.set_password(
                KEYRING_SERVICE,
                KEYRING_KEY_NAME,
                base64.urlsafe_b64encode(new_key).decode()
            )
            print("Generated and stored new encryption key in system keyring")
            return new_key
        except keyring.errors.KeyringError:
            pass

    # Last resort: warn user and return the key
    # In production, you might want to require keyring or env var
    print("Warning: Could not store encryption key securely.")
    print(f"Set HERMES_FACE_KEY environment variable to: {base64.urlsafe_b64encode(new_key).decode()}")
    return new_key


def _encrypt_data(data: bytes, key: bytes) -> bytes:
    """Encrypt data using Fernet symmetric encryption."""
    if not CRYPTO_AVAILABLE:
        return data
    f = Fernet(key)
    return f.encrypt(data)


def _decrypt_data(encrypted_data: bytes, key: bytes) -> bytes:
    """Decrypt data using Fernet symmetric encryption."""
    if not CRYPTO_AVAILABLE:
        return encrypted_data
    f = Fernet(key)
    return f.decrypt(encrypted_data)


def _check_cuda_available() -> bool:
    """Check if CUDA is available for dlib/face_recognition."""
    try:
        import dlib
        return dlib.DLIB_USE_CUDA and dlib.cuda.get_num_devices() > 0
    except (ImportError, AttributeError, RuntimeError):
        # ImportError: dlib not installed
        # AttributeError: dlib doesn't have CUDA support compiled
        # RuntimeError: CUDA initialization failed
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
            encodings_path: Path to store face encodings. Defaults to data/face_encodings.npz
            tolerance: How strict the face matching is. Lower = stricter. Default 0.6
                       Must be between 0.0 and 1.0.
            model: Face detection model - 'cnn' (GPU) or 'hog' (CPU).
                   Defaults to 'cnn' if CUDA available, else 'hog'.
        """
        # Validate tolerance
        if not 0.0 <= tolerance <= 1.0:
            raise ValueError(f"Tolerance must be between 0.0 and 1.0, got {tolerance}")

        if encodings_path is None:
            # Default to data/face_encodings.npz relative to project root
            project_root = Path(__file__).parent.parent
            self.encodings_path = project_root / "data" / "face_encodings.npz"
        else:
            self.encodings_path = Path(encodings_path)
            # Ensure .npz extension for security
            if self.encodings_path.suffix == '.pkl':
                self.encodings_path = self.encodings_path.with_suffix('.npz')

        # Ensure data directory exists
        self.encodings_path.parent.mkdir(parents=True, exist_ok=True)

        self.tolerance = tolerance
        self.encodings: dict[str, list[np.ndarray]] = {}

        # Initialize encryption
        self._encryption_key = _get_or_create_encryption_key()
        if self._encryption_key:
            print("Biometric data encryption: ENABLED")
        else:
            print("Warning: Biometric data encryption not available. Install 'cryptography' package.")

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

    def _migrate_pickle_file(self) -> bool:
        """
        Migrate old pickle format to secure numpy format.

        Returns:
            True if migration occurred, False otherwise
        """
        # Check for old pickle file
        old_pkl_path = self.encodings_path.with_suffix('.pkl')
        if not old_pkl_path.exists():
            return False

        print(f"Found legacy pickle file, migrating to secure format...")

        try:
            # Load from pickle (one-time only for migration)
            import pickle
            with open(old_pkl_path, 'rb') as f:
                loaded_data = pickle.load(f)

            if isinstance(loaded_data, dict):
                self.encodings = {}
                for name, enc_list in loaded_data.items():
                    if isinstance(name, str) and isinstance(enc_list, list):
                        self.encodings[name] = enc_list

                # Save in new secure format
                self._save_encodings()

                # Remove old pickle file (security: prevents future pickle loading)
                old_pkl_path.unlink()
                print(f"Migration complete. Old pickle file removed for security.")
                return True

        except Exception as e:
            print(f"Warning: Could not migrate pickle file: {e}")
            print("Starting fresh for security reasons.")

        return False

    def _load_encodings(self) -> None:
        """Load face encodings from disk using secure, encrypted numpy format."""
        import io

        self.encodings = {}

        # First, check for and migrate any old pickle file
        if self._migrate_pickle_file():
            return  # Migration already loaded the encodings

        if not self.encodings_path.exists():
            print("No existing face encodings found (first run)")
            return

        # Check if file is empty
        if self.encodings_path.stat().st_size == 0:
            print("Encodings file is empty, starting fresh")
            return

        try:
            # Read raw data
            with open(self.encodings_path, 'rb') as f:
                data = f.read()

            # Decrypt if encryption is available
            if self._encryption_key:
                try:
                    data = _decrypt_data(data, self._encryption_key)
                except Exception as e:
                    print(f"Warning: Could not decrypt encodings (wrong key?): {e}")
                    print("Starting fresh - previous face enrollments lost")
                    self.encodings = {}
                    return

            # Load from numpy format (from bytes buffer)
            buffer = io.BytesIO(data)
            with np.load(buffer, allow_pickle=False) as npz_data:
                # Load the index (list of names and their encoding counts)
                if '_index' not in npz_data:
                    print("Warning: Invalid encodings format (no index), starting fresh")
                    return

                index = json.loads(str(npz_data['_index']))

                # Reconstruct the encodings dict
                for name, count in index.items():
                    self.encodings[name] = []
                    for i in range(count):
                        key = f"{name}_{i}"
                        if key in npz_data:
                            self.encodings[name].append(npz_data[key])

            # Validate we got something
            valid_count = sum(1 for encs in self.encodings.values() if encs)
            if valid_count > 0:
                print(f"Loaded {valid_count} enrolled face(s)")
            else:
                print("No valid encodings found in file")
                self.encodings = {}

        except (OSError, ValueError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load encodings ({type(e).__name__}): {e}")
            self.encodings = {}

    def _save_encodings(self) -> None:
        """Save face encodings to disk using secure, encrypted numpy format."""
        import io

        # Ensure directory exists
        self.encodings_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Build arrays dict for numpy.savez_compressed
            arrays = {}

            # Create an index mapping names to their encoding counts
            index = {name: len(encs) for name, encs in self.encodings.items()}
            arrays['_index'] = np.array(json.dumps(index))

            # Save each encoding as a separate array
            for name, enc_list in self.encodings.items():
                for i, encoding in enumerate(enc_list):
                    arrays[f"{name}_{i}"] = np.asarray(encoding)

            # Save to a bytes buffer first
            buffer = io.BytesIO()
            np.savez_compressed(buffer, **arrays)
            data = buffer.getvalue()

            # Encrypt if available
            if self._encryption_key:
                data = _encrypt_data(data, self._encryption_key)

            # Write to file
            with open(self.encodings_path, 'wb') as f:
                f.write(data)

        except (OSError, ValueError) as e:
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
