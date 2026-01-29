"""
HERMES Face Enrollment Utility
Captures face images and enrolls them for recognition.

Usage:
    python scripts/enroll_face.py --name "Gracia"
    python scripts/enroll_face.py --name "Gracia" --samples 5
    python scripts/enroll_face.py --name "Gracia" --camera 0
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
from sensors.face_recognition_interface import FaceRecognitionInterface


def main():
    parser = argparse.ArgumentParser(description="Enroll a face for HERMES recognition")
    parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="Name to associate with this face"
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=5,
        help="Number of face samples to capture (default: 5)"
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="Camera index to use (default: 0)"
    )
    args = parser.parse_args()

    print(f"\n{'='*50}")
    print(f"HERMES Face Enrollment")
    print(f"{'='*50}")
    print(f"Enrolling: {args.name}")
    print(f"Samples to capture: {args.samples}")
    print(f"Camera index: {args.camera}")
    print(f"{'='*50}\n")

    # Initialize face recognition
    face_rec = FaceRecognitionInterface()

    # Initialize camera
    print("Opening camera...")
    cap = cv2.VideoCapture(args.camera)

    if not cap.isOpened():
        print(f"Error: Could not open camera {args.camera}")
        print("Try a different camera index with --camera")
        return 1

    # Set camera properties for better quality
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("\nInstructions:")
    print("  - Position your face in the center of the frame")
    print("  - Press SPACE to capture a sample")
    print("  - Vary your angle/expression between captures")
    print("  - Press Q to quit early")
    print("  - Press R to reset and start over")
    print()

    samples_captured = 0
    initial_count = len(face_rec.encodings.get(args.name, []))

    try:
        while samples_captured < args.samples:
            ret, frame = cap.read()
            if not ret:
                print("Error: Could not read frame")
                break

            # Create display frame with status
            display = frame.copy()

            # Draw guide rectangle for face positioning
            h, w = frame.shape[:2]
            cx, cy = w // 2, h // 2
            rect_size = 200
            cv2.rectangle(
                display,
                (cx - rect_size, cy - rect_size),
                (cx + rect_size, cy + rect_size),
                (0, 255, 0),
                2
            )

            # Add status text
            status = f"Samples: {samples_captured}/{args.samples} | Press SPACE to capture"
            cv2.putText(
                display, status, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
            )
            cv2.putText(
                display, f"Enrolling: {args.name}", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2
            )
            cv2.putText(
                display, "Q=Quit | R=Reset", (10, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1
            )

            cv2.imshow("HERMES Face Enrollment", display)

            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                print("\nQuitting...")
                break
            elif key == ord('r'):
                print("\nResetting enrollment...")
                face_rec.remove_enrollment(args.name)
                samples_captured = 0
                print("Enrollment reset. Start capturing again.")
            elif key == ord(' '):
                # Convert BGR to RGB for face_recognition
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Attempt enrollment
                print(f"\nCapturing sample {samples_captured + 1}...")

                if face_rec.enroll_face(args.name, rgb_frame):
                    samples_captured += 1
                    print(f"Sample {samples_captured}/{args.samples} captured!")

                    # Flash green to indicate success
                    success_frame = display.copy()
                    cv2.rectangle(success_frame, (0, 0), (w, h), (0, 255, 0), 10)
                    cv2.imshow("HERMES Face Enrollment", success_frame)
                    cv2.waitKey(200)
                else:
                    # Flash red to indicate failure
                    fail_frame = display.copy()
                    cv2.rectangle(fail_frame, (0, 0), (w, h), (0, 0, 255), 10)
                    cv2.putText(
                        fail_frame, "No face detected - try again",
                        (cx - 150, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2
                    )
                    cv2.imshow("HERMES Face Enrollment", fail_frame)
                    cv2.waitKey(500)

    finally:
        cap.release()
        cv2.destroyAllWindows()

    # Summary
    final_count = len(face_rec.encodings.get(args.name, []))
    new_samples = final_count - initial_count

    print(f"\n{'='*50}")
    print(f"Enrollment Complete")
    print(f"{'='*50}")
    print(f"Name: {args.name}")
    print(f"New samples captured: {new_samples}")
    print(f"Total samples for {args.name}: {final_count}")
    print(f"Encodings saved to: {face_rec.encodings_path}")
    print(f"{'='*50}\n")

    if final_count > 0:
        print("You can now test recognition with: python startup_greeter.py --timeout 15")
        return 0
    else:
        print("No samples captured. Please try again.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
