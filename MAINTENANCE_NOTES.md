# HERMES Maintenance Notes

Track important warnings, deprecations, and future updates needed.

---

## Active Warnings

### 1. pkg_resources Deprecation (face_recognition_models)
- **Severity:** Low
- **Deadline:** November 2025 (tentative removal)
- **Affected Package:** `face_recognition_models` v0.3.0
- **Issue:** Uses deprecated `pkg_resources` API from setuptools
- **Action Required:** Monitor for `face_recognition` library updates. If not fixed by late 2025:
  - Option A: Pin `setuptools<81` in requirements.txt
  - Option B: Fork and patch `face_recognition_models`
- **Status:** Waiting for upstream fix

### 2. dlib-bin vs dlib Naming Mismatch
- **Severity:** Low
- **Issue:** `pip check` reports `face-recognition requires dlib, which is not installed` because we use `dlib-bin` (pre-built wheel)
- **Impact:** None - functionally equivalent, just different package name
- **Action Required:** None unless `face_recognition` changes its dependency spec
- **Status:** Acceptable

### 3. mediapipe Platform Support
- **Severity:** Medium (pre-existing)
- **Issue:** `mediapipe 0.10.31` reports not supported on this platform
- **Impact:** May affect other HERMES features using mediapipe
- **Action Required:** Check mediapipe releases for Windows compatibility updates
- **Status:** Pre-existing issue, unrelated to face recognition

---

## Dependency Versions (as of 2025-01-26)

| Package | Version | Notes |
|---------|---------|-------|
| face_recognition | 1.3.0 | Last updated 2018, may need fork eventually |
| dlib-bin | 20.0.0 | Pre-built, no CUDA support |
| pyttsx3 | 2.99 | Stable |
| opencv-python | 4.12.0.88 | Current |

---

## Future Considerations

### GPU Acceleration (Optional)
If CPU face recognition proves too slow:
1. Install Visual Studio Build Tools (C++ workload)
2. Install CMake from cmake.org (add to PATH)
3. Install CUDA Toolkit for RTX 4060 Ti
4. Build dlib from source: `pip install dlib --no-binary dlib`
5. Update `face_recognition_interface.py` - will auto-detect CUDA

### face_recognition Library Status
The `face_recognition` library (ageitgey) hasn't been actively maintained since ~2020. Long-term alternatives to monitor:
- `deepface` - More actively maintained, multiple backends
- `insightface` - High accuracy, good GPU support
- Direct `dlib` usage - Skip the wrapper

---

## Changelog

### 2025-01-26
- Added face recognition module (FaceRecognitionInterface)
- Installed: face_recognition, dlib-bin, pyttsx3
- Created: startup_greeter.py, enroll_face.py, setup_autostart.py
- Security audit: No vulnerabilities found
