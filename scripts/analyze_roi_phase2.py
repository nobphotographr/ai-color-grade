#!/usr/bin/env python
"""
AI Color Grade - Phase 2.1 ROI解析スクリプト
DaVinci Resolve 用 人物検出 + ROI統計値出力

機能:
- 現在フレームをスチルとして書き出し
- MediaPipe Face Detectionで顔検出
- Primary ROI選定（シャープネス優先・ヒステリシス）
- ROI内/全体の輝度・彩度統計値を出力

使用方法:
1. Resolve で Color ページを開き、クリップを選択
2. 解析したいフレームにプレイヘッドを移動
3. Workspace → Scripts → analyze_roi_phase2 を実行
"""

import os
import sys
import json
import tempfile
from datetime import datetime

# =============================================================================
# 設定
# =============================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else os.path.expanduser("~")
LOG_FILE = os.path.join(os.path.expanduser("~"), "Documents", "ai_colorgrade_phase2_log.txt")
OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "ai_colorgrade_roi")

# スチル書き出し設定
STILL_FORMAT = "png"
TEMP_STILL_PREFIX = "resolve_still_"

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

def ensure_dir(path):
    """ディレクトリ作成"""
    if not os.path.exists(path):
        os.makedirs(path)
    return path

# =============================================================================
# Resolve API
# =============================================================================

def get_resolve():
    """Resolve接続"""
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

def get_current_context(resolve):
    """現在のプロジェクト・タイムライン・クリップを取得"""
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

def export_current_frame(project, output_path):
    """
    現在フレームをスチルとして書き出し

    Args:
        project: Resolve Project object
        output_path: 出力ファイルパス

    Returns:
        bool: 成功/失敗
    """
    try:
        result = project.ExportCurrentFrameAsStill(output_path)
        if result:
            log(f"[OK] Still exported: {output_path}")
        else:
            log(f"[WARN] ExportCurrentFrameAsStill returned False")
        return result
    except Exception as e:
        log(f"[ERROR] ExportCurrentFrameAsStill exception: {e}")
        return False

def get_current_timecode(timeline):
    """現在のタイムコードを取得"""
    try:
        tc = timeline.GetCurrentTimecode()
        return tc if tc else "00:00:00:00"
    except:
        return "00:00:00:00"

# =============================================================================
# ROI解析
# =============================================================================

def import_roi_detector():
    """roi_detector モジュールをインポート"""
    # スクリプトディレクトリをパスに追加
    if SCRIPT_DIR not in sys.path:
        sys.path.insert(0, SCRIPT_DIR)

    try:
        import roi_detector
        return roi_detector
    except ImportError as e:
        log(f"[ERROR] Failed to import roi_detector: {e}")
        log("[INFO] Ensure MediaPipe and OpenCV are installed:")
        log("       pip install mediapipe opencv-python numpy")
        return None

def analyze_still(still_path, previous_primary_id=None):
    """
    スチル画像を解析

    Args:
        still_path: スチル画像のパス
        previous_primary_id: 前回のPrimary ROI ID

    Returns:
        dict: 解析結果
    """
    roi_detector = import_roi_detector()
    if not roi_detector:
        return None

    try:
        result = roi_detector.analyze_image_file(still_path, previous_primary_id=previous_primary_id)
        return result
    except Exception as e:
        log(f"[ERROR] ROI analysis failed: {e}")
        return None

# =============================================================================
# 結果出力
# =============================================================================

def format_result(result, timecode, clip_name=None):
    """結果を整形"""
    output = {
        "timecode": timecode,
        "clip_name": clip_name,
        "timestamp": datetime.now().isoformat(),
        "face_count": len(result["faces"]) if result else 0,
        "primary_roi": None,
        "roi_stats": None,
        "global_stats": None
    }

    if result:
        if result["primary_roi"]:
            primary = result["primary_roi"]
            output["primary_roi"] = {
                "id": primary["id"],
                "roi": primary["roi"],
                "confidence": round(primary["confidence"], 4),
                "score": round(primary.get("score", 0), 4)
            }

        if result["roi_stats"]:
            stats = result["roi_stats"]
            output["roi_stats"] = {
                "luma_mean": round(stats["luma_mean"], 4),
                "luma_std": round(stats["luma_std"], 4),
                "saturation_mean": round(stats["saturation_mean"], 4),
                "saturation_std": round(stats["saturation_std"], 4)
            }

        if result["global_stats"]:
            stats = result["global_stats"]
            output["global_stats"] = {
                "luma_mean": round(stats["luma_mean"], 4),
                "luma_std": round(stats["luma_std"], 4),
                "saturation_mean": round(stats["saturation_mean"], 4),
                "saturation_std": round(stats["saturation_std"], 4)
            }

    return output

