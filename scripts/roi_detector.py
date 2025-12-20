#!/usr/bin/env python
"""
AI Color Grade - Phase 2.1 ROI検出モジュール
人物（顔）検出とROI統計値算出

機能:
- MediaPipe Face Detection（Tasks API）による顔検出
- ROI座標とconfidence score出力
- Primary ROI選定（シャープネス優先・ヒステリシス）
- ROI内/全体の輝度・彩度統計値算出

対応MediaPipeバージョン: 0.10.x (Tasks API)
"""

import os
import sys
import urllib.request
import tempfile

# MediaPipeインポート（遅延インポート）
_mediapipe = None
_cv2 = None
_np = None

# モデルファイルのURL
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
MODEL_FILENAME = "blaze_face_short_range.tflite"


def _ensure_imports():
    """必要なライブラリをインポート"""
    global _mediapipe, _cv2, _np

    if _mediapipe is None:
        try:
            import mediapipe as mp
            _mediapipe = mp
        except ImportError:
            raise ImportError("MediaPipe not found. Install with: pip install mediapipe")

    if _cv2 is None:
        try:
            import cv2
            _cv2 = cv2
        except ImportError:
            raise ImportError("OpenCV not found. Install with: pip install opencv-python")

    if _np is None:
        try:
            import numpy as np
            _np = np
        except ImportError:
            raise ImportError("NumPy not found. Install with: pip install numpy")

    return _mediapipe, _cv2, _np


def _get_model_path():
    """モデルファイルのパスを取得（なければダウンロード）"""
    # ユーザーのDocumentsフォルダにモデルを保存
    model_dir = os.path.join(os.path.expanduser("~"), "Documents", "ai_colorgrade_models")
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)

    model_path = os.path.join(model_dir, MODEL_FILENAME)

    if not os.path.exists(model_path):
        print(f"Downloading face detection model to {model_path}...")
        try:
            urllib.request.urlretrieve(MODEL_URL, model_path)
            print("Model downloaded successfully.")
        except Exception as e:
            raise RuntimeError(f"Failed to download model: {e}")

    return model_path


# =============================================================================
# 定数
# =============================================================================

# 顔検出設定
MIN_DETECTION_CONFIDENCE = 0.3  # S-Log3の低コントラスト素材用に閾値を下げる

# Primary ROI選定
HYSTERESIS_THRESHOLD = 0.15  # confidence差がこれ以下なら前回を維持
SHARPNESS_WEIGHT = 0.3       # シャープネスの重み（0-1）

# ROI拡張（顔領域を拡大して肌色領域を含める）
ROI_EXPAND_RATIO = 1.5  # 顔領域を1.5倍に拡大


# =============================================================================
# 顔検出
# =============================================================================

