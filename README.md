# AI Color Grade

DaVinci Resolve 用 AI カラーグレーディング自動化ツール

## 概要

Sony S-Log3 素材を対象とした、AI による自動カラーグレーディングシステム。
Phase 0 では Resolve API との連携基盤を構築。

## 現在のステータス

**Phase 0: Resolve連携の土台** - ✅ 完了 (2024-12-20)

- [x] Resolve Python API 接続
- [x] クリップ取得・ノード操作
- [x] SetCDL による色補正反映
- [x] JSON パラメータ読み込み
- [x] 完成版スクリプト

## 要件

- DaVinci Resolve Studio 18.x 以上
- Python 3.6 以上
- Windows 10/11

## セットアップ

### 1. PYTHONPATH 設定

PowerShell（管理者）で実行:

```powershell
[Environment]::SetEnvironmentVariable("PYTHONPATH", "C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules", "User")
```

### 2. スクリプト配置

`scripts/apply_grade.py` を以下にコピー:

```
%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Color\
```

### 3. Resolve 設定

Preferences → System → General → External scripting using → **Local**

## 使用方法

1. DaVinci Resolve でプロジェクトを開く
2. タイムラインにクリップを配置
3. Color ページでクリップを選択
4. Workspace → Scripts → apply_grade を実行

## 入力パラメータ仕様

```json
{
  "camera": "Sony S-Log3",
  "exposure_ev": 0.6,
  "wb_temp_delta": 300,
  "wb_tint_delta": -4,
  "contrast_factor": 1.08
}
```

| パラメータ | 説明 | 範囲 |
|-----------|------|------|
| exposure_ev | 露出補正 (EV) | -2.0 ~ 2.0 |
| wb_temp_delta | 色温度補正 (K) | -2000 ~ 2000 |
| wb_tint_delta | ティント補正 | -100 ~ 100 |
| contrast_factor | コントラスト係数 | 0.5 ~ 2.0 |

## 開発ロードマップ

| Phase | 内容 | 状態 |
|-------|------|------|
| 0 | Resolve連携の土台 | ✅ 完了 |
| 1 | シーン分類 + ルールベース補正 | 未着手 |
| 2 | 基本補正推定モデル導入 | 未着手 |
| 3 | ルック選択 | 未着手 |

## ライセンス

MIT License
