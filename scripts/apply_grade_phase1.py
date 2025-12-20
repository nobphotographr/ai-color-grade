#!/usr/bin/env python
"""
AI Color Grade - Phase 1 統合版
DaVinci Resolve 用 自動カラーグレーディングツール

Phase 1 機能:
- サムネイルからメトリクス抽出
- シーン自動分類（outdoor_day / indoor_human / night）
- ルールベース補正パラメータ適用

使用方法:
1. Resolve で Color ページを開き、クリップを選択
2. Workspace → Scripts → apply_grade_phase1 を実行
"""

import os
import sys
import json
import base64
from datetime import datetime

# =============================================================================
# 設定
# =============================================================================

LOG_FILE = os.path.join(os.path.expanduser("~"), "Documents", "ai_colorgrade_log.txt")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else os.path.expanduser("~")

# パラメータ制限値
LIMITS = {
    "exposure_ev": (-2.0, 2.0),
    "wb_temp_delta": (-2000, 2000),
    "wb_tint_delta": (-100, 100),
    "contrast_factor": (0.5, 2.0)
}

# 安全クランプ（Phase 1）
SAFETY_CLAMPS = {
    "exposure_ev": (-1.0, 1.0),
    "contrast_factor": (0.8, 1.3)
}

# =============================================================================
# ユーティリティ
# =============================================================================

