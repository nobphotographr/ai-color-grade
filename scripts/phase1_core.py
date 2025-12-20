#!/usr/bin/env python
"""
AI Color Grade - Phase 1 コアロジック
共通モジュール: メトリクス抽出・シーン分類・パラメータ決定

このモジュールは apply_grade_phase1.py と verify_phase1.py から共通で呼び出される。
Phase 1 ロジックの変更はここに集約する。
"""

import base64

# =============================================================================
# 定数
# =============================================================================

# 輝度しきい値（0-255スケール）
HIGHLIGHT_THRESHOLD = 230
SHADOW_THRESHOLD = 25

# シーン分類しきい値
LUMA_HIGH = 0.55
LUMA_LOW = 0.35
SATURATION_HIGH = 0.35
SHADOW_RATIO_NIGHT = 0.25

# シーン別補正パラメータ
SCENE_ADJUSTMENTS = {
    "outdoor_day": {"exposure_ev": -0.3, "contrast_factor": 1.05, "desc": "屋外昼間"},
    "indoor_human": {"exposure_ev": 0.0, "contrast_factor": 1.0, "desc": "室内人物"},
    "night": {"exposure_ev": 0.5, "contrast_factor": 1.15, "desc": "夜景"}
}

# 安全クランプ値
SAFETY_CLAMPS = {
    "exposure_ev": (-1.0, 1.0),
    "contrast_factor": (0.8, 1.3)
}

# =============================================================================
# ユーティリティ
# =============================================================================

def clamp(value, min_val, max_val):
    """値を範囲内に制限"""
    return max(min(value, max_val), min_val)


def rgb_to_luma(r, g, b):
    """RGBから輝度（Luma）を計算 (Rec.709)"""
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def rgb_to_saturation(r, g, b):
    """RGBから彩度を計算（HSL方式）"""
    r_norm, g_norm, b_norm = r / 255.0, g / 255.0, b / 255.0
    max_c, min_c = max(r_norm, g_norm, b_norm), min(r_norm, g_norm, b_norm)
    if max_c == min_c:
        return 0.0
    l = (max_c + min_c) / 2.0
    return (max_c - min_c) / (max_c + min_c) if l <= 0.5 else (max_c - min_c) / (2.0 - max_c - min_c)


# =============================================================================
# メトリクス抽出
# =============================================================================

def extract_metrics(thumbnail_data):
    """
    サムネイルデータからメトリクスを抽出

    Args:
        thumbnail_data: Resolve API GetCurrentClipThumbnailImage() の戻り値
                       dict with keys: width, height, format, data (base64)

    Returns:
        dict: avg_luma, highlight_ratio, shadow_ratio, saturation_avg, face_detected
    """
    default_metrics = {
        "avg_luma": 0.5,
        "highlight_ratio": 0.0,
        "shadow_ratio": 0.0,
        "saturation_avg": 0.0,
        "face_detected": False
    }

    if not thumbnail_data:
        return default_metrics

    width = thumbnail_data.get("width", 0)
    height = thumbnail_data.get("height", 0)
    data_b64 = thumbnail_data.get("data", "")

    if not data_b64 or width == 0 or height == 0:
        return default_metrics

    try:
        raw_bytes = base64.b64decode(data_b64)
    except Exception:
        return default_metrics

    total_pixels = 0
    luma_sum = 0.0
    saturation_sum = 0.0
    highlight_count = 0
    shadow_count = 0

    for i in range(0, len(raw_bytes) - 2, 3):
        r, g, b = raw_bytes[i], raw_bytes[i+1], raw_bytes[i+2]
        total_pixels += 1

        luma = rgb_to_luma(r, g, b)
        luma_sum += luma
        if luma >= HIGHLIGHT_THRESHOLD:
            highlight_count += 1
        elif luma <= SHADOW_THRESHOLD:
            shadow_count += 1

        saturation_sum += rgb_to_saturation(r, g, b)

    if total_pixels == 0:
        return default_metrics

    return {
        "avg_luma": round((luma_sum / total_pixels) / 255.0, 4),
        "highlight_ratio": round(highlight_count / total_pixels, 4),
        "shadow_ratio": round(shadow_count / total_pixels, 4),
        "saturation_avg": round(saturation_sum / total_pixels, 4),
        "face_detected": False
    }


