#!/usr/bin/env python
"""
AI Color Grade - Phase 1 検証スクリプト
DaVinci Resolve用 品質検証ツール

目的:
- テスト素材セットで再現性・事故率・手戻し量を定量化
- Phase 2へ進む判断材料を作成

使用方法:
1. DaVinci Resolveで "Test_Timeline" という名前のタイムラインを作成
2. 検証対象クリップを配置（任意でBlueマーカーでフィルタ可能）
3. Color ページを開く
4. Workspace → Scripts → verify_phase1 を実行
"""

import os
import sys
import json
import csv
from datetime import datetime

# =============================================================================
# 設定
# =============================================================================

# 検証対象タイムライン名
TEST_TIMELINE_NAME = "Test_Timeline"

# マーカーフィルタ（Blueマーカーのみ対象にする場合はTrue）
MARKER_FILTER_ENABLED = False
MARKER_FILTER_COLOR = "Blue"

# 出力先
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else os.path.expanduser("~")
REPORTS_DIR = os.path.join(SCRIPT_DIR, "reports")

# ログファイル
LOG_FILE = os.path.join(os.path.expanduser("~"), "Documents", "phase1_verify_log.txt")

# 事故検出しきい値
CATASTROPHIC_RULES = {
    "highlight_clipping_risk": {"field": "highlight_ratio_after", "op": ">", "value": 0.08, "severity": "high"},
    "shadow_crush_risk": {"field": "shadow_ratio_after", "op": ">", "value": 0.20, "severity": "high"},
    "midtone_too_dark": {"field": "avg_luma_after", "op": "<", "value": 0.28, "severity": "medium"},
    "midtone_too_bright": {"field": "avg_luma_after", "op": ">", "value": 0.65, "severity": "medium"},
}

# 使用可能候補の条件
USABLE_LUMA_MIN = 0.30
USABLE_LUMA_MAX = 0.62

# マーカー色
MARKER_COLORS = {
    "high": "Red",
    "medium": "Yellow"
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

def ensure_reports_dir():
    """レポートディレクトリを作成"""
    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR)
    return REPORTS_DIR

# =============================================================================
# Phase 1 コアロジック（インライン版）
# Resolve内実行時はimportが難しいため、コア機能をここに含める
# =============================================================================

import base64

# 定数
HIGHLIGHT_THRESHOLD = 230
SHADOW_THRESHOLD = 25
LUMA_HIGH = 0.55
LUMA_LOW = 0.35
SATURATION_HIGH = 0.35
SHADOW_RATIO_NIGHT = 0.25

SCENE_ADJUSTMENTS = {
    "outdoor_day": {"exposure_ev": -0.3, "contrast_factor": 1.05, "desc": "屋外昼間"},
    "indoor_human": {"exposure_ev": 0.0, "contrast_factor": 1.0, "desc": "室内人物"},
    "night": {"exposure_ev": 0.5, "contrast_factor": 1.15, "desc": "夜景"}
}

SAFETY_CLAMPS = {
    "exposure_ev": (-1.0, 1.0),
    "contrast_factor": (0.8, 1.3)
}

