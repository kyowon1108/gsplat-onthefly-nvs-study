#!/usr/bin/env python3
import os
import subprocess
import sys

def run_command(cmd):
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    print(result.stdout)
    return result

def main():
    base_dir = "/home/kapr/Desktop/gaussian-splatting/data/room2_640480"
    input_dir = os.path.join(base_dir, "input")
    workspace_dir = os.path.join(base_dir, "colmap_workspace")
    database_path = os.path.join(workspace_dir, "database.db")
    sparse_dir = os.path.join(workspace_dir, "sparse")

    # Intel RealSense D435 640x480 camera parameters
    # These are typical values for D435 at 640x480 resolution
    fx=382.613
    fy=382.613
    cx=320.183
    cy=237.712


    print("=== COLMAP Pipeline for Intel RealSense D435 640x480 ===")
    print(f"Input directory: {input_dir}")
    print(f"Workspace directory: {workspace_dir}")
    print(f"Camera parameters: fx={fx}, fy={fy}, cx={cx}, cy={cy}")

    # Step 1: Feature extraction with known camera parameters
    print("\n=== Step 1: Feature Extraction ===")
    cmd = f"""colmap feature_extractor \
        --database_path {database_path} \
        --image_path {input_dir} \
        --ImageReader.single_camera 1 \
        --ImageReader.camera_model PINHOLE \
        --ImageReader.camera_params {fx},{fy},{cx},{cy} \
        --SiftExtraction.max_image_size 1600 \
        --SiftExtraction.max_num_features 16384 \
        --SiftExtraction.estimate_affine_shape 1 \
        --SiftExtraction.domain_size_pooling 1"""
    run_command(cmd)

    # Step 2: Feature matching
    print("\n=== Step 2: Feature Matching ===")
    cmd = f"""colmap exhaustive_matcher \
        --database_path {database_path} \
        --SiftMatching.guided_matching 1 \
        --SiftMatching.max_ratio 0.85 \
        --SiftMatching.max_distance 0.7 \
        --SiftMatching.cross_check 1"""
    run_command(cmd)

    # Step 3: Sparse reconstruction (mapper)
    print("\n=== Step 3: Sparse Reconstruction (Mapper) ===")
    cmd = f"""colmap mapper \
        --database_path {database_path} \
        --image_path {input_dir} \
        --output_path {sparse_dir} \
        --Mapper.ba_refine_focal_length 1 \
        --Mapper.ba_refine_principal_point 0 \
        --Mapper.ba_refine_extra_params 0 \
        --Mapper.init_min_num_inliers 50 \
        --Mapper.extract_colors 1"""
    run_command(cmd)

    print("\n=== COLMAP Processing Complete ===")
    print(f"Sparse reconstruction saved to: {sparse_dir}")

    # Check if sparse reconstruction was successful
    sparse_0_dir = os.path.join(sparse_dir, "0")
    if os.path.exists(sparse_0_dir):
        print(f"\nSparse reconstruction successful!")
        print(f"Model directory: {sparse_0_dir}")

        # List output files
        print("\nGenerated files:")
        for file in os.listdir(sparse_0_dir):
            file_path = os.path.join(sparse_0_dir, file)
            size = os.path.getsize(file_path)
            print(f"  - {file}: {size:,} bytes")
    else:
        print("\nWarning: No sparse reconstruction found in expected location")
        print("Checking sparse directory contents...")
        run_command(f"ls -la {sparse_dir}")

if __name__ == "__main__":
    main()