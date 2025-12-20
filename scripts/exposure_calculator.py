#!/usr/bin/env python
"""
AI Color Grade - Phase 2.2 露出補正計算モジュール
ROI統計値から露出補正パラメータを算出

機能:
- 顔ROI輝度から目標露出を計算
- 肌トーン目標値への補正量算出
- 全体バランスを考慮した最終補正値決定
"""

import math

# =============================================================================
# 定数
# =============================================================================

# 肌トーン目標値（Rec.709 / sRGB空間での理想的な肌の輝度）
# 一般的に肌は中間グレーより少し明るい（約0.45-0.55）
SKIN_TONE_TARGET_LUMA = 0.50  # 目標輝度（0-1スケール）
SKIN_TONE_TOLERANCE = 0.05   # 許容範囲（±5%は補正しない）

# S-Log3固有の設定
SLOG3_MIDDLE_GRAY = 0.41     # S-Log3での18%グレー位置
SLOG3_SKIN_TYPICAL = 0.35    # S-Log3での典型的な肌輝度

# 露出補正の制限
MAX_EXPOSURE_EV = 2.0        # 最大補正量（+方向）
MIN_EXPOSURE_EV = -1.0       # 最大補正量（-方向）

# 顔検出時の重み付け
FACE_WEIGHT = 0.7            # 顔検出時、顔領域の重み
GLOBAL_WEIGHT = 0.3          # 顔検出時、全体の重み

# コントラスト補正
CONTRAST_BASE = 1.25         # S-Log3用ベースコントラスト
CONTRAST_ADJUSTMENT_RANGE = 0.1  # 調整幅


# =============================================================================
# 露出計算
# =============================================================================

def calculate_exposure_for_skin(roi_luma, target_luma=SKIN_TONE_TARGET_LUMA):
    """
    顔ROI輝度から目標肌トーンへの露出補正量を計算

    Args:
        roi_luma: 顔ROIの平均輝度（0-1）
        target_luma: 目標輝度（0-1）

    Returns:
        float: 露出補正量（EV）
    """
    if roi_luma <= 0:
        return 0.0

    # 輝度比から露出補正量を計算
    # EV = log2(target / current)
    ratio = target_luma / roi_luma
    exposure_ev = math.log2(ratio)

    return exposure_ev


def calculate_exposure_for_global(global_luma, is_slog3=True):
    """
    全体輝度から露出補正量を計算

    Args:
        global_luma: 全体の平均輝度（0-1）
        is_slog3: S-Log3素材かどうか

    Returns:
        float: 露出補正量（EV）
    """
    if global_luma <= 0:
        return 0.0

    # S-Log3の場合、中間グレーを基準
    target = SLOG3_MIDDLE_GRAY if is_slog3 else 0.5

    ratio = target / global_luma
    exposure_ev = math.log2(ratio)

    return exposure_ev


def calculate_combined_exposure(roi_stats, global_stats, has_face=True):
    """
    顔ROIと全体の統計値から最終的な露出補正量を計算

    Args:
        roi_stats: 顔ROIの統計値 {"luma_mean": float, ...}
        global_stats: 全体の統計値 {"luma_mean": float, ...}
        has_face: 顔が検出されたかどうか

    Returns:
        dict: {
            "exposure_ev": float,
            "roi_exposure_ev": float,
            "global_exposure_ev": float,
            "method": str
        }
    """
    global_luma = global_stats.get("luma_mean", 0.5)
    global_exp = calculate_exposure_for_global(global_luma)

    if has_face and roi_stats:
        roi_luma = roi_stats.get("luma_mean", 0.5)
        roi_exp = calculate_exposure_for_skin(roi_luma)

        # 重み付け平均
        combined_exp = (roi_exp * FACE_WEIGHT) + (global_exp * GLOBAL_WEIGHT)

        return {
            "exposure_ev": combined_exp,
            "roi_exposure_ev": roi_exp,
            "global_exposure_ev": global_exp,
            "method": "face_weighted"
        }
    else:
        # 顔がない場合は全体のみで計算
        return {
            "exposure_ev": global_exp,
            "roi_exposure_ev": None,
            "global_exposure_ev": global_exp,
            "method": "global_only"
        }


# =============================================================================
# コントラスト計算
# =============================================================================

def calculate_contrast(global_stats, is_slog3=True):
    """
    統計値からコントラスト補正量を計算

    Args:
        global_stats: 全体の統計値
        is_slog3: S-Log3素材かどうか

    Returns:
        float: コントラスト係数
    """
    if not is_slog3:
        return 1.0

    # S-Log3の場合はベースコントラストを適用
    # 輝度の標準偏差が小さい（フラットな映像）ならコントラスト強め
    luma_std = global_stats.get("luma_std", 0.15)

    # 標準偏差が0.1以下ならコントラスト強め、0.2以上なら控えめ
    if luma_std < 0.1:
        adjustment = CONTRAST_ADJUSTMENT_RANGE
    elif luma_std > 0.2:
        adjustment = -CONTRAST_ADJUSTMENT_RANGE / 2
    else:
        adjustment = 0.0

    return CONTRAST_BASE + adjustment


