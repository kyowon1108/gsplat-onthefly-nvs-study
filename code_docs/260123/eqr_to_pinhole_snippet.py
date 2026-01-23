# eqr_to_pinhole.py에서 추출 - get_reference_camera_index() 메서드
# 경로: on-the-fly-nvs/insta360/eqr_to_pinhole.py (lines 311-321)

class EQRToPinholeConverter:
    # ... (다른 메서드 생략)

    def get_reference_camera_index(self) -> int:
        """
        Get the reference camera index based on paper methodology.

        The reference camera is selected as the one with minimum pairwise
        feature distance sum to all other cameras.

        Returns:
            Camera index (4 = High_Cam08, 315°, distance sum = 4.359)
        """
        return 4  # High_Cam08
