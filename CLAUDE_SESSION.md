# AI Color Grade - Claude Code セッション再開用メモ

## プロジェクト概要
DaVinci Resolve用AIカラーグレーディング自動化ツール（Sony S-Log3対象）

## GitHubリポジトリ
https://github.com/nobphotographr/ai-color-grade

## ファイル配置

### Resolveスクリプト（実行用）
```
C:\Users\nobuy\AppData\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Color\AIColorGrade\
├── apply_grade.py
└── test_connection.py
```

### パラメータファイル
```
C:\Users\nobuy\Documents\params.json
```

### Gitリポジトリ（開発・管理用）
```
C:\Users\nobuy\Documents\ai-color-grade-repo\
├── scripts\
│   ├── apply_grade.py
│   └── params.json
├── docs\
├── README.md
└── .gitignore
```

## 現在の進捗

| Phase | 内容 | 状態 |
|-------|------|------|
| 0 | Resolve連携の土台 | ✅ 完了 (2024-12-20) |
| 1 | シーン分類 + ルールベース補正 | 未着手 |
| 2 | 基本補正推定モデル導入 | 未着手 |
| 3 | ルック選択 | 未着手 |

## セッション再開時のコピペ用テキスト

```
AI Color Gradeプロジェクトの続きをお願いします。

■ GitHub: https://github.com/nobphotographr/ai-color-grade

■ ファイル配置:
- Resolveスクリプト: C:\Users\nobuy\AppData\Roaming\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Color\AIColorGrade\
- Gitリポジトリ: C:\Users\nobuy\Documents\ai-color-grade-repo\
- パラメータ: C:\Users\nobuy\Documents\params.json

■ 現在の状態: Phase 0 完了、Phase 1 未着手

■ 今回やりたいこと:
（ここに具体的なタスクを書く）
```

## 開発フロー
1. `ai-color-grade-repo` でコード編集
2. `Scripts\Color\AIColorGrade\` にコピーしてResolve動作確認
3. 動作OKならgit commit & push

## 技術メモ
- Resolve API: DaVinciResolveScript モジュール使用
- CDL適用: `clip.SetCDL()` メソッド
- パラメータ形式: JSON（露出EV、色温度、ティント、コントラスト）
