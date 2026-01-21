#!/usr/bin/env python3
"""
COLMAP Rig-based SfM Pipeline with Fixed Intrinsics
- Fixed camera intrinsics: fx=960, fy=960, cx=960, cy=960
- Rig with rotation only (translation = 0)
- Based on 2step observation: cameras at single point with different orientations

Ubuntu 22.04 + COLMAP 3.13 compatible
"""

import json
import subprocess
import shutil
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import re
import numpy as np


def quat_to_rotmat(q):
    """Quaternion [w,x,y,z] to rotation matrix."""
    w, x, y, z = q
    return np.array([
        [1 - 2*y*y - 2*z*z, 2*x*y - 2*z*w, 2*x*z + 2*y*w],
        [2*x*y + 2*z*w, 1 - 2*x*x - 2*z*z, 2*y*z - 2*x*w],
        [2*x*z - 2*y*w, 2*y*z + 2*x*w, 1 - 2*x*x - 2*y*y]
    ])


def rotmat_to_quat(R):
    """Rotation matrix to quaternion [w,x,y,z]."""
    trace = np.trace(R)
    if trace > 0:
        s = 0.5 / np.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (R[2, 1] - R[1, 2]) * s
        y = (R[0, 2] - R[2, 0]) * s
        z = (R[1, 0] - R[0, 1]) * s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
        w = (R[2, 1] - R[1, 2]) / s
        x = 0.25 * s
        y = (R[0, 1] + R[1, 0]) / s
        z = (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
        w = (R[0, 2] - R[2, 0]) / s
        x = (R[0, 1] + R[1, 0]) / s
        y = 0.25 * s
        z = (R[1, 2] + R[2, 1]) / s
    else:
        s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
        w = (R[1, 0] - R[0, 1]) / s
        x = (R[0, 2] + R[2, 0]) / s
        y = (R[1, 2] + R[2, 1]) / s
        z = 0.25 * s
    q = np.array([w, x, y, z])
    return (q / np.linalg.norm(q)).tolist()


class COLMAPRigFixedIntrinsics:
    def __init__(self, project_dir: Path, use_gpu: bool = True):
        self.project_dir = Path(project_dir)
        self.images_dir = self.project_dir / "images"
        self.blender_rig_path = self.project_dir / "blender_rig.json"
        self.result_dir = self.project_dir / "result" / "rig_fixed_intrinsics"

        # Result folder structure
        self.images_reorganized_dir = self.result_dir / "images_by_camera"
        self.database_path = self.result_dir / "database.db"
        self.sparse_dir = self.result_dir / "sparse"
        self.rig_config_path = self.result_dir / "rig_config.json"
        self.use_gpu = use_gpu

        # Fixed camera intrinsics (from 2step observation)
        # PINHOLE model: fx, fy, cx, cy
        self.camera_model = "PINHOLE"
        self.camera_params = "960,960,960,960"  # fx, fy, cx, cy (all 960)

    def reorganize_images_by_camera(self) -> Dict[str, Path]:
        """Reorganize images from High/Low folders to per-camera folders."""
        print("\n" + "=" * 60)
        print("[1/6] Reorganizing images by camera")
        print("=" * 60)

        camera_folders = {}
        self.result_dir.mkdir(parents=True, exist_ok=True)

        if self.images_reorganized_dir.exists():
            shutil.rmtree(self.images_reorganized_dir)
        self.images_reorganized_dir.mkdir(parents=True)

        pattern = re.compile(r'(f\d+)-(.+)\.png')

        for folder in ["High", "Low"]:
            folder_path = self.images_dir / folder
            if not folder_path.exists():
                continue

            for img_file in sorted(folder_path.glob("*.png")):
                match = pattern.match(img_file.name)
                if not match:
                    continue

                frame_id = match.group(1)
                camera_name = match.group(2)

                camera_folder = self.images_reorganized_dir / camera_name
                if camera_name not in camera_folders:
                    camera_folder.mkdir(exist_ok=True)
                    camera_folders[camera_name] = camera_folder

                target = camera_folder / f"{frame_id}.png"
                if not target.exists():
                    target.hardlink_to(img_file.resolve())

        print(f"\nCreated {len(camera_folders)} camera folders:")
        for cam_name in sorted(camera_folders.keys()):
            num_images = len(list(camera_folders[cam_name].glob("*.png")))
            print(f"  - {cam_name}: {num_images} images")

        return camera_folders

    def compute_relative_rotation(self, ref_rot: List[float], cam_rot: List[float]) -> List[float]:
        """
        Compute relative rotation: cam_from_ref
        Both rotations are Blender quaternions (cam_to_world)

        cam_from_ref = cam_from_world @ world_from_ref
                     = R_cam.T @ R_ref
        """
        R_ref = quat_to_rotmat(ref_rot)
        R_cam = quat_to_rotmat(cam_rot)

        # Relative rotation in Blender coordinates
        R_rel = R_cam.T @ R_ref

        # Convert Blender to OpenCV/COLMAP coordinate system
        # Blender: +X right, +Y forward, +Z up
        # OpenCV: +X right, +Y down, +Z forward
        T = np.diag([1, -1, -1])
        R_rel_cv = T @ R_rel @ T

        return rotmat_to_quat(R_rel_cv)

    def create_rig_config(self, camera_folders: Dict[str, Path]) -> None:
        """
        Create COLMAP rig_config.json with:
        - Rotation from Blender
        - Translation = 0 (all cameras at same point)
        """
        print("\n" + "=" * 60)
        print("[2/6] Creating rig config (rotation only, translation=0)")
        print("=" * 60)

        with open(self.blender_rig_path, 'r') as f:
            blender_rig = json.load(f)

        # Find reference camera
        ref_camera_name = None
        ref_rotation = None

        for group in blender_rig:
            for cam in group["cameras"]:
                if cam["name"] in camera_folders:
                    ref_camera_name = cam["name"]
                    ref_rotation = cam["rotation"]
                    break
            if ref_camera_name:
                break

        if not ref_camera_name:
            raise ValueError("No valid reference camera found")

        print(f"Reference camera: {ref_camera_name}")

        cameras = []
        for group in blender_rig:
            for cam in group["cameras"]:
                cam_name = cam["name"]

                if cam_name not in camera_folders:
                    print(f"  Warning: Camera {cam_name} not found in images, skipping")
                    continue

                if cam_name == ref_camera_name:
                    camera_entry = {
                        "image_prefix": f"{cam_name}/",
                        "ref_sensor": True
                    }
                else:
                    # Compute relative rotation
                    rel_rotation = self.compute_relative_rotation(ref_rotation, cam["rotation"])

                    camera_entry = {
                        "image_prefix": f"{cam_name}/",
                        "cam_from_rig_rotation": rel_rotation,
                        "cam_from_rig_translation": [0.0, 0.0, 0.0]  # Translation = 0
                    }

                cameras.append(camera_entry)
                print(f"  Added camera: {cam_name}")

        rig_config = [{"cameras": cameras}]

        with open(self.rig_config_path, 'w') as f:
            json.dump(rig_config, f, indent=2)

        print(f"\nSaved rig config to {self.rig_config_path}")
        print(f"Total cameras: {len(cameras)}")
        print(f"Translation for all cameras: [0, 0, 0]")

    def run_command(self, cmd: List[str], description: str) -> bool:
        """Run a command with real-time output."""
        print(f"\n{'=' * 60}")
        print(f"{description}")
        print("=" * 60)
        print(f"Command: {' '.join(cmd[:6])}...")
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
        """Extract features with fixed camera intrinsics."""
        if self.database_path.exists():
            self.database_path.unlink()

        cmd = [
            "colmap", "feature_extractor",
            "--database_path", str(self.database_path),
            "--image_path", str(self.images_reorganized_dir),
            "--ImageReader.single_camera_per_folder", "1",
            "--ImageReader.camera_model", self.camera_model,
            "--ImageReader.camera_params", self.camera_params,
            "--FeatureExtraction.use_gpu", "1" if self.use_gpu else "0",
        ]

        print(f"\nFixed camera intrinsics:")
        print(f"  Model: {self.camera_model}")
        print(f"  Params: fx=960, fy=960, cx=960, cy=960")

        return self.run_command(cmd, "[3/6] Feature Extraction (Fixed Intrinsics, GPU)")

    def run_rig_configurator(self) -> bool:
        """Apply rig configuration to database."""
        cmd = [
            "colmap", "rig_configurator",
            "--database_path", str(self.database_path),
            "--rig_config_path", str(self.rig_config_path),
        ]

        return self.run_command(cmd, "[4/6] Rig Configurator")

    def run_sequential_matcher(self) -> bool:
        """Run sequential matching with rig verification."""
        cmd = [
            "colmap", "sequential_matcher",
            "--database_path", str(self.database_path),
            "--FeatureMatching.use_gpu", "1" if self.use_gpu else "0",
            "--FeatureMatching.rig_verification", "1",
            "--SequentialMatching.overlap", "10",
            "--SequentialMatching.quadratic_overlap", "1",
        ]

        return self.run_command(cmd, "[5/6] Sequential Matching (GPU + Rig Verification)")

    def run_mapper(self) -> bool:
        """Run mapping with rig constraints and fixed intrinsics."""
        if self.sparse_dir.exists():
            shutil.rmtree(self.sparse_dir)
        self.sparse_dir.mkdir(parents=True)

        cmd = [
            "colmap", "mapper",
            "--database_path", str(self.database_path),
            "--image_path", str(self.images_reorganized_dir),
            "--output_path", str(self.sparse_dir),
            # Rig constraints - keep rig fixed
            "--Mapper.ba_refine_sensor_from_rig", "0",
            # Camera intrinsics - keep fixed
            "--Mapper.ba_refine_focal_length", "0",
            "--Mapper.ba_refine_principal_point", "0",
            "--Mapper.ba_refine_extra_params", "0",
        ]

        return self.run_command(cmd, "[6/6] Mapper (Rig + Fixed Intrinsics)")

    def run_pipeline(self) -> bool:
        """Run the complete pipeline."""
        print("\n" + "=" * 60)
        print("COLMAP 3.13 Rig SfM - Fixed Intrinsics")
        print("=" * 60)
        print(f"Project directory: {self.project_dir}")
        print(f"Result directory:  {self.result_dir}")
        print(f"GPU mode: {'Enabled' if self.use_gpu else 'Disabled'}")
        print(f"\nCamera settings:")
        print(f"  Model: {self.camera_model}")
        print(f"  fx=960, fy=960, cx=960, cy=960")
        print(f"\nRig settings:")
        print(f"  Rotation: from blender_rig.json")
        print(f"  Translation: [0, 0, 0] (single point)")

        camera_folders = self.reorganize_images_by_camera()
        if not camera_folders:
            print("Error: No images found")
            return False

        self.create_rig_config(camera_folders)

        if not self.run_feature_extractor():
            return False

        if not self.run_rig_configurator():
            return False

        if not self.run_sequential_matcher():
            return False

        if not self.run_mapper():
            return False

        print("\n" + "=" * 60)
        print("Pipeline completed!")
        print("=" * 60)
        print(f"Results saved to: {self.sparse_dir}")

        # Analyze result
        for model_dir in sorted(self.sparse_dir.glob("*")):
            if model_dir.is_dir():
                print(f"\nModel {model_dir.name}:")
                # Run model_analyzer
                subprocess.run([
                    "colmap", "model_analyzer",
                    "--path", str(model_dir)
                ], capture_output=False)

        return True


def main():
    parser = argparse.ArgumentParser(
        description="COLMAP Rig SfM with Fixed Intrinsics"
    )
    parser.add_argument(
        "--project_dir",
        type=str,
        default="/opt/ftp/files/saebit",
        help="Project directory"
    )
    parser.add_argument(
        "--no-gpu",
        action="store_true",
        help="Disable GPU acceleration"
    )

    args = parser.parse_args()

    pipeline = COLMAPRigFixedIntrinsics(
        project_dir=Path(args.project_dir),
        use_gpu=not args.no_gpu
    )

    success = pipeline.run_pipeline()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