# =============================================================================
# 安全クランプ
# =============================================================================

def clamp_exposure(exposure_ev):
    """露出補正量を安全範囲にクランプ"""
    return max(MIN_EXPOSURE_EV, min(MAX_EXPOSURE_EV, exposure_ev))


def is_within_tolerance(exposure_ev, tolerance=SKIN_TONE_TOLERANCE):
    """補正が許容範囲内かどうか"""
    # 小さな補正は適用しない
    return abs(exposure_ev) < tolerance


# =============================================================================
# 統合処理
# =============================================================================

def calculate_correction_params(roi_analysis_result, is_slog3=True):
    """
    ROI解析結果から補正パラメータを計算

    Args:
        roi_analysis_result: analyze_frame()の戻り値
        is_slog3: S-Log3素材かどうか

    Returns:
        dict: {
            "exposure_ev": float,
            "contrast_factor": float,
            "has_face": bool,
            "method": str,
            "details": {...}
        }
    """
    has_face = roi_analysis_result.get("primary_roi") is not None
    roi_stats = roi_analysis_result.get("roi_stats")
    global_stats = roi_analysis_result.get("global_stats", {})

    # 露出計算
    exposure_result = calculate_combined_exposure(roi_stats, global_stats, has_face)
    raw_exposure = exposure_result["exposure_ev"]

    # 許容範囲チェック
    if is_within_tolerance(raw_exposure):
        final_exposure = 0.0
        skip_reason = "within_tolerance"
    else:
        final_exposure = clamp_exposure(raw_exposure)
        skip_reason = None

    # コントラスト計算
    contrast = calculate_contrast(global_stats, is_slog3)

    return {
        "exposure_ev": final_exposure,
        "contrast_factor": contrast,
        "has_face": has_face,
        "method": exposure_result["method"],
        "skip_reason": skip_reason,
        "details": {
            "raw_exposure_ev": raw_exposure,
            "roi_exposure_ev": exposure_result.get("roi_exposure_ev"),
            "global_exposure_ev": exposure_result.get("global_exposure_ev"),
            "roi_luma": roi_stats.get("luma_mean") if roi_stats else None,
            "global_luma": global_stats.get("luma_mean"),
            "global_luma_std": global_stats.get("luma_std")
        }
    }


# =============================================================================
# CDL変換
# =============================================================================

def params_to_cdl(exposure_ev, contrast_factor):
    """
    補正パラメータをASC-CDL形式に変換

    Args:
        exposure_ev: 露出補正量（EV）
        contrast_factor: コントラスト係数

    Returns:
        dict: slope, offset, power, saturation
    """
    slope = pow(2, exposure_ev)
    power = 1.0 / contrast_factor if contrast_factor != 0 else 1.0

    return {
        "slope": slope,
        "offset": 0.0,
        "power": power,
        "saturation": 1.0
    }


# =============================================================================
# テスト用
# =============================================================================

def _test():
    """テスト"""
    print("Exposure Calculator Test")
    print("=" * 50)

    # テスト用のROI解析結果
    test_result = {
        "primary_roi": {"id": 0, "roi": (100, 100, 200, 200)},
        "roi_stats": {
            "luma_mean": 0.37,  # 顔の輝度（S-Log3で暗め）
            "luma_std": 0.12,
            "saturation_mean": 0.16,
            "saturation_std": 0.07
        },
        "global_stats": {
            "luma_mean": 0.40,
            "luma_std": 0.16,
            "saturation_mean": 0.21,
            "saturation_std": 0.11
        }
    }

    # 補正計算
    params = calculate_correction_params(test_result, is_slog3=True)

    print(f"Has face: {params['has_face']}")
    print(f"Method: {params['method']}")
    print(f"Exposure EV: {params['exposure_ev']:+.2f}")
    print(f"Contrast: {params['contrast_factor']:.2f}")
    print(f"Skip reason: {params['skip_reason']}")
    print()
    print("Details:")
    for k, v in params['details'].items():
        if v is not None:
            print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

    # CDL変換
    cdl = params_to_cdl(params['exposure_ev'], params['contrast_factor'])
    print()
    print("CDL Values:")
    print(f"  Slope: {cdl['slope']:.4f}")
    print(f"  Offset: {cdl['offset']:.4f}")
    print(f"  Power: {cdl['power']:.4f}")

    print("=" * 50)
    print("Test completed!")


if __name__ == "__main__":
    _test()