def clamp(value, min_val, max_val):
    return max(min(value, max_val), min_val)

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
    default_metrics = {
        "avg_luma": 0.5, "highlight_ratio": 0.0, "shadow_ratio": 0.0,
        "saturation_avg": 0.0, "face_detected": False
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
    except:
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

def classify_scene(metrics):
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

def decide_and_clamp_params(scene_type):
    adj = SCENE_ADJUSTMENTS.get(scene_type, SCENE_ADJUSTMENTS["indoor_human"])
    exp = adj["exposure_ev"]
    con = adj["contrast_factor"]
    clamped_exp = clamp(exp, *SAFETY_CLAMPS["exposure_ev"])
    clamped_con = clamp(con, *SAFETY_CLAMPS["contrast_factor"])
    return {
        "exposure_ev": exp,
        "contrast_factor": con,
        "clamped_exposure_ev": clamped_exp,
        "clamped_contrast_factor": clamped_con,
        "clamp_triggered": (clamped_exp != exp) or (clamped_con != con)
    }

def params_to_cdl(clamped_exp, clamped_con):
    slope = pow(2, clamped_exp)
    power = 1.0 / clamped_con if clamped_con != 0 else 1.0
    return {"slope": slope, "offset": 0.0, "power": power, "saturation": 1.0}

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

def get_test_timeline(resolve):
    """検証用タイムラインを取得"""
    project = resolve.GetProjectManager().GetCurrentProject()
    if not project:
        log("[ERROR] No project open")
        return None, None

    # タイムライン一覧から Test_Timeline を探す
    timeline_count = project.GetTimelineCount()
    for i in range(1, timeline_count + 1):
        timeline = project.GetTimelineByIndex(i)
        if timeline and timeline.GetName() == TEST_TIMELINE_NAME:
            log(f"[OK] Found timeline: {TEST_TIMELINE_NAME}")
            return project, timeline

    # 見つからない場合は現在のタイムラインを使用
    timeline = project.GetCurrentTimeline()
    if timeline:
        log(f"[WARN] '{TEST_TIMELINE_NAME}' not found, using current timeline: {timeline.GetName()}")
        return project, timeline

    log("[ERROR] No timeline available")
    return None, None

def get_timeline_clips(timeline):
    """タイムライン内の全ビデオクリップを取得"""
    clips = []
    track_count = timeline.GetTrackCount("video")

    for track_idx in range(1, track_count + 1):
        track_clips = timeline.GetItemListInTrack("video", track_idx)
        if track_clips:
            for clip in track_clips:
                clips.append({
                    "clip": clip,
                    "track": track_idx
                })

    return clips

def get_clip_thumbnail(timeline, clip):
    """クリップのサムネイルを取得"""
    # クリップを選択状態にする
    try:
        # 現在のクリップのサムネイルを取得
        thumbnail = timeline.GetCurrentClipThumbnailImage()
        return thumbnail
    except Exception as e:
        log(f"[WARN] GetCurrentClipThumbnailImage failed: {e}")
        return None

def apply_cdl(clip, node_index, cdl_values):
    """CDLを適用"""
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

def add_marker_to_clip(clip, color, note):
    """クリップにマーカーを追加"""
    try:
        # クリップの開始フレームにマーカーを追加
        frame_id = clip.GetStart()
        markers = clip.GetMarkers()

        # 既存のPhase1Verifyマーカーを削除
        for frame, marker_data in list(markers.items()):
            if "Phase1Verify" in marker_data.get("note", ""):
                clip.DeleteMarkerAtFrame(frame)

        # 新しいマーカーを追加
        clip.AddMarker(0, color, "Phase1Verify", note, 1)
        return True
    except Exception as e:
        log(f"[WARN] AddMarker failed: {e}")
        return False

# =============================================================================
# 事故検出
# =============================================================================

def detect_catastrophic_flags(metrics_after):
    """事故フラグを検出"""
    flags = []

    for rule_name, rule in CATASTROPHIC_RULES.items():
        field = rule["field"]
        op = rule["op"]
        threshold = rule["value"]
        severity = rule["severity"]

        value = metrics_after.get(field.replace("_after", ""), 0)

        triggered = False
        if op == ">" and value > threshold:
            triggered = True
        elif op == "<" and value < threshold:
            triggered = True
        elif op == ">=" and value >= threshold:
            triggered = True
        elif op == "<=" and value <= threshold:
            triggered = True

        if triggered:
            flags.append({"rule": rule_name, "severity": severity, "value": value, "threshold": threshold})

    return flags

def is_usable_candidate(metrics_after, flags):
    """使用可能候補かどうかを判定"""
    # high severity フラグがあれば不可
    for f in flags:
        if f["severity"] == "high":
            return False

    # avg_luma が範囲内か
    avg_luma = metrics_after.get("avg_luma", 0.5)
    if avg_luma < USABLE_LUMA_MIN or avg_luma > USABLE_LUMA_MAX:
        return False

    return True

# =============================================================================
# 決定論性チェック
# =============================================================================

def check_determinism(thumbnail_data):
    """同一入力で2回計算し、結果が一致するか確認"""
    # 1回目
    metrics1 = extract_metrics(thumbnail_data)
    scene1 = classify_scene(metrics1)
    params1 = decide_and_clamp_params(scene1)

    # 2回目
    metrics2 = extract_metrics(thumbnail_data)
    scene2 = classify_scene(metrics2)
    params2 = decide_and_clamp_params(scene2)

    # 比較
    match = (
        metrics1 == metrics2 and
        scene1 == scene2 and
        params1 == params2
    )

    return match

# =============================================================================
# レポート生成
# =============================================================================

def generate_reports(results, summary, reports_dir):
    """CSV, JSON, TXT レポートを生成"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # CSV
    csv_path = os.path.join(reports_dir, f"phase1_verification_report_{timestamp}.csv")
    if results:
        fieldnames = list(results[0].keys())
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                # flagsをJSON文字列に変換
                row_copy = row.copy()
                if "catastrophic_flags" in row_copy:
                    row_copy["catastrophic_flags"] = json.dumps(row_copy["catastrophic_flags"], ensure_ascii=False)
                writer.writerow(row_copy)
    log(f"[OK] CSV report: {csv_path}")

    # JSON
    json_path = os.path.join(reports_dir, f"phase1_verification_summary_{timestamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "details": results}, f, indent=2, ensure_ascii=False)
    log(f"[OK] JSON report: {json_path}")

    # TXT
    txt_path = os.path.join(reports_dir, f"phase1_verification_summary_{timestamp}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("AI Color Grade - Phase 1 Verification Report\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")

        f.write("## Summary\n")
        f.write(f"Total clips processed: {summary['total_clips_processed']}\n")
        f.write(f"Total clips skipped: {summary['total_clips_skipped']}\n")
        f.write(f"Deterministic check pass rate: {summary['deterministic_check_pass_rate']:.1%}\n")
        f.write(f"Clamp trigger rate: {summary['clamp_trigger_rate']:.1%}\n")
        f.write(f"Catastrophic flag rate: {summary['catastrophic_flag_rate']:.1%}\n")
        f.write(f"Usability estimate rate: {summary['usability_estimate_rate']:.1%}\n\n")

        f.write("## Scene Distribution\n")
        for scene, count in summary['per_scene_distribution'].items():
            f.write(f"  {scene}: {count}\n")
        f.write("\n")

        f.write("## Flagged Clips\n")
        for r in results:
            if r.get("catastrophic_flags"):
                f.write(f"  - {r['clip_name']}: {r['catastrophic_flags']}\n")

    log(f"[OK] TXT report: {txt_path}")

    return csv_path, json_path, txt_path

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

    log("=" * 60)
    log("AI Color Grade - Phase 1 Verification")
    log("=" * 60)

    # レポートディレクトリ作成
    reports_dir = ensure_reports_dir()
    log(f"[OK] Reports directory: {reports_dir}")

    # Resolve接続
    resolve = get_resolve()
    if not resolve:
        return False

    log("[OK] Connected to Resolve")

    # タイムライン取得
    project, timeline = get_test_timeline(resolve)
    if not timeline:
        return False

    log(f"[OK] Project: {project.GetName()}")
    log(f"[OK] Timeline: {timeline.GetName()}")

    # クリップ取得
    clips_info = get_timeline_clips(timeline)
    total_clips = len(clips_info)
    log(f"[OK] Found {total_clips} clips in timeline")

    if total_clips == 0:
        log("[ERROR] No clips found in timeline")
        return False

    # 結果格納
    results = []
    skipped_clips = []
    deterministic_passes = 0
    clamp_triggers = 0
    catastrophic_count = 0
    usable_count = 0
    scene_distribution = {"outdoor_day": 0, "indoor_human": 0, "night": 0}

    # 各クリップを処理
    log("-" * 60)
    log("Processing clips...")

    for idx, clip_info in enumerate(clips_info):
        clip = clip_info["clip"]
        clip_name = clip.GetName() if hasattr(clip, 'GetName') else f"Clip_{idx+1}"
        track = clip_info["track"]

        log(f"\n[{idx+1}/{total_clips}] {clip_name}")

        # クリップ情報取得
        try:
            start_frame = clip.GetStart()
            end_frame = clip.GetEnd()
            duration = end_frame - start_frame
        except:
            start_frame = 0
            end_frame = 0
            duration = 0

        # サムネイル取得（現在のクリップに移動が必要）
        # Note: Resolve APIでは直接クリップを選択する方法が限られている
        # ここでは簡易的にCurrentClipThumbnailImageを使用
        thumbnail = timeline.GetCurrentClipThumbnailImage()

        if not thumbnail:
            log(f"  [SKIP] No thumbnail available")
            skipped_clips.append({"clip_name": clip_name, "reason": "No thumbnail"})
            continue

        # 決定論性チェック
        deterministic = check_determinism(thumbnail)
        if deterministic:
            deterministic_passes += 1
            log(f"  [OK] Deterministic check passed")
        else:
            log(f"  [WARN] Deterministic check failed")

        # Phase 1 適用前メトリクス
        metrics_before = extract_metrics(thumbnail)
        scene_label = classify_scene(metrics_before)
        params = decide_and_clamp_params(scene_label)

        scene_distribution[scene_label] += 1

        if params["clamp_triggered"]:
            clamp_triggers += 1

        log(f"  Scene: {scene_label}")
        log(f"  Exposure: {params['clamped_exposure_ev']:+.2f} EV")
        log(f"  Contrast: {params['clamped_contrast_factor']:.2f}")

        # CDL適用
        cdl = params_to_cdl(params["clamped_exposure_ev"], params["clamped_contrast_factor"])
        apply_result = apply_cdl(clip, 1, cdl)

        if not apply_result:
            log(f"  [WARN] SetCDL failed")

        # 適用後メトリクス取得（サムネイル再取得）
        thumbnail_after = timeline.GetCurrentClipThumbnailImage()
        metrics_after = extract_metrics(thumbnail_after) if thumbnail_after else metrics_before

        # 事故フラグ検出
        flags = detect_catastrophic_flags(metrics_after)
        if flags:
            catastrophic_count += 1
            log(f"  [FLAG] Catastrophic: {[f['rule'] for f in flags]}")

            # マーカー追加
            max_severity = max([f["severity"] for f in flags], key=lambda s: 0 if s == "medium" else 1)
            marker_color = MARKER_COLORS.get(max_severity, "Yellow")
            marker_note = f"Phase1Verify\nscene={scene_label}\nexp={params['clamped_exposure_ev']}\ncon={params['clamped_contrast_factor']}\nflags={[f['rule'] for f in flags]}"
            add_marker_to_clip(clip, marker_color, marker_note)

        # 使用可能候補判定
        usable = is_usable_candidate(metrics_after, flags)
        if usable:
            usable_count += 1

        # 結果記録
        result = {
            "timeline_name": timeline.GetName(),
            "clip_index": idx + 1,
            "clip_name": clip_name,
            "track": track,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "duration_frames": duration,
            # 適用前メトリクス
            "avg_luma": metrics_before["avg_luma"],
            "highlight_ratio": metrics_before["highlight_ratio"],
            "shadow_ratio": metrics_before["shadow_ratio"],
            "saturation_avg": metrics_before["saturation_avg"],
            "face_detected": metrics_before["face_detected"],
            # Phase 1 決定
            "scene_label": scene_label,
            "exposure_ev": params["exposure_ev"],
            "contrast_factor": params["contrast_factor"],
            "clamped_exposure_ev": params["clamped_exposure_ev"],
            "clamped_contrast_factor": params["clamped_contrast_factor"],
            "clamp_triggered": params["clamp_triggered"],
            # 適用後メトリクス
            "avg_luma_after": metrics_after["avg_luma"],
            "highlight_ratio_after": metrics_after["highlight_ratio"],
            "shadow_ratio_after": metrics_after["shadow_ratio"],
            "saturation_avg_after": metrics_after["saturation_avg"],
            # 検証結果
            "deterministic_pass": deterministic,
            "catastrophic_flags": flags,
            "usable_candidate": usable
        }
        results.append(result)

    # サマリー計算
    processed = len(results)
    summary = {
        "total_clips_processed": processed,
        "total_clips_skipped": len(skipped_clips),
        "deterministic_check_pass_rate": deterministic_passes / processed if processed > 0 else 0,
        "clamp_trigger_rate": clamp_triggers / processed if processed > 0 else 0,
        "catastrophic_flag_rate": catastrophic_count / processed if processed > 0 else 0,
        "usability_estimate_rate": usable_count / processed if processed > 0 else 0,
        "per_scene_distribution": scene_distribution,
        "skipped_clips": skipped_clips
    }

    # レポート生成
    log("-" * 60)
    log("Generating reports...")
    csv_path, json_path, txt_path = generate_reports(results, summary, reports_dir)

    # 結果表示
    log("=" * 60)
    log("Verification Complete!")
    log("=" * 60)
    log(f"Processed: {processed} clips")
    log(f"Skipped: {len(skipped_clips)} clips")
    log(f"Deterministic: {summary['deterministic_check_pass_rate']:.1%}")
    log(f"Clamp triggered: {summary['clamp_trigger_rate']:.1%}")
    log(f"Catastrophic flags: {summary['catastrophic_flag_rate']:.1%}")
    log(f"Usable candidates: {summary['usability_estimate_rate']:.1%}")
    log("-" * 60)
    log("Scene distribution:")
    for scene, count in scene_distribution.items():
        pct = count / processed * 100 if processed > 0 else 0
        log(f"  {scene}: {count} ({pct:.1f}%)")
    log("=" * 60)

    return True

# 実行
main()