def print_result(formatted):
    """結果をログ出力"""
    log("-" * 50)
    log(f"Timecode: {formatted['timecode']}")
    log(f"Faces detected: {formatted['face_count']}")

    if formatted["primary_roi"]:
        roi = formatted["primary_roi"]
        log(f"Primary ROI: {roi['roi']} (conf={roi['confidence']:.2f})")

    if formatted["roi_stats"]:
        stats = formatted["roi_stats"]
        log(f"ROI Stats:")
        log(f"  Luma: mean={stats['luma_mean']:.4f}, std={stats['luma_std']:.4f}")
        log(f"  Saturation: mean={stats['saturation_mean']:.4f}, std={stats['saturation_std']:.4f}")

    if formatted["global_stats"]:
        stats = formatted["global_stats"]
        log(f"Global Stats:")
        log(f"  Luma: mean={stats['luma_mean']:.4f}, std={stats['luma_std']:.4f}")
        log(f"  Saturation: mean={stats['saturation_mean']:.4f}, std={stats['saturation_std']:.4f}")

def save_result_json(formatted, output_dir):
    """結果をJSONファイルに保存"""
    ensure_dir(output_dir)

    # ファイル名: roi_analysis_YYYYMMDD_HHMMSS.json
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"roi_analysis_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(formatted, f, indent=2, ensure_ascii=False)

    log(f"[OK] Result saved: {filepath}")
    return filepath

# =============================================================================
# メイン処理
# =============================================================================

def main():
    """メイン処理"""
    # ログ初期化
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("")
    except:
        pass

    log("=" * 50)
    log("AI Color Grade - Phase 2.1")
    log("ROI Detection + Statistics")
    log("=" * 50)

    # Resolve接続
    resolve = get_resolve()
    if not resolve:
        return False

    log("[OK] Connected to Resolve")

    # 現在のコンテキスト取得
    project, timeline, clip = get_current_context(resolve)
    if not clip:
        return False

    project_name = project.GetName()
    timeline_name = timeline.GetName()
    timecode = get_current_timecode(timeline)

    log(f"[OK] Project: {project_name}")
    log(f"[OK] Timeline: {timeline_name}")
    log(f"[OK] Timecode: {timecode}")

    # 一時ファイルでスチル書き出し
    log("-" * 50)
    log("Exporting current frame as still...")

    temp_dir = tempfile.gettempdir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    still_path = os.path.join(temp_dir, f"{TEMP_STILL_PREFIX}{timestamp}.{STILL_FORMAT}")

    if not export_current_frame(project, still_path):
        log("[ERROR] Failed to export still")
        return False

    # ファイル存在確認
    if not os.path.exists(still_path):
        log(f"[ERROR] Still file not found: {still_path}")
        return False

    log(f"[OK] Still file size: {os.path.getsize(still_path)} bytes")

    # ROI解析
    log("-" * 50)
    log("Analyzing ROI...")

    result = analyze_still(still_path)

    if result is None:
        log("[ERROR] ROI analysis failed")
        # 一時ファイル削除
        try:
            os.remove(still_path)
        except:
            pass
        return False

    # 結果整形・出力
    formatted = format_result(result, timecode, timeline_name)
    print_result(formatted)

    # JSON保存
    log("-" * 50)
    save_result_json(formatted, OUTPUT_DIR)

    # 一時ファイル削除
    try:
        os.remove(still_path)
        log(f"[OK] Temp file removed: {still_path}")
    except Exception as e:
        log(f"[WARN] Failed to remove temp file: {e}")

    log("=" * 50)
    log("[SUCCESS] ROI analysis completed!")
    log("=" * 50)

    return True

# 実行
if __name__ == "__main__":
    main()
else:
    # Resolve から実行された場合
    main()
