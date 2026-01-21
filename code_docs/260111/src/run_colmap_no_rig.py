#!/usr/bin/env python3
"""
COLMAP SfM Pipeline (No Rig Constraints)
- Ubuntu 22.04 + COLMAP 3.13 compatible
- GPU acceleration enabled by default
- Real-time log output
"""

import json
import subprocess
import shutil
import argparse
import sys
from pathlib import Path
from typing import Dict, List
import re


class COLMAPNoRigSfM:
    def __init__(self, project_dir: Path, use_gpu: bool = True):
        self.project_dir = Path(project_dir)
        self.images_dir = self.project_dir / "images"
        self.result_dir = self.project_dir / "result" / "no_rig"

        # Result folder structure
        self.images_reorganized_dir = self.result_dir / "images_by_camera"
        self.database_path = self.result_dir / "database.db"
        self.sparse_dir = self.result_dir / "sparse"
        self.use_gpu = use_gpu

    def reorganize_images_by_camera(self) -> Dict[str, Path]:
        """
        Reorganize images from High/Low folders to per-camera folders.
        Original: images/High/f0001-High_Cam01.png
        Target: result/no_rig/images_by_camera/High_Cam01/f0001.png
        """
        print("\n" + "=" * 60)
        print("[1/4] Reorganizing images by camera")
        print("=" * 60)

        camera_folders = {}

        # Create result directory
        self.result_dir.mkdir(parents=True, exist_ok=True)

        # Remove existing reorganized folder
        if self.images_reorganized_dir.exists():
            shutil.rmtree(self.images_reorganized_dir)
        self.images_reorganized_dir.mkdir(parents=True)

        # Pattern: f{frame}-{camera_name}.png
        pattern = re.compile(r'(f\d+)-(.+)\.png')

        for folder in ["High", "Low"]:
            folder_path = self.images_dir / folder
            if not folder_path.exists():
                continue

            for img_file in sorted(folder_path.glob("*.png")):
                match = pattern.match(img_file.name)
                if not match:
                    print(f"  Warning: Skipping {img_file.name} (pattern mismatch)")
                    continue

                frame_id = match.group(1)  # e.g., f0001
                camera_name = match.group(2)  # e.g., High_Cam01

                # Create camera folder if needed
                camera_folder = self.images_reorganized_dir / camera_name
                if camera_name not in camera_folders:
                    camera_folder.mkdir(exist_ok=True)
                    camera_folders[camera_name] = camera_folder

                # Create hard link (to save disk space and keep correct path in COLMAP)
                target = camera_folder / f"{frame_id}.png"
                if not target.exists():
                    target.hardlink_to(img_file.resolve())

        print(f"\nCreated {len(camera_folders)} camera folders:")
        for cam_name in sorted(camera_folders.keys()):
            num_images = len(list(camera_folders[cam_name].glob("*.png")))
            print(f"  - {cam_name}: {num_images} images")

        return camera_folders

    def run_command(self, cmd: List[str], description: str) -> bool:
        """Run a command with real-time output."""
        print(f"\n{'=' * 60}")
        print(f"{description}")
        print("=" * 60)
        print(f"Command: {' '.join(cmd[:5])}...")
        print("-" * 60)

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Real-time output
            for line in process.stdout:
                print(line, end='', flush=True)

            process.wait()

            if process.returncode != 0:
                print(f"\nError: {description} failed with code {process.returncode}")
                return False

            print("-" * 60)
            print(f"✓ {description} completed")
            return True

        except Exception as e:
            print(f"\nException in {description}: {e}")
            return False

    def run_feature_extractor(self) -> bool:
        """Extract features using COLMAP with GPU."""
        # Remove existing database
        if self.database_path.exists():
            self.database_path.unlink()

        cmd = [
            "colmap", "feature_extractor",
            "--database_path", str(self.database_path),
            "--image_path", str(self.images_reorganized_dir),
            "--ImageReader.single_camera_per_folder", "1",
            "--FeatureExtraction.use_gpu", "1" if self.use_gpu else "0",
        ]

        return self.run_command(cmd, "[2/4] Feature Extraction (GPU)")

    def run_sequential_matcher(self) -> bool:
        """Run sequential matching for video sequences."""
        cmd = [
            "colmap", "sequential_matcher",
            "--database_path", str(self.database_path),
            "--FeatureMatching.use_gpu", "1" if self.use_gpu else "0",
            "--SequentialMatching.overlap", "10",
            "--SequentialMatching.quadratic_overlap", "1",
        ]

        return self.run_command(cmd, "[3/4] Sequential Matching (GPU)")

    def run_mapper(self) -> bool:
        """Run mapping WITHOUT rig constraints."""
        # Create sparse output directory
        if self.sparse_dir.exists():
            shutil.rmtree(self.sparse_dir)
        self.sparse_dir.mkdir(parents=True)

        cmd = [
            "colmap", "mapper",
            "--database_path", str(self.database_path),
            "--image_path", str(self.images_reorganized_dir),
            "--output_path", str(self.sparse_dir),
            # No rig constraints - allow refinement
            "--Mapper.ba_refine_focal_length", "1",
            "--Mapper.ba_refine_extra_params", "1",
        ]

        return self.run_command(cmd, "[4/4] Mapper (No Rig Constraints)")

    def run_pipeline(self) -> bool:
        """Run the complete COLMAP SfM pipeline without rig."""
        print("\n" + "=" * 60)
        print("COLMAP 3.13 SfM Pipeline (No Rig)")
        print("=" * 60)
        print(f"Project directory: {self.project_dir}")
        print(f"Result directory:  {self.result_dir}")
        print(f"GPU mode: {'Enabled' if self.use_gpu else 'Disabled'}")

        # Step 1: Reorganize images
        camera_folders = self.reorganize_images_by_camera()
        if not camera_folders:
            print("Error: No images found")
            return False

        # Step 2: Feature extraction
        if not self.run_feature_extractor():
            return False

        # Step 3: Sequential matching
        if not self.run_sequential_matcher():
            return False

        # Step 4: Mapping (no rig)
        if not self.run_mapper():
            return False

        print("\n" + "=" * 60)
        print("Pipeline completed!")
        print("=" * 60)
        print(f"Results saved to: {self.sparse_dir}")

        # List output models
        for model_dir in sorted(self.sparse_dir.glob("*")):
            if model_dir.is_dir():
                cameras = list(model_dir.glob("cameras.*"))
                images = list(model_dir.glob("images.*"))
                points = list(model_dir.glob("points3D.*"))
                print(f"\nModel {model_dir.name}:")
                print(f"  - cameras: {len(cameras)} files")
                print(f"  - images: {len(images)} files")
                print(f"  - points3D: {len(points)} files")

        return True


def main():
    parser = argparse.ArgumentParser(
        description="COLMAP 3.13 SfM Pipeline (No Rig Constraints)"
    )
    parser.add_argument(
        "--project_dir",
        type=str,
        default="/opt/ftp/files/saebit",
        help="Project directory containing images folder"
    )
    parser.add_argument(
        "--no-gpu",
        action="store_true",
        help="Disable GPU acceleration (GPU enabled by default)"
    )

    args = parser.parse_args()

    pipeline = COLMAPNoRigSfM(
        project_dir=Path(args.project_dir),
        use_gpu=not args.no_gpu
    )

    success = pipeline.run_pipeline()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
