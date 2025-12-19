#!/usr/bin/env python
"""
AI Color Grade - Phase 0 完成版
DaVinci Resolve 用 自動カラーグレーディングツール

使用方法:
1. params.json をスクリプトと同じフォルダに配置
2. Resolve で Color ページを開き、クリップを選択
3. Workspace → Scripts → apply_grade を実行
"""

import os
import json
from datetime import datetime

# =============================================================================
# 設定
# =============================================================================

# ログファイルパス
LOG_FILE = os.path.join(os.path.expanduser("~"), "Documents", "ai_colorgrade_log.txt")

# パラメータファイルパス（スクリプトと同じフォルダ）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else os.path.expanduser("~")
PARAMS_FILE = os.path.join(SCRIPT_DIR, "params.json")

# デフォルトパラメータ（params.json がない場合に使用）
DEFAULT_PARAMS = {
    "camera": "Sony S-Log3",
    "exposure_ev": 0.0,
    "wb_temp_delta": 0,
    "wb_tint_delta": 0,
    "contrast_factor": 1.0
}

# パラメータ制限値
LIMITS = {
    "exposure_ev": (-2.0, 2.0),
    "wb_temp_delta": (-2000, 2000),
    "wb_tint_delta": (-100, 100),
    "contrast_factor": (0.5, 2.0)
}

# =============================================================================
# ユーティリティ関数
# =============================================================================

def log(message):
    """ログ出力（コンソール + ファイル）"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(message)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass

def clamp(value, min_val, max_val):
    """値を範囲内に制限"""
    return max(min(value, max_val), min_val)

# =============================================================================
# Resolve API
# =============================================================================

def get_resolve():
    """Resolve APIへの接続"""
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
    """現在選択中のクリップを取得"""
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
        log("[ERROR] No clip selected - please select a clip in Color page")
        return None, None, None

    return project, timeline, clip

# =============================================================================
# パラメータ処理
# =============================================================================

def load_params():
    """JSONファイルからパラメータを読み込み"""
    # Resolve 内での実行時は __file__ が使えないため、
    # Documents フォルダにも params.json を探す
    search_paths = [
        PARAMS_FILE,
        os.path.join(os.path.expanduser("~"), "Documents", "params.json"),
        os.path.join(os.path.expanduser("~"), "Documents", "ai_colorgrade_params.json"),
    ]

    for path in search_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    params = json.load(f)
                log(f"[OK] Loaded params from: {path}")
                return params
            except json.JSONDecodeError as e:
                log(f"[ERROR] Invalid JSON in {path}: {e}")
            except Exception as e:
                log(f"[ERROR] Failed to read {path}: {e}")

    log("[INFO] No params.json found, using default parameters")
    return DEFAULT_PARAMS.copy()

def validate_params(params):
    """パラメータを検証・クランプ"""
    validated = {}

    # camera
    validated["camera"] = params.get("camera", DEFAULT_PARAMS["camera"])

    # 数値パラメータ
    for key, (min_val, max_val) in LIMITS.items():
        value = params.get(key, DEFAULT_PARAMS[key])
        try:
            value = float(value)
        except (TypeError, ValueError):
            log(f"[WARN] Invalid {key} value, using default")
            value = DEFAULT_PARAMS[key]

        original = value
        value = clamp(value, min_val, max_val)
        if value != original:
            log(f"[WARN] {key} clamped: {original} -> {value}")

        validated[key] = value

    return validated

def params_to_cdl(params):
    """
    パラメータをASC-CDL形式に変換

    ASC-CDL:
    - Slope (乗算): 明るさの乗算係数
    - Offset (加算): 明るさの加算値
    - Power (ガンマ): ガンマ補正
    - Saturation: 彩度
    """
    exposure_ev = params["exposure_ev"]
    contrast = params["contrast_factor"]

    # 露出調整: EVをSlopeに変換
    # EV +1.0 = 2倍の明るさ = Slope 2.0
    slope = pow(2, exposure_ev)

    # コントラスト調整: Power（ガンマ）で調整
    # contrast > 1 → power < 1 でコントラスト増加
    power = 1.0 / contrast if contrast != 0 else 1.0

    # Offset（将来的にWB補正で使用予定）
    offset = 0.0

    # Saturation
    saturation = 1.0

    return {
        "slope": slope,
        "offset": offset,
        "power": power,
        "saturation": saturation
    }

# =============================================================================
# CDL適用
# =============================================================================

def apply_cdl(clip, node_index, cdl_values):
    """
    SetCDL でノードにCDL値を適用

    APIドキュメント形式:
    SetCDL({"NodeIndex": "1", "Slope": "R G B", "Offset": "R G B", "Power": "R G B", "Saturation": "value"})
    """
    slope = cdl_values['slope']
    offset = cdl_values['offset']
    power = cdl_values['power']
    saturation = cdl_values['saturation']

    # CDL形式に変換（全て文字列、RGB値はスペース区切り）
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
    # ログファイル初期化
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("")
    except:
        pass

    log("=" * 50)
    log("AI Color Grade - Phase 0")
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

    # ノード数確認
    num_nodes = clip.GetNumNodes()
    log(f"[OK] Nodes: {num_nodes}")

    # パラメータ読み込み
    log("-" * 50)
    params = load_params()
    params = validate_params(params)

    # パラメータ表示
    log(f"Camera: {params['camera']}")
    log(f"Exposure: {params['exposure_ev']:+.2f} EV")
    log(f"WB Temp: {params['wb_temp_delta']:+.0f} K")
    log(f"WB Tint: {params['wb_tint_delta']:+.0f}")
    log(f"Contrast: {params['contrast_factor']:.2f}")

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
        log("[SUCCESS] Grade applied!")
        log("=" * 50)
        return True
    else:
        log("[FAILED] SetCDL returned False")
        log("=" * 50)
        return False

# 実行
main()