def log(message):
    """ログ出力"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(message)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass

def clamp(value, min_val, max_val):
    return max(min(value, max_val), min_val)

# =============================================================================
# メトリクス抽出（metrics_extractor.py から統合）
# =============================================================================

HIGHLIGHT_THRESHOLD = 230
SHADOW_THRESHOLD = 25

def rgb_to_luma(r, g, b):
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def rgb_to_saturation(r, g, b):
    r_norm, g_norm, b_norm = r / 255.0, g / 255.0, b / 255.0
    max_c, min_c = max(r_norm, g_norm, b_norm), min(r_norm, g_norm, b_norm)
    if max_c == min_c:
        return 0.0
    l = (max_c + min_c) / 2.0
    return (max_c - min_c) / (max_c + min_c) if l <= 0.5 else (max_c - min_c) / (2.0 - max_c - min_c)

def extract_metrics(thumbnail_data):
    """サムネイルからメトリクスを抽出"""
    if not thumbnail_data:
        log("[WARN] No thumbnail data, using defaults")
        return {"avg_luma": 0.5, "highlight_ratio": 0.0, "shadow_ratio": 0.0, "saturation_avg": 0.0, "face_detected": False}

    width = thumbnail_data.get("width", 0)
    height = thumbnail_data.get("height", 0)
    data_b64 = thumbnail_data.get("data", "")

    if not data_b64 or width == 0 or height == 0:
        log("[WARN] Invalid thumbnail data")
        return {"avg_luma": 0.5, "highlight_ratio": 0.0, "shadow_ratio": 0.0, "saturation_avg": 0.0, "face_detected": False}

    try:
        raw_bytes = base64.b64decode(data_b64)
    except Exception as e:
        log(f"[ERROR] Base64 decode failed: {e}")
        return {"avg_luma": 0.5, "highlight_ratio": 0.0, "shadow_ratio": 0.0, "saturation_avg": 0.0, "face_detected": False}

    log(f"[OK] Thumbnail: {width}x{height}")

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
        return {"avg_luma": 0.5, "highlight_ratio": 0.0, "shadow_ratio": 0.0, "saturation_avg": 0.0, "face_detected": False}

    return {
        "avg_luma": round((luma_sum / total_pixels) / 255.0, 4),
        "highlight_ratio": round(highlight_count / total_pixels, 4),
        "shadow_ratio": round(shadow_count / total_pixels, 4),
        "saturation_avg": round(saturation_sum / total_pixels, 4),
        "face_detected": False
    }

# =============================================================================
# シーン分類（scene_classifier.py から統合）
# =============================================================================

SCENE_ADJUSTMENTS = {
    "outdoor_day": {"exposure_ev": -0.3, "contrast_factor": 1.05, "desc": "屋外昼間"},
    "indoor_human": {"exposure_ev": 0.0, "contrast_factor": 1.0, "desc": "室内人物"},
    "night": {"exposure_ev": 0.5, "contrast_factor": 1.15, "desc": "夜景"}
}

def classify_scene(metrics):
    """シーン分類"""
    avg_luma = metrics.get("avg_luma", 0.5)
    saturation_avg = metrics.get("saturation_avg", 0.0)
    shadow_ratio = metrics.get("shadow_ratio", 0.0)
    face_detected = metrics.get("face_detected", False)

    if face_detected:
        return "indoor_human"
    if avg_luma > 0.55 and saturation_avg > 0.35:
        return "outdoor_day"
    if avg_luma < 0.35 and shadow_ratio > 0.25:
        return "night"
    return "indoor_human"

def apply_scene_adjustments(scene_type):
    """シーンに応じた補正パラメータを取得"""
    adj = SCENE_ADJUSTMENTS.get(scene_type, SCENE_ADJUSTMENTS["indoor_human"])

    exposure = clamp(adj["exposure_ev"], *SAFETY_CLAMPS["exposure_ev"])
    contrast = clamp(adj["contrast_factor"], *SAFETY_CLAMPS["contrast_factor"])

    return {
        "camera": "Sony S-Log3",
        "exposure_ev": exposure,
        "wb_temp_delta": 0,
        "wb_tint_delta": 0,
        "contrast_factor": contrast,
        "scene_type": scene_type,
        "scene_desc": adj["desc"]
    }

# =============================================================================
# Resolve API
# =============================================================================

def get_resolve():
    try:
        import DaVinciResolveScript as dvr
        resolve = dvr.scriptapp("Resolve")
        if not resolve:
            log("[ERROR] Resolve is not running")
            return None
        return resolve
    except ImportError as e:
        log(f"[ERROR] DaVinciResolveScript not found: {e}")
        return None

def get_current_clip(resolve):
    project = resolve.GetProjectManager().GetCurrentProject()
    if not project:
        log("[ERROR] No project open")
        return None, None, None

    timeline = project.GetCurrentTimeline()
    if not timeline:
        log("[ERROR] No timeline selected")
        return None, None, None

    clip = timeline.GetCurrentVideoItem()
    if not clip:
        log("[ERROR] No clip selected")
        return None, None, None

    return project, timeline, clip

def get_thumbnail(timeline):
    """サムネイル取得"""
    try:
        thumbnail = timeline.GetCurrentClipThumbnailImage()
        return thumbnail
    except Exception as e:
        log(f"[WARN] GetCurrentClipThumbnailImage failed: {e}")
        return None

# =============================================================================
# CDL変換・適用
# =============================================================================

def params_to_cdl(params):
    exposure_ev = params["exposure_ev"]
    contrast = params["contrast_factor"]

    slope = pow(2, exposure_ev)
    power = 1.0 / contrast if contrast != 0 else 1.0

    return {
        "slope": slope,
        "offset": 0.0,
        "power": power,
        "saturation": 1.0
    }

def apply_cdl(clip, node_index, cdl_values):
    slope = cdl_values['slope']
    offset = cdl_values['offset']
    power = cdl_values['power']
    saturation = cdl_values['saturation']

    cdl_map = {
        "NodeIndex": str(node_index),
        "Slope": f"{slope:.4f} {slope:.4f} {slope:.4f}",
        "Offset": f"{offset:.4f} {offset:.4f} {offset:.4f}",
        "Power": f"{power:.4f} {power:.4f} {power:.4f}",
        "Saturation": f"{saturation:.4f}"
    }

    try:
        result = clip.SetCDL(cdl_map)
        return result
    except Exception as e:
        log(f"[ERROR] SetCDL exception: {e}")
        return False

# =============================================================================
# メイン処理
# =============================================================================

def main():
    # ログ初期化
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("")
    except:
        pass

    log("=" * 50)
    log("AI Color Grade - Phase 1")
    log("Scene Classification + Rule-Based Grading")
    log("=" * 50)

    # Resolve接続
    resolve = get_resolve()
    if not resolve:
        return False
    log("[OK] Connected to Resolve")

    # クリップ取得
    project, timeline, clip = get_current_clip(resolve)
    if not clip:
        return False

    log(f"[OK] Project: {project.GetName()}")
    log(f"[OK] Timeline: {timeline.GetName()}")
    log(f"[OK] Clip selected")

    # サムネイル取得とメトリクス抽出
    log("-" * 50)
    log("Extracting metrics from thumbnail...")

    thumbnail = get_thumbnail(timeline)
    metrics = extract_metrics(thumbnail)

    log(f"  avg_luma: {metrics['avg_luma']:.4f}")
    log(f"  highlight_ratio: {metrics['highlight_ratio']:.4f}")
    log(f"  shadow_ratio: {metrics['shadow_ratio']:.4f}")
    log(f"  saturation_avg: {metrics['saturation_avg']:.4f}")
    log(f"  face_detected: {metrics['face_detected']}")

    # シーン分類
    log("-" * 50)
    scene_type = classify_scene(metrics)
    log(f"[OK] Scene classified: {scene_type}")

    # 補正パラメータ取得
    params = apply_scene_adjustments(scene_type)
    log(f"  Description: {params['scene_desc']}")
    log(f"  Exposure: {params['exposure_ev']:+.2f} EV")
    log(f"  Contrast: {params['contrast_factor']:.2f}")

    # CDL変換
    cdl_values = params_to_cdl(params)

    log("-" * 50)
    log("CDL Values:")
    log(f"  Slope: {cdl_values['slope']:.4f}")
    log(f"  Offset: {cdl_values['offset']:.4f}")
    log(f"  Power: {cdl_values['power']:.4f}")
    log(f"  Saturation: {cdl_values['saturation']:.4f}")

    # CDL適用
    log("-" * 50)
    success = apply_cdl(clip, 1, cdl_values)

    if success:
        log(f"[SUCCESS] Grade applied! (Scene: {scene_type})")
        log("=" * 50)
        return True
    else:
        log("[FAILED] SetCDL returned False")
        log("=" * 50)
        return False

# 実行
main()
