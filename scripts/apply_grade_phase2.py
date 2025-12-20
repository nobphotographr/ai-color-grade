#!/usr/bin/env python
"""
AI Color Grade - Phase 2 統合版
DaVinci Resolve 用 AI自動カラーグレーディング

Phase 2 機能:
- 高解像度スチル書き出し
- MediaPipe顔検出
- ROI統計値算出
- 肌トーン基準の露出補正
- CDL適用

使用方法:
1. Resolve で Color ページを開き、クリップを選択
2. 解析したいフレームにプレイヘッドを移動
3. Workspace → Scripts → apply_grade_phase2 を実行
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
# モジュールインポート
# =============================================================================

def import_modules():
    """必要なモジュールをインポート"""
    if SCRIPT_DIR not in sys.path:
        sys.path.insert(0, SCRIPT_DIR)

    try:
        import roi_detector
        import exposure_calculator
        return roi_detector, exposure_calculator
    except ImportError as e:
        log(f"[ERROR] Failed to import modules: {e}")
        log("[INFO] Ensure roi_detector.py and exposure_calculator.py are in the same directory")
        return None, None

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
    """現在フレームをスチルとして書き出し"""
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

def apply_cdl(clip, node_index, cdl_values):
    """CDL適用"""
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
    """メイン処理"""
    # ログ初期化
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("")
    except:
        pass

    log("=" * 50)
    log("AI Color Grade - Phase 2")
    log("Face Detection + Smart Exposure")
    log("=" * 50)

    # モジュールインポート
    roi_detector, exposure_calculator = import_modules()
    if not roi_detector or not exposure_calculator:
        return False

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

    # スチル書き出し
    log("-" * 50)
    log("Step 1: Exporting current frame...")

    temp_dir = tempfile.gettempdir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    still_path = os.path.join(temp_dir, f"{TEMP_STILL_PREFIX}{timestamp}.{STILL_FORMAT}")

    if not export_current_frame(project, still_path):
        log("[ERROR] Failed to export still")
        return False

    if not os.path.exists(still_path):
        log(f"[ERROR] Still file not found: {still_path}")
        return False

    log(f"[OK] Still file size: {os.path.getsize(still_path)} bytes")

    # ROI解析
    log("-" * 50)
    log("Step 2: Analyzing ROI...")

    try:
        roi_result = roi_detector.analyze_image_file(still_path)
    except Exception as e:
        log(f"[ERROR] ROI analysis failed: {e}")
        # 一時ファイル削除
        try:
            os.remove(still_path)
        except:
            pass
        return False

    # ROI結果表示
    face_count = len(roi_result.get("faces", []))
    has_face = roi_result.get("primary_roi") is not None

    log(f"Faces detected: {face_count}")

    if has_face:
        primary = roi_result["primary_roi"]
        log(f"Primary ROI: {primary['roi']} (conf={primary['confidence']:.2f})")

        roi_stats = roi_result["roi_stats"]
        log(f"ROI Stats:")
        log(f"  Luma: mean={roi_stats['luma_mean']:.4f}, std={roi_stats['luma_std']:.4f}")
        log(f"  Saturation: mean={roi_stats['saturation_mean']:.4f}")

    global_stats = roi_result["global_stats"]
    log(f"Global Stats:")
    log(f"  Luma: mean={global_stats['luma_mean']:.4f}, std={global_stats['luma_std']:.4f}")

    # 露出補正計算
    log("-" * 50)
    log("Step 3: Calculating correction parameters...")

    correction = exposure_calculator.calculate_correction_params(roi_result, is_slog3=True)

    log(f"Method: {correction['method']}")
    log(f"Exposure: {correction['exposure_ev']:+.2f} EV")
    log(f"Contrast: {correction['contrast_factor']:.2f}")

    if correction['skip_reason']:
        log(f"[INFO] Skipped: {correction['skip_reason']}")

    # 詳細情報
    details = correction['details']
    if details.get('roi_exposure_ev') is not None:
        log(f"  (ROI-based: {details['roi_exposure_ev']:+.2f} EV)")
    log(f"  (Global-based: {details['global_exposure_ev']:+.2f} EV)")

    # CDL変換
    cdl_values = exposure_calculator.params_to_cdl(
        correction['exposure_ev'],
        correction['contrast_factor']
    )

    log("-" * 50)
    log("Step 4: Applying CDL...")
    log(f"  Slope: {cdl_values['slope']:.4f}")
    log(f"  Offset: {cdl_values['offset']:.4f}")
    log(f"  Power: {cdl_values['power']:.4f}")

    # CDL適用
    success = apply_cdl(clip, 1, cdl_values)

    # 結果保存
    ensure_dir(OUTPUT_DIR)
    result_data = {
        "timecode": timecode,
        "timestamp": datetime.now().isoformat(),
        "face_count": face_count,
        "has_face": has_face,
        "roi_stats": roi_result.get("roi_stats"),
        "global_stats": global_stats,
        "correction": correction,
        "cdl_values": cdl_values,
        "success": success
    }

    result_path = os.path.join(OUTPUT_DIR, f"grade_result_{timestamp}.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)
    log(f"[OK] Result saved: {result_path}")

    # 一時ファイル削除
    try:
        os.remove(still_path)
        log(f"[OK] Temp file removed")
    except:
        pass

    log("=" * 50)
    if success:
        if has_face:
            log(f"[SUCCESS] Grade applied! (Face detected, {correction['exposure_ev']:+.2f} EV)")
        else:
            log(f"[SUCCESS] Grade applied! (No face, {correction['exposure_ev']:+.2f} EV)")
    else:
        log("[FAILED] SetCDL returned False")
    log("=" * 50)

    return success

# 実行
if __name__ == "__main__":
    main()
else:
    main()
