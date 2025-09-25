#!/usr/bin/env python3
"""
Intel RealSense D435 Camera Capture for Gaussian Splatting
Captures RGB images with known camera intrinsics
"""

import pyrealsense2 as rs
import numpy as np
import cv2
import os
import argparse
from pathlib import Path
import time

# RealSense D435 intrinsics for 640x480 resolution
D435_INTRINSICS = {
    "width": 640,
    "height": 480,
    "fx": 606.62,
    "fy": 606.71,
    "cx": 320.78,
    "cy": 253.30
}

def setup_realsense():
    """Initialize RealSense pipeline"""
    pipeline = rs.pipeline()
    config = rs.config()

    # Configure streams
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

    # Start streaming
    profile = pipeline.start(config)

    # Get actual intrinsics from the camera
    color_stream = profile.get_stream(rs.stream.color)
    intrinsics = color_stream.as_video_stream_profile().get_intrinsics()

    print(f"📷 RealSense D435 Connected!")
    print(f"   Resolution: {intrinsics.width}x{intrinsics.height}")
    print(f"   Intrinsics: fx={intrinsics.fx:.2f}, fy={intrinsics.fy:.2f}")
    print(f"   Principal: cx={intrinsics.ppx:.2f}, cy={intrinsics.ppy:.2f}")

    return pipeline, intrinsics

def capture_images(output_dir, num_images=50, capture_mode="manual"):
    """Capture images from RealSense D435"""

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    pipeline, intrinsics = setup_realsense()

    captured_count = 0
    frame_id = 0

    print(f"\n🎯 Capture Mode: {capture_mode}")
    if capture_mode == "manual":
        print("   Press SPACE to capture image, ESC to quit")
    else:
        print(f"   Auto-capturing {num_images} images every 0.5 seconds")

    try:
        while captured_count < num_images:
            # Wait for frames
            frames = pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()

            if not color_frame:
                continue

            # Convert to numpy array
            color_image = np.ascontiguousarray(np.array(color_frame.get_data()))

            # Display preview
            preview = cv2.resize(color_image, (480, 360))
            info_text = f"Captured: {captured_count}/{num_images} | Frame: {frame_id}"
            cv2.putText(preview, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            if capture_mode == "manual":
                cv2.putText(preview, "SPACE: Capture, ESC: Quit", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            cv2.imshow('RealSense D435 Capture', preview)

            key = cv2.waitKey(1) & 0xFF

            if capture_mode == "manual":
                if key == ord(' '):  # Space key
                    # Save image
                    filename = output_path / f"frame_{captured_count:06d}.jpg"
                    cv2.imwrite(str(filename), color_image)
                    print(f"✅ Captured: {filename}")
                    captured_count += 1
                elif key == 27:  # ESC key
                    break
            else:  # auto mode
                if frame_id % 15 == 0:  # Capture every 15 frames (0.5 seconds at 30fps)
                    filename = output_path / f"frame_{captured_count:06d}.jpg"
                    cv2.imwrite(str(filename), color_image)
                    print(f"✅ Auto-captured: {filename}")
                    captured_count += 1
                    time.sleep(0.1)  # Brief pause

            frame_id += 1

    except KeyboardInterrupt:
        print("\n⚠️ Capture interrupted by user")

    finally:
        pipeline.stop()
        cv2.destroyAllWindows()

    print(f"\n📸 Capture complete! {captured_count} images saved to {output_dir}")
    return captured_count, intrinsics

def main():
    parser = argparse.ArgumentParser(description="RealSense D435 capture for Gaussian Splatting")
    parser.add_argument("output_dir", help="Directory to save captured images")
    parser.add_argument("--num-images", "-n", type=int, default=50,
                       help="Number of images to capture (default: 50)")
    parser.add_argument("--mode", "-m", choices=["manual", "auto"], default="manual",
                       help="Capture mode: manual (space key) or auto (timed)")

    args = parser.parse_args()

    print("=== Intel RealSense D435 Capture for Gaussian Splatting ===")

    try:
        captured_count, intrinsics = capture_images(args.output_dir, args.num_images, args.mode)

        if captured_count > 0:
            print(f"\n🎉 Successfully captured {captured_count} images!")
            print(f"📁 Images saved to: {args.output_dir}")
            print(f"📷 Camera intrinsics: fx={intrinsics.fx:.2f}, fy={intrinsics.fy:.2f}")
            print(f"   Principal point: cx={intrinsics.ppx:.2f}, cy={intrinsics.ppy:.2f}")
            print(f"\n🚀 Next step: Run clean pipeline to train Gaussian Splatting")

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())