# =============================================================================
# シーン分類
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
        metrics: dict from extract_metrics()

    Returns:
        str: "outdoor_day", "indoor_human", or "night"
    """
    avg_luma = metrics.get("avg_luma", 0.5)
    saturation_avg = metrics.get("saturation_avg", 0.0)
    shadow_ratio = metrics.get("shadow_ratio", 0.0)
    face_detected = metrics.get("face_detected", False)

    if face_detected:
        return "indoor_human"
    if avg_luma > LUMA_HIGH and saturation_avg > SATURATION_HIGH:
        return "outdoor_day"
    if avg_luma < LUMA_LOW and shadow_ratio > SHADOW_RATIO_NIGHT:
        return "night"
    return "indoor_human"


# =============================================================================
# パラメータ決定
# =============================================================================

def decide_params(scene_type):
    """
    シーンタイプに基づいて補正パラメータを決定（クランプ前）

    Args:
        scene_type: str from classify_scene()

    Returns:
        dict: exposure_ev, contrast_factor (クランプ前の値)
    """
    adj = SCENE_ADJUSTMENTS.get(scene_type, SCENE_ADJUSTMENTS["indoor_human"])
    return {
        "exposure_ev": adj["exposure_ev"],
        "contrast_factor": adj["contrast_factor"],
        "description": adj["desc"]
    }


def clamp_params(params):
    """
    パラメータに安全クランプを適用

    Args:
        params: dict with exposure_ev, contrast_factor

    Returns:
        dict: clamped values + clamp_triggered flag
    """
    original_exp = params["exposure_ev"]
    original_con = params["contrast_factor"]

    clamped_exp = clamp(original_exp, *SAFETY_CLAMPS["exposure_ev"])
    clamped_con = clamp(original_con, *SAFETY_CLAMPS["contrast_factor"])

    clamp_triggered = (clamped_exp != original_exp) or (clamped_con != original_con)

    return {
        "exposure_ev": original_exp,
        "contrast_factor": original_con,
        "clamped_exposure_ev": clamped_exp,
        "clamped_contrast_factor": clamped_con,
        "clamp_triggered": clamp_triggered
    }


# =============================================================================
# CDL変換
# =============================================================================

def params_to_cdl(clamped_exposure_ev, clamped_contrast_factor):
    """
    クランプ済みパラメータをASC-CDL形式に変換

    Args:
        clamped_exposure_ev: float
        clamped_contrast_factor: float

    Returns:
        dict: slope, offset, power, saturation
    """
    slope = pow(2, clamped_exposure_ev)
    power = 1.0 / clamped_contrast_factor if clamped_contrast_factor != 0 else 1.0

    return {
        "slope": slope,
        "offset": 0.0,
        "power": power,
        "saturation": 1.0
    }


# =============================================================================
# 統合処理（Phase 1 フルパイプライン）
# =============================================================================

def run_phase1_pipeline(thumbnail_data):
    """
    Phase 1 の全処理を実行

    Args:
        thumbnail_data: Resolve API GetCurrentClipThumbnailImage() の戻り値

    Returns:
        dict: metrics, scene_label, params, cdl_values
    """
    # メトリクス抽出
    metrics = extract_metrics(thumbnail_data)

    # シーン分類
    scene_label = classify_scene(metrics)

    # パラメータ決定
    raw_params = decide_params(scene_label)
    clamped_params = clamp_params(raw_params)

    # CDL変換
    cdl_values = params_to_cdl(
        clamped_params["clamped_exposure_ev"],
        clamped_params["clamped_contrast_factor"]
    )

    return {
        "metrics": metrics,
        "scene_label": scene_label,
        "params": {
            "exposure_ev": clamped_params["exposure_ev"],
            "contrast_factor": clamped_params["contrast_factor"],
            "clamped_exposure_ev": clamped_params["clamped_exposure_ev"],
            "clamped_contrast_factor": clamped_params["clamped_contrast_factor"],
            "clamp_triggered": clamped_params["clamp_triggered"],
            "description": raw_params["description"]
        },
        "cdl_values": cdl_values
    }
