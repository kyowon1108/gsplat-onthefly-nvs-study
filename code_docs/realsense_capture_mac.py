#!/usr/bin/env python3
"""
RealSense D435 capture using OpenCV (for macOS)
Press SPACE to capture, ESC to quit
"""

import cv2
import numpy as np
from pathlib import Path
import argparse
import time

def find_realsense_camera():
    """Find RealSense camera index"""
    print("Searching for RealSense camera...")

    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            # Try to read a frame
            ret, frame = cap.read()
            if ret:
                print(f"✓ Found camera at index {i}")
                return i
            cap.release()

    print("❌ No camera found!")
    return None

def capture_images(output_dir, num_images=50, camera_index=0):
    """Capture images using OpenCV"""

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Open camera
    print(f"\nOpening camera {camera_index}...")
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print(f"❌ Failed to open camera {camera_index}")
        return 0

    # Set resolution to 1920x1080
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    # Set all camera parameters to AUTO
    print("Setting camera parameters to AUTO...")

    # Auto Exposure
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)  # 0.75 = auto, 0.25 = manual
    print("  Auto Exposure: ON")

    # Auto White Balance
    cap.set(cv2.CAP_PROP_AUTO_WB, 1)  # 1 = auto
    print("  Auto White Balance: ON")

    # Auto Focus (if supported)
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)  # 1 = auto
    print("  Auto Focus: ON")

    # Disable manual brightness/contrast adjustments
    # (let auto exposure handle it)
    try:
        cap.set(cv2.CAP_PROP_BRIGHTNESS, -1)  # -1 often means auto
        cap.set(cv2.CAP_PROP_CONTRAST, -1)
        cap.set(cv2.CAP_PROP_SATURATION, -1)
        cap.set(cv2.CAP_PROP_GAIN, -1)
        print("  Other parameters: AUTO")
    except:
        pass  # Some cameras don't support all parameters

    # Get actual resolution
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))

    print(f"✓ Camera opened!")
    print(f"  Resolution: {width}x{height}")
    print(f"  FPS: {fps}")

    # Warmup
    print("\nWarming up camera...")
    for _ in range(30):
        cap.read()

    print("\n" + "=" * 60)
    print("📷 Capture Mode")
    print("=" * 60)
    print("SPACE: Capture image")
    print("ESC: Quit")
    print(f"Target: {num_images} images")
    print("=" * 60 + "\n")

    captured_count = 0
    frame_id = 0

    try:
        while captured_count < num_images:
            ret, frame = cap.read()

            if not ret:
                print("⚠️ Failed to read frame")
                time.sleep(0.1)
                continue

            # Display preview (resize for display)
            preview = cv2.resize(frame, (960, 540))

            # Add info text
            info_text = f"Captured: {captured_count}/{num_images} | Frame: {frame_id}"
            cv2.putText(preview, info_text, (10, 40),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            cv2.putText(preview, "SPACE: Capture, ESC: Quit", (10, 80),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
            cv2.putText(preview, f"Resolution: {width}x{height}", (10, 510),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 1)

            cv2.imshow('RealSense Capture (OpenCV)', preview)

            key = cv2.waitKey(1) & 0xFF

            if key == ord(' '):  # Space key
                # Save full resolution image
                filename = output_path / f"frame_{captured_count:06d}.jpg"
                cv2.imwrite(str(filename), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                print(f"✅ Captured {captured_count+1}/{num_images}: {filename}")
                captured_count += 1

            elif key == 27:  # ESC key
                print("\n⚠️ Capture interrupted by user")
                break

            frame_id += 1

    except KeyboardInterrupt:
        print("\n⚠️ Capture interrupted by user")

    finally:
        cap.release()
        cv2.destroyAllWindows()

    print(f"\n📸 Capture complete! {captured_count} images saved to {output_dir}")

    # RealSense D435 camera intrinsics @ 1920x1080 (measured)
    # Serial Number: 241222076464, Firmware: 5.17.0.10
    fx = 1364.89
    fy = 1365.10
    cx = 961.75
    cy = 569.93

    print(f"\n📷 RealSense D435 camera intrinsics (1920x1080):")
    print(f"   fx: {fx:.2f}, fy: {fy:.2f}")
    print(f"   cx: {cx:.2f}, cy: {cy:.2f}")
    print(f"   S/N: 241222076464, FW: 5.17.0.10")
    print(f"   Factory calibrated - distortion: k1=k2=p1=p2=0")

    return captured_count

def main():
    parser = argparse.ArgumentParser(description="RealSense capture using OpenCV")
    parser.add_argument("output_dir", help="Directory to save captured images")
    parser.add_argument("--num-images", "-n", type=int, default=50,
                       help="Number of images to capture (default: 50)")
    parser.add_argument("--camera", "-c", type=int, default=None,
                       help="Camera index (default: auto-detect)")

    args = parser.parse_args()

    print("=" * 60)
    print("RealSense D435 Capture (OpenCV Backend)")
    print("=" * 60)

    # Find camera if not specified
    if args.camera is None:
        camera_index = find_realsense_camera()
        if camera_index is None:
            return 1
    else:
        camera_index = args.camera

    try:
        captured_count = capture_images(args.output_dir, args.num_images, camera_index)

        if captured_count > 0:
            print(f"\n🎉 Successfully captured {captured_count} images!")
            print(f"📁 Images saved to: {args.output_dir}")
            print(f"\n🚀 Next step: Process images for 3D reconstruction")

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())
