"""
PSNR, SSIM, LPIPS 계산 스크립트
Raw(GT) vs No Rig / Rig 렌더링 결과 비교
"""

import os
import ssl

# SSL 인증서 우회 (macOS)
ssl._create_default_https_context = ssl._create_unverified_context

import numpy as np
from PIL import Image
from skimage.metrics import peak_signal_noise_ratio as psnr
from skimage.metrics import structural_similarity as ssim

# LPIPS는 선택적 (torch, lpips 필요)
try:
    import torch
    import lpips
    LPIPS_AVAILABLE = True
except ImportError:
    LPIPS_AVAILABLE = False
    print("Warning: lpips not available. Install with: pip install lpips torch")


def load_and_resize(path, target_size=None):
    """이미지 로드 및 리사이즈"""
    img = Image.open(path).convert('RGB')
    if target_size and img.size != target_size:
        img = img.resize(target_size, Image.LANCZOS)
    return np.array(img)


def compute_psnr(img1, img2):
    """PSNR 계산"""
    return psnr(img1, img2, data_range=255)


def compute_ssim(img1, img2):
    """SSIM 계산 (multichannel)"""
    return ssim(img1, img2, channel_axis=2, data_range=255)



def compute_lpips(img1, img2, lpips_fn):
    """LPIPS 계산"""
    # Normalize to [-1, 1]
    img1_tensor = torch.from_numpy(img1).permute(2, 0, 1).unsqueeze(0).float() / 127.5 - 1
    img2_tensor = torch.from_numpy(img2).permute(2, 0, 1).unsqueeze(0).float() / 127.5 - 1

    with torch.no_grad():
        score = lpips_fn(img1_tensor, img2_tensor)
    return score.item()


def main():
    # 경로 설정
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    img_dir = os.path.join(base_dir, "video_picture", "260113")

    # 이미지 ID 목록
    ids = [20, 40, 60, 80, 100, 120]

    # 타겟 크기 (no_rig/rig 해상도)
    target_size = (1177, 1177)

    # LPIPS 모델 로드
    lpips_fn = None
    if LPIPS_AVAILABLE:
        lpips_fn = lpips.LPIPS(net='alex')

    # 결과 저장
    results = {
        'no_rig': {'psnr': [], 'ssim': [], 'lpips': []},
        'rig': {'psnr': [], 'ssim': [], 'lpips': []}
    }

    print("=" * 60)
    print("PSNR / SSIM / LPIPS 계산")
    print("=" * 60)
    print(f"Target size: {target_size}")
    print()

    for img_id in ids:
        # 이미지 로드
        raw_path = os.path.join(img_dir, f"260113-raw_{img_id}.png")
        no_rig_path = os.path.join(img_dir, f"260113-no_rig_{img_id}.png")
        rig_path = os.path.join(img_dir, f"260113-rig_{img_id}.png")

        # Raw를 target_size로 리사이즈
        raw_img = load_and_resize(raw_path, target_size)
        no_rig_img = load_and_resize(no_rig_path)
        rig_img = load_and_resize(rig_path)

        # No Rig vs Raw
        psnr_no_rig = compute_psnr(raw_img, no_rig_img)
        ssim_no_rig = compute_ssim(raw_img, no_rig_img)
        lpips_no_rig = compute_lpips(raw_img, no_rig_img, lpips_fn) if LPIPS_AVAILABLE else None

        results['no_rig']['psnr'].append(psnr_no_rig)
        results['no_rig']['ssim'].append(ssim_no_rig)
        if lpips_no_rig is not None:
            results['no_rig']['lpips'].append(lpips_no_rig)

        # Rig vs Raw
        psnr_rig = compute_psnr(raw_img, rig_img)
        ssim_rig = compute_ssim(raw_img, rig_img)
        lpips_rig = compute_lpips(raw_img, rig_img, lpips_fn) if LPIPS_AVAILABLE else None

        results['rig']['psnr'].append(psnr_rig)
        results['rig']['ssim'].append(ssim_rig)
        if lpips_rig is not None:
            results['rig']['lpips'].append(lpips_rig)

        # 개별 결과 출력
        print(f"[ID {img_id:3d}]")
        print(f"  No Rig - PSNR: {psnr_no_rig:.2f} dB, SSIM: {ssim_no_rig:.4f}", end="")
        if lpips_no_rig is not None:
            print(f", LPIPS: {lpips_no_rig:.4f}")
        else:
            print()
        print(f"  Rig    - PSNR: {psnr_rig:.2f} dB, SSIM: {ssim_rig:.4f}", end="")
        if lpips_rig is not None:
            print(f", LPIPS: {lpips_rig:.4f}")
        else:
            print()
        print()

    # 평균 결과 출력
    print("=" * 60)
    print("평균 결과")
    print("=" * 60)
    print()
    print(f"{'조건':<10} {'PSNR (dB)':<12} {'SSIM':<10} {'LPIPS':<10}")
    print("-" * 42)

    avg_psnr_no_rig = np.mean(results['no_rig']['psnr'])
    avg_ssim_no_rig = np.mean(results['no_rig']['ssim'])
    avg_lpips_no_rig = np.mean(results['no_rig']['lpips']) if results['no_rig']['lpips'] else None

    avg_psnr_rig = np.mean(results['rig']['psnr'])
    avg_ssim_rig = np.mean(results['rig']['ssim'])
    avg_lpips_rig = np.mean(results['rig']['lpips']) if results['rig']['lpips'] else None

    lpips_str_no_rig = f"{avg_lpips_no_rig:.4f}" if avg_lpips_no_rig else "N/A"
    lpips_str_rig = f"{avg_lpips_rig:.4f}" if avg_lpips_rig else "N/A"

    print(f"{'No Rig':<10} {avg_psnr_no_rig:<12.2f} {avg_ssim_no_rig:<10.4f} {lpips_str_no_rig:<10}")
    print(f"{'Rig':<10} {avg_psnr_rig:<12.2f} {avg_ssim_rig:<10.4f} {lpips_str_rig:<10}")
    print()

    # 마크다운 테이블 출력
    print("=" * 60)
    print("마크다운 테이블 (복사용)")
    print("=" * 60)
    print()
    print("| 조건 | PSNR | SSIM | LPIPS |")
    print("|------|------|------|-------|")
    print(f"| No Rig | {avg_psnr_no_rig:.2f} | {avg_ssim_no_rig:.4f} | {lpips_str_no_rig} |")
    print(f"| Rig | {avg_psnr_rig:.2f} | {avg_ssim_rig:.4f} | {lpips_str_rig} |")


if __name__ == "__main__":
    main()
