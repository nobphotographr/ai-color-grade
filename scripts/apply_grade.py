#!/usr/bin/env python
"""
AI Color Grade - Phase 0
SetCDL を使った色補正テスト（正しい形式）
"""

import os
from datetime import datetime

# ログファイルパス
LOG_FILE = os.path.join(os.path.expanduser("~"), "Documents", "ai_colorgrade_log.txt")

# テスト用パラメータ
TEST_PARAMS = {
    "camera": "Sony S-Log3",
    "exposure_ev": 0.6,
    "wb_temp_delta": 300,
    "wb_tint_delta": -4,
    "contrast_factor": 1.08
}

def log(message):
    """ログ出力"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    print(message)

def clamp(value, min_val, max_val):
    return max(min(value, max_val), min_val)

def get_resolve():
    try:
        import DaVinciResolveScript as dvr
        return dvr.scriptapp("Resolve")
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

def params_to_cdl(params):
    """
    パラメータをCDL形式に変換

    ASC-CDL:
    - Slope (乗算): デフォルト 1.0 - 明るさの乗算
    - Offset (加算): デフォルト 0.0 - 明るさの加算
    - Power (ガンマ): デフォルト 1.0 - ガンマ補正
    - Saturation: デフォルト 1.0 - 彩度
    """
    exposure_ev = clamp(params.get("exposure_ev", 0), -2.0, 2.0)
    contrast = clamp(params.get("contrast_factor", 1.0), 0.5, 2.0)

    # 露出調整: EVをSlopeに変換
    # EV +1.0 = 2倍の明るさ = Slope 2.0
    # EV +0.6 ≒ Slope 1.52
    slope = pow(2, exposure_ev)

    # コントラスト調整: Power（ガンマ）で調整
    # contrast > 1 → power < 1 でコントラスト増加
    power = 1.0 / contrast if contrast != 0 else 1.0

    # Offset はデフォルト 0.0
    offset = 0.0

    # Saturation はデフォルト 1.0
    saturation = 1.0

    return {
        "slope": slope,
        "offset": offset,
        "power": power,
        "saturation": saturation
    }

def apply_cdl(clip, node_index, cdl_values):
    """
    SetCDL でノードにCDL値を適用

    正しい形式（APIドキュメントより）:
    SetCDL({"NodeIndex": "1", "Slope": "R G B", "Offset": "R G B", "Power": "R G B", "Saturation": "value"})
    値はすべて文字列！
    """
    slope = cdl_values['slope']
    offset = cdl_values['offset']
    power = cdl_values['power']
    saturation = cdl_values['saturation']

    log(f"Applying CDL to node {node_index}:")
    log(f"  Slope: {slope:.4f}")
    log(f"  Offset: {offset:.4f}")
    log(f"  Power: {power:.4f}")
    log(f"  Saturation: {saturation:.4f}")

    try:
        # 正しいCDL形式（APIドキュメントに準拠）
        # 全ての値は文字列、RGB値はスペース区切り
        cdl_map = {
            "NodeIndex": str(node_index),
            "Slope": f"{slope:.4f} {slope:.4f} {slope:.4f}",
            "Offset": f"{offset:.4f} {offset:.4f} {offset:.4f}",
            "Power": f"{power:.4f} {power:.4f} {power:.4f}",
            "Saturation": f"{saturation:.4f}"
        }

        log(f"CDL Map: {cdl_map}")

        result = clip.SetCDL(cdl_map)
        log(f"SetCDL result: {result}")

        return result

    except Exception as e:
        log(f"SetCDL failed: {e}")
        import traceback
        log(traceback.format_exc())
        return False

def main():
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("")

    log("=" * 50)
    log("AI Color Grade - Phase 0 (SetCDL Test)")
    log("=" * 50)

    resolve = get_resolve()
    if not resolve:
        return False

    log("[OK] Connected to Resolve")

    project, timeline, clip = get_current_clip(resolve)
    if not clip:
        return False

    log(f"[OK] Project: {project.GetName()}")
    log(f"[OK] Timeline: {timeline.GetName()}")
    log(f"[OK] Clip selected")

    # ノード数確認
    num_nodes = clip.GetNumNodes()
    log(f"[OK] Number of nodes: {num_nodes}")

    # パラメータをCDLに変換
    log("-" * 50)
    log(f"Camera: {TEST_PARAMS['camera']}")
    log(f"Input - Exposure: {TEST_PARAMS['exposure_ev']} EV")
    log(f"Input - Contrast: {TEST_PARAMS['contrast_factor']}")

    cdl_values = params_to_cdl(TEST_PARAMS)

    # ノード1にCDL適用
    log("-" * 50)
    success = apply_cdl(clip, 1, cdl_values)

    log("-" * 50)
    if success:
        log("[SUCCESS] CDL applied successfully!")
        log(">>> Check the clip - it should be BRIGHTER now <<<")
    else:
        log("[FAILED] SetCDL returned False")

    log("=" * 50)
    return success

main()
