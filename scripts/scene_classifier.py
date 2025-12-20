#!/usr/bin/env python
"""
AI Color Grade - Phase 1 シーン分類モジュール
メトリクスに基づいてシーンタイプを判定し、補正パラメータを生成

シーンタイプ:
- outdoor_day: 屋外昼間（明るく彩度高め）
- indoor_human: 室内人物（中間露出、顔検出）
- night: 夜景（暗め、コントラスト高め）
"""

# =============================================================================
# シーン分類しきい値
# =============================================================================

# 輝度しきい値
LUMA_HIGH = 0.55      # これ以上は明るい（outdoor_day候補）
LUMA_LOW = 0.35       # これ以下は暗い（night候補）

# 彩度しきい値
SATURATION_HIGH = 0.35  # 屋外の高彩度

# ハイライト/シャドウ比率
HIGHLIGHT_RATIO_NIGHT = 0.15  # 夜景の特徴: ハイライトが少ない
SHADOW_RATIO_NIGHT = 0.25     # 夜景の特徴: シャドウが多い

# =============================================================================
# シーン別補正パラメータ
# =============================================================================

SCENE_ADJUSTMENTS = {
    "outdoor_day": {
        "exposure_ev": -0.3,       # 少し暗く
        "contrast_factor": 1.05,   # 若干コントラスト上げ
        "saturation_boost": 1.0,   # 彩度維持
        "description": "屋外昼間: 露出下げ、コントラスト微増"
    },
    "indoor_human": {
        "exposure_ev": 0.0,        # 補正なし
        "contrast_factor": 1.0,    # 補正なし
        "saturation_boost": 1.0,   # 彩度維持
        "description": "室内人物: ニュートラル"
    },
    "night": {
        "exposure_ev": 0.5,        # 露出上げ
        "contrast_factor": 1.15,   # コントラスト上げ
        "saturation_boost": 0.9,   # 彩度若干下げ
        "description": "夜景: 露出上げ、コントラスト強調"
    }
}

# =============================================================================
# 安全クランプ値（Phase 1仕様準拠）
# =============================================================================

SAFETY_CLAMPS = {
    "exposure_ev": (-1.0, 1.0),
    "contrast_factor": (0.8, 1.3)
}

# =============================================================================
# 分類ロジック
# =============================================================================

def classify_scene(metrics):
    """
    メトリクスからシーンタイプを判定

    判定ロジック:
    1. face_detected=True → indoor_human
    2. avg_luma > 0.55 かつ saturation > 0.35 → outdoor_day
    3. avg_luma < 0.35 かつ shadow_ratio > 0.25 → night
    4. それ以外 → indoor_human（デフォルト）

    Args:
        metrics: dict with avg_luma, highlight_ratio, shadow_ratio, saturation_avg, face_detected

    Returns:
        scene_type: str ("outdoor_day", "indoor_human", "night")
    """
    avg_luma = metrics.get("avg_luma", 0.5)
    saturation_avg = metrics.get("saturation_avg", 0.0)
    shadow_ratio = metrics.get("shadow_ratio", 0.0)
    face_detected = metrics.get("face_detected", False)

    # 顔検出があれば室内人物
    if face_detected:
        return "indoor_human"

    # 明るく彩度が高い → 屋外昼間
    if avg_luma > LUMA_HIGH and saturation_avg > SATURATION_HIGH:
        return "outdoor_day"

    # 暗くシャドウが多い → 夜景
    if avg_luma < LUMA_LOW and shadow_ratio > SHADOW_RATIO_NIGHT:
        return "night"

    # デフォルト: 室内人物（最も保守的）
    return "indoor_human"


def clamp(value, min_val, max_val):
    """値を範囲内に制限"""
    return max(min(value, max_val), min_val)


def get_adjustments(scene_type, base_params=None):
    """
    シーンタイプに応じた補正パラメータを取得

    Args:
        scene_type: str ("outdoor_day", "indoor_human", "night")
        base_params: dict 既存のパラメータ（あれば加算）

    Returns:
        dict with adjusted parameters
    """
    if base_params is None:
        base_params = {
            "exposure_ev": 0.0,
            "wb_temp_delta": 0,
            "wb_tint_delta": 0,
            "contrast_factor": 1.0
        }

    adjustments = SCENE_ADJUSTMENTS.get(scene_type, SCENE_ADJUSTMENTS["indoor_human"])

    # パラメータ調整
    new_exposure = base_params.get("exposure_ev", 0.0) + adjustments["exposure_ev"]
    new_contrast = base_params.get("contrast_factor", 1.0) * adjustments["contrast_factor"]

    # 安全クランプ適用
    new_exposure = clamp(new_exposure, *SAFETY_CLAMPS["exposure_ev"])
    new_contrast = clamp(new_contrast, *SAFETY_CLAMPS["contrast_factor"])

    result = {
        "camera": base_params.get("camera", "Sony S-Log3"),
        "exposure_ev": round(new_exposure, 2),
        "wb_temp_delta": base_params.get("wb_temp_delta", 0),
        "wb_tint_delta": base_params.get("wb_tint_delta", 0),
        "contrast_factor": round(new_contrast, 2),
        "scene_type": scene_type,
        "scene_description": adjustments["description"]
    }

    return result


def analyze_and_adjust(metrics, base_params=None):
    """
    メトリクスを分析してシーン分類し、補正パラメータを返す（メインエントリポイント）

    Args:
        metrics: dict from metrics_extractor
        base_params: dict 既存のパラメータ

    Returns:
        dict with scene_type and adjusted parameters
    """
    scene_type = classify_scene(metrics)
    adjustments = get_adjustments(scene_type, base_params)

    return adjustments


# =============================================================================
# テスト用
# =============================================================================

def test_classification():
    """各シーンタイプのテスト"""
    test_cases = [
        {
            "name": "Bright outdoor scene",
            "metrics": {
                "avg_luma": 0.65,
                "highlight_ratio": 0.15,
                "shadow_ratio": 0.05,
                "saturation_avg": 0.45,
                "face_detected": False
            },
            "expected": "outdoor_day"
        },
        {
            "name": "Dark night scene",
            "metrics": {
                "avg_luma": 0.25,
                "highlight_ratio": 0.05,
                "shadow_ratio": 0.35,
                "saturation_avg": 0.20,
                "face_detected": False
            },
            "expected": "night"
        },
        {
            "name": "Indoor with face",
            "metrics": {
                "avg_luma": 0.50,
                "highlight_ratio": 0.10,
                "shadow_ratio": 0.10,
                "saturation_avg": 0.30,
                "face_detected": True
            },
            "expected": "indoor_human"
        },
        {
            "name": "Neutral scene (default)",
            "metrics": {
                "avg_luma": 0.50,
                "highlight_ratio": 0.10,
                "shadow_ratio": 0.10,
                "saturation_avg": 0.25,
                "face_detected": False
            },
            "expected": "indoor_human"
        }
    ]

    print("=" * 50)
    print("Scene Classification Test")
    print("=" * 50)

    for tc in test_cases:
        scene_type = classify_scene(tc["metrics"])
        status = "✓" if scene_type == tc["expected"] else "✗"
        print(f"\n{status} {tc['name']}")
        print(f"  Expected: {tc['expected']}")
        print(f"  Got: {scene_type}")

        if scene_type == tc["expected"]:
            adjustments = get_adjustments(scene_type)
            print(f"  Exposure: {adjustments['exposure_ev']:+.2f} EV")
            print(f"  Contrast: {adjustments['contrast_factor']:.2f}")


if __name__ == "__main__":
    test_classification()
