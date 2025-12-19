# Phase 0：DaVinci Resolve 連携 API 設計（確定案）

## 0. Phase 0 のゴール（再定義）

外部から渡された「数値パラメータ」を Resolve のノードに安定して・再現性高く反映できること

この時点では：
- 自動推定 ❌
- AI ❌
- 判断 ❌

> 純粋に「配線」を作るフェーズ

---

## 1. 採用技術スタック（固定）

### Resolve API
- DaVinci Resolve Python API
- Resolve 18.x 前提

### スクリプト配置
- Resolve Script フォルダ
- UI から実行可能

### 外部連携
- JSON ファイル or Python dict
- STDIN / HTTP は使わない（Phase 0）

---

## 2. データ受け渡し仕様（最重要）

### 入力データ仕様（固定）

```json
{
  "camera": "Sony S-Log3",
  "exposure_ev": 0.6,
  "wb_temp_delta": 300,
  "wb_tint_delta": -4,
  "contrast_factor": 1.08
}
```

### 制約
- キー名は固定
- 単位も固定（EV / Kelvin）
- 無いキーは「何もしない」

> この仕様は Phase 2 以降も不変

---

## 3. 実装方式：SetCDL

### ASC-CDL形式

DaVinci Resolve の `SetCDL()` API を使用。

```python
cdl_map = {
    "NodeIndex": "1",
    "Slope": "1.5157 1.5157 1.5157",
    "Offset": "0.0000 0.0000 0.0000",
    "Power": "0.9259 0.9259 0.9259",
    "Saturation": "1.0000"
}
clip.SetCDL(cdl_map)
```

### パラメータ変換

| 入力 | CDL | 変換式 |
|------|-----|--------|
| exposure_ev | Slope | `pow(2, exposure_ev)` |
| contrast_factor | Power | `1.0 / contrast_factor` |

---

## 4. UI要件（最低限）

### UI構成
- Resolve Scripts メニューから実行
- 実行結果をコンソールログ表示

### ログ例

```
Camera: Sony S-Log3
Exposure: +0.6 EV
Contrast: 1.08
SetCDL result: True
[SUCCESS] CDL applied successfully!
```

---

## 5. エラー・保護設計

### ガード条件
- 対象クリップ未選択 → 処理中止
- 値が異常（±5EVなど）→ Clamp

### Clamp例

```python
exposure_ev = max(min(exposure_ev, 2.0), -2.0)
```

---

## 6. Phase 0 完了条件（明確）

### Done条件
- 手動入力パラメータで
- SetCDL が True を返す
- 映像が変化する（明るく/暗く）
- 同じパラメータで同じ結果

### Not Done
- 値が揺れる
- 毎回結果が違う
- SetCDL が False