class FaceDetector:
    """MediaPipe Face Detection (Tasks API) ラッパー"""

    def __init__(self, min_confidence=MIN_DETECTION_CONFIDENCE):
        """
        Args:
            min_confidence: 検出信頼度の閾値
        """
        mp, cv2, np = _ensure_imports()

        # モデルパス取得
        model_path = _get_model_path()

        # Tasks APIでFaceDetectorを作成
        BaseOptions = mp.tasks.BaseOptions
        FaceDetector = mp.tasks.vision.FaceDetector
        FaceDetectorOptions = mp.tasks.vision.FaceDetectorOptions
        VisionRunningMode = mp.tasks.vision.RunningMode

        options = FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=VisionRunningMode.IMAGE,
            min_detection_confidence=min_confidence
        )

        self.detector = FaceDetector.create_from_options(options)
        self._previous_primary_id = None

    def detect(self, image):
        """
        画像から顔を検出

        Args:
            image: numpy array (BGR or RGB)

        Returns:
            list of dict: [{"roi": (x, y, w, h), "confidence": float, "id": int}, ...]
        """
        mp, cv2, np = _ensure_imports()

        # BGRならRGBに変換
        if len(image.shape) == 3 and image.shape[2] == 3:
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            rgb_image = image

        h, w = rgb_image.shape[:2]

        # MediaPipe Image形式に変換
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)

        # 検出実行
        results = self.detector.detect(mp_image)

        faces = []
        if results.detections:
            for idx, detection in enumerate(results.detections):
                bbox = detection.bounding_box

                # ピクセル座標を取得
                x = bbox.origin_x
                y = bbox.origin_y
                fw = bbox.width
                fh = bbox.height

                # 境界チェック
                x = max(0, x)
                y = max(0, y)
                fw = min(fw, w - x)
                fh = min(fh, h - y)

                # confidence scoreを取得
                confidence = detection.categories[0].score if detection.categories else 0.0

                faces.append({
                    "roi": (int(x), int(y), int(fw), int(fh)),
                    "confidence": float(confidence),
                    "id": idx
                })

        return faces

    def detect_with_expanded_roi(self, image, expand_ratio=ROI_EXPAND_RATIO):
        """
        顔検出 + ROI拡張（肌色領域を含める）

        Args:
            image: numpy array
            expand_ratio: ROI拡張倍率

        Returns:
            list of dict: 拡張済みROI情報
        """
        mp, cv2, np = _ensure_imports()

        faces = self.detect(image)
        h, w = image.shape[:2]

        expanded_faces = []
        for face in faces:
            x, y, fw, fh = face["roi"]

            # 中心点を基準に拡張
            cx, cy = x + fw // 2, y + fh // 2
            new_w = int(fw * expand_ratio)
            new_h = int(fh * expand_ratio)
            new_x = max(0, cx - new_w // 2)
            new_y = max(0, cy - new_h // 2)
            new_w = min(new_w, w - new_x)
            new_h = min(new_h, h - new_y)

            expanded_faces.append({
                "roi": (new_x, new_y, new_w, new_h),
                "original_roi": face["roi"],
                "confidence": face["confidence"],
                "id": face["id"]
            })

        return expanded_faces

    def close(self):
        """リソース解放"""
        if hasattr(self, 'detector') and self.detector:
            self.detector.close()


# =============================================================================
# シャープネス計算
# =============================================================================

def calculate_sharpness(image, roi=None):
    """
    ROI内のシャープネスを計算（Laplacian variance）

    Args:
        image: numpy array (BGR or grayscale)
        roi: (x, y, w, h) or None for full image

    Returns:
        float: シャープネス値（高いほどシャープ）
    """
    mp, cv2, np = _ensure_imports()

    # ROI抽出
    if roi:
        x, y, w, h = roi
        region = image[y:y+h, x:x+w]
    else:
        region = image

    # 空の領域チェック
    if region.size == 0:
        return 0.0

    # グレースケール変換
    if len(region.shape) == 3:
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    else:
        gray = region

    # Laplacian varianceでシャープネス計算
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    sharpness = laplacian.var()

    return sharpness


# =============================================================================
# Primary ROI選定
# =============================================================================

def select_primary_roi(faces, image, previous_primary_id=None,
                       hysteresis=HYSTERESIS_THRESHOLD,
                       sharpness_weight=SHARPNESS_WEIGHT):
    """
    Primary ROIを選定（シャープネス優先 + ヒステリシス）

    選定ロジック:
    1. confidence + sharpness_weight * normalized_sharpness でスコア算出
    2. 前回のPrimary ROIがあり、差がhysteresis以下なら維持
    3. それ以外は最高スコアを選択

    Args:
        faces: detect()の戻り値
        image: numpy array
        previous_primary_id: 前回のPrimary ROI ID
        hysteresis: ヒステリシス閾値
        sharpness_weight: シャープネスの重み

    Returns:
        dict or None: Primary ROI情報
    """
    if not faces:
        return None

    mp, cv2, np = _ensure_imports()

    # 各顔のシャープネスを計算
    for face in faces:
        face["sharpness"] = calculate_sharpness(image, face["roi"])

    # シャープネスを正規化（0-1）
    max_sharpness = max(f["sharpness"] for f in faces)
    if max_sharpness > 0:
        for face in faces:
            face["normalized_sharpness"] = face["sharpness"] / max_sharpness
    else:
        for face in faces:
            face["normalized_sharpness"] = 0.0

    # スコア算出
    for face in faces:
        face["score"] = (
            face["confidence"] * (1 - sharpness_weight) +
            face["normalized_sharpness"] * sharpness_weight
        )

    # 最高スコアのROIを取得
    best_face = max(faces, key=lambda f: f["score"])

    # ヒステリシス: 前回のPrimary ROIがあれば比較
    if previous_primary_id is not None:
        previous_face = next((f for f in faces if f["id"] == previous_primary_id), None)
        if previous_face:
            score_diff = best_face["score"] - previous_face["score"]
            if score_diff < hysteresis:
                # 差が小さいので前回を維持
                return previous_face

    return best_face


# =============================================================================
# ROI統計値算出
# =============================================================================

def calculate_roi_stats(image, roi=None):
    """
    ROI内の輝度・彩度統計値を算出

    Args:
        image: numpy array (BGR)
        roi: (x, y, w, h) or None for full image

    Returns:
        dict: {
            "luma_mean": float,
            "luma_std": float,
            "saturation_mean": float,
            "saturation_std": float,
            "pixel_count": int
        }
    """
    mp, cv2, np = _ensure_imports()

    # ROI抽出
    if roi:
        x, y, w, h = roi
        region = image[y:y+h, x:x+w]
    else:
        region = image

    # 空の領域チェック
    if region.size == 0:
        return {
            "luma_mean": 0.0,
            "luma_std": 0.0,
            "saturation_mean": 0.0,
            "saturation_std": 0.0,
            "pixel_count": 0
        }

    # HSV変換
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)

    # Vチャンネル = 輝度（0-255）
    v_channel = hsv[:, :, 2].astype(np.float32) / 255.0

    # Sチャンネル = 彩度（0-255）
    s_channel = hsv[:, :, 1].astype(np.float32) / 255.0

    return {
        "luma_mean": float(np.mean(v_channel)),
        "luma_std": float(np.std(v_channel)),
        "saturation_mean": float(np.mean(s_channel)),
        "saturation_std": float(np.std(s_channel)),
        "pixel_count": int(region.shape[0] * region.shape[1])
    }


# =============================================================================
# 統合処理
# =============================================================================

def analyze_frame(image, detector=None, previous_primary_id=None):
    """
    フレーム全体を解析してROI統計値を出力

    Args:
        image: numpy array (BGR)
        detector: FaceDetector instance (Noneなら新規作成)
        previous_primary_id: 前回のPrimary ROI ID

    Returns:
        dict: {
            "faces": [...],  # 検出された全顔
            "primary_roi": {...} or None,  # Primary ROI
            "roi_stats": {...},  # Primary ROI内統計
            "global_stats": {...},  # 全体統計
            "primary_id": int or None  # 次回用Primary ID
        }
    """
    mp, cv2, np = _ensure_imports()

    # 検出器の準備
    close_detector = False
    if detector is None:
        detector = FaceDetector()
        close_detector = True

    try:
        # 顔検出（拡張ROI付き）
        faces = detector.detect_with_expanded_roi(image)

        # Primary ROI選定
        primary = select_primary_roi(faces, image, previous_primary_id)

        # ROI統計
        if primary:
            roi_stats = calculate_roi_stats(image, primary["roi"])
            primary_id = primary["id"]
        else:
            roi_stats = None
            primary_id = None

        # 全体統計
        global_stats = calculate_roi_stats(image)

        return {
            "faces": faces,
            "primary_roi": primary,
            "roi_stats": roi_stats,
            "global_stats": global_stats,
            "primary_id": primary_id
        }

    finally:
        if close_detector:
            detector.close()


# =============================================================================
# ファイル入出力
# =============================================================================

def load_image(file_path):
    """画像ファイルを読み込み"""
    mp, cv2, np = _ensure_imports()

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Image not found: {file_path}")

    image = cv2.imread(file_path)
    if image is None:
        raise ValueError(f"Failed to load image: {file_path}")

    return image


def analyze_image_file(file_path, detector=None, previous_primary_id=None):
    """
    画像ファイルを解析

    Args:
        file_path: 画像ファイルパス
        detector: FaceDetector instance
        previous_primary_id: 前回のPrimary ID

    Returns:
        dict: analyze_frame()の戻り値
    """
    image = load_image(file_path)
    return analyze_frame(image, detector, previous_primary_id)


# =============================================================================
# テスト用
# =============================================================================

def _test_with_sample():
    """サンプル画像でテスト"""
    print("ROI Detector Test")
    print("=" * 50)

    # テスト用ダミー画像生成
    mp, cv2, np = _ensure_imports()

    # 640x480のテスト画像
    test_image = np.zeros((480, 640, 3), dtype=np.uint8)
    test_image[:] = (128, 128, 128)  # グレー背景

    # 顔検出器
    print("Creating FaceDetector...")
    detector = FaceDetector()

    try:
        print("Analyzing frame...")
        result = analyze_frame(test_image, detector)

        print(f"Faces detected: {len(result['faces'])}")
        print(f"Primary ROI: {result['primary_roi']}")
        print(f"Global stats: luma_mean={result['global_stats']['luma_mean']:.4f}")
        print("=" * 50)
        print("Test completed successfully!")

    finally:
        detector.close()


if __name__ == "__main__":
    _test_with_sample()
