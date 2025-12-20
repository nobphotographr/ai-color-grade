# AI Color Grade

DaVinci Resolve 用 AI カラーグレーディング自動化ツール

## 概要

Sony S-Log3 素材を対象とした、AI による自動カラーグレーディングシステム。
顔検出による肌トーン基準の露出補正を実現。

## 現在のステータス

**Phase 2: 顔検出 + スマート露出補正** - ✅ 完了 (2024-12-20)

- [x] 高解像度スチル書き出し（ExportCurrentFrameAsStill）
- [x] MediaPipe Face Detection による顔検出
- [x] ROI（顔領域）統計値算出
- [x] 肌トーン基準の露出補正（顔70% + 全体30%の重み付け）
- [x] S-Log3用コントラスト補正（1.25）

**Phase 1: シーン分類 + ルールベース補正** - ✅ 完了 (2024-12-20)

- [x] サムネイルからメトリクス抽出（輝度・彩度・ハイライト/シャドウ比率）
- [x] シーン自動分類（outdoor_day / indoor_human / night / slog3_base）
- [x] ルールベース補正パラメータ適用
- [x] S-Log3自動検出

**Phase 0: Resolve連携の土台** - ✅ 完了 (2024-12-20)

- [x] Resolve Python API 接続
- [x] クリップ取得・ノード操作
- [x] SetCDL による色補正反映

## 要件

- DaVinci Resolve Studio 18.x 以上
- Python 3.6 以上
- Windows 10/11

### Python パッケージ

```bash
pip install mediapipe opencv-python numpy
```

## セットアップ

### 1. PYTHONPATH 設定

PowerShell（管理者）で実行:

```powershell
[Environment]::SetEnvironmentVariable("PYTHONPATH", "C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules", "User")
```

### 2. スクリプト配置

`scripts/` フォルダ内のファイルを以下にコピー:

```
%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Color\AIColorGrade\
```

必要ファイル:
- `apply_grade_phase1.py` - Phase 1 シーン分類補正
- `apply_grade_phase2.py` - Phase 2 顔検出スマート補正
- `roi_detector.py` - 顔検出モジュール
- `exposure_calculator.py` - 露出計算モジュール

### 3. Resolve 設定

Preferences → System → General → External scripting using → **Local**

## 使用方法

### Phase 2（推奨）: 顔検出スマート補正

1. DaVinci Resolve でプロジェクトを開く
2. Color ページでクリップを選択
3. 解析したいフレームにプレイヘッドを移動
4. **Workspace → Scripts → AIColorGrade → apply_grade_phase2** を実行

顔が検出された場合、肌トーンを基準に露出補正が適用されます。

### Phase 1: シーン分類補正

1. Color ページでクリップを選択
2. **Workspace → Scripts → AIColorGrade → apply_grade_phase1** を実行

S-Log3素材は自動検出され、適切な補正が適用されます。

## 補正パラメータ

### Phase 2 設定

| パラメータ | 値 | 説明 |
|-----------|------|------|
| 肌トーン目標輝度 | 0.50 | Rec.709での理想的な肌の明るさ |
| 顔領域重み | 70% | 露出計算における顔の重要度 |
| コントラスト | 1.25 | S-Log3用ベースコントラスト |

### Phase 1 シーン別補正

| シーンタイプ | 露出 (EV) | コントラスト |
|-------------|-----------|--------------|
| slog3_base | +0.8 | 1.1 |
| outdoor_day | -0.3 | 1.05 |
| indoor_human | 0.0 | 1.0 |
| night | +0.5 | 1.15 |

## 開発ロードマップ

| Phase | 内容 | 状態 |
|-------|------|------|
| 0 | Resolve連携の土台 | ✅ 完了 |
| 1 | シーン分類 + ルールベース補正 | ✅ 完了 |
| 2 | 顔検出 + スマート露出補正 | ✅ 完了 |
| 3 | ルック選択・カラーマッチング | 未着手 |

## ライセンス

MIT License
