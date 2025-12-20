#!/usr/bin/env python
"""
AI Color Grade - Phase 1 メトリクス抽出モジュール
サムネイル画像からシーン分類用のメトリクスを計算

メトリクス:
- avg_luma: 平均輝度 (0.0-1.0)
- highlight_ratio: ハイライト領域の割合
- shadow_ratio: シャドウ領域の割合
- saturation_avg: 平均彩度
- face_detected: 顔検出フラグ（Phase 1では常にFalse）
"""

import base64
import struct

# =============================================================================
# 定数
# =============================================================================

# 輝度しきい値（0-255スケール）
HIGHLIGHT_THRESHOLD = 230  # これ以上はハイライト
SHADOW_THRESHOLD = 25      # これ以下はシャドウ

# =============================================================================
# ピクセル処理
# =============================================================================

def decode_thumbnail(thumbnail_data):
    """
    Resolve APIのサムネイルデータをデコード

    Args:
        thumbnail_data: dict with keys "width", "height", "format", "data"
                       data is RGB 8-bit base64 encoded

    Returns:
        list of (r, g, b) tuples, width, height
    """
    if not thumbnail_data:
        return None, 0, 0

    width = thumbnail_data.get("width", 0)
    height = thumbnail_data.get("height", 0)
    data_b64 = thumbnail_data.get("data", "")

    if not data_b64 or width == 0 or height == 0:
        return None, 0, 0

    # Base64デコード
    try:
        raw_bytes = base64.b64decode(data_b64)
    except Exception as e:
        print(f"[ERROR] Base64 decode failed: {e}")
        return None, 0, 0

    # RGB 8-bit → ピクセルリスト
    pixels = []
    expected_size = width * height * 3  # RGB = 3 bytes per pixel

    if len(raw_bytes) != expected_size:
        print(f"[WARN] Data size mismatch: expected {expected_size}, got {len(raw_bytes)}")
        # サイズが合わなくても処理を試みる

    for i in range(0, len(raw_bytes) - 2, 3):
        r = raw_bytes[i]
        g = raw_bytes[i + 1]
        b = raw_bytes[i + 2]
        pixels.append((r, g, b))

    return pixels, width, height


def rgb_to_luma(r, g, b):
    """
    RGBから輝度（Luma）を計算
    Rec.709 係数使用: Y = 0.2126*R + 0.7152*G + 0.0722*B

    Returns:
        輝度値 (0-255)
    """
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def rgb_to_saturation(r, g, b):
    """
    RGBから彩度を計算（HSL方式）

    Returns:
        彩度値 (0.0-1.0)
    """
    r_norm = r / 255.0
    g_norm = g / 255.0
    b_norm = b / 255.0

    max_c = max(r_norm, g_norm, b_norm)
    min_c = min(r_norm, g_norm, b_norm)

    # 明度（Lightness）
    l = (max_c + min_c) / 2.0

    if max_c == min_c:
        return 0.0  # 無彩色

    # 彩度計算
    if l <= 0.5:
        s = (max_c - min_c) / (max_c + min_c)
    else:
        s = (max_c - min_c) / (2.0 - max_c - min_c)

    return s


# =============================================================================
# メトリクス計算
# =============================================================================

def calculate_metrics(pixels):
    """
    ピクセルリストからメトリクスを計算

    Args:
        pixels: list of (r, g, b) tuples

    Returns:
        dict with metrics
    """
    if not pixels or len(pixels) == 0:
        return {
            "avg_luma": 0.5,
            "highlight_ratio": 0.0,
            "shadow_ratio": 0.0,
            "saturation_avg": 0.0,
            "face_detected": False
        }

    total_pixels = len(pixels)

    luma_sum = 0.0
    saturation_sum = 0.0
    highlight_count = 0
    shadow_count = 0

    for r, g, b in pixels:
        # 輝度計算
        luma = rgb_to_luma(r, g, b)
        luma_sum += luma

        # ハイライト/シャドウ判定
        if luma >= HIGHLIGHT_THRESHOLD:
            highlight_count += 1
        elif luma <= SHADOW_THRESHOLD:
            shadow_count += 1

        # 彩度計算
        sat = rgb_to_saturation(r, g, b)
        saturation_sum += sat

    # 平均計算
    avg_luma = (luma_sum / total_pixels) / 255.0  # 0.0-1.0に正規化
    avg_saturation = saturation_sum / total_pixels
    highlight_ratio = highlight_count / total_pixels
    shadow_ratio = shadow_count / total_pixels

    return {
        "avg_luma": round(avg_luma, 4),
        "highlight_ratio": round(highlight_ratio, 4),
        "shadow_ratio": round(shadow_ratio, 4),
        "saturation_avg": round(avg_saturation, 4),
        "face_detected": False  # Phase 1では未実装
    }


def extract_metrics_from_thumbnail(thumbnail_data):
    """
    サムネイルデータからメトリクスを抽出（メインエントリポイント）

    Args:
        thumbnail_data: Resolve API GetCurrentClipThumbnailImage() の戻り値

    Returns:
        dict with metrics
    """
    pixels, width, height = decode_thumbnail(thumbnail_data)

    if pixels is None:
        print("[WARN] Could not decode thumbnail, using default metrics")
        return {
            "avg_luma": 0.5,
            "highlight_ratio": 0.0,
            "shadow_ratio": 0.0,
            "saturation_avg": 0.0,
            "face_detected": False
        }

    print(f"[OK] Decoded thumbnail: {width}x{height}, {len(pixels)} pixels")

    metrics = calculate_metrics(pixels)
    return metrics


# =============================================================================
# テスト用
# =============================================================================

def test_with_sample_data():
    """サンプルデータでテスト"""
    # 10x10のグレー画像をシミュレート（RGB各128）
    width = 10
    height = 10

    # RGB 8-bit データ作成
    raw_bytes = bytes([128, 128, 128] * (width * height))
    data_b64 = base64.b64encode(raw_bytes).decode('ascii')

    sample_thumbnail = {
        "width": width,
        "height": height,
        "format": "RGB 8-bit",
        "data": data_b64
    }

    print("Testing with sample gray image...")
    metrics = extract_metrics_from_thumbnail(sample_thumbnail)

    print("\nMetrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")

    return metrics


if __name__ == "__main__":
    test_with_sample_data()
