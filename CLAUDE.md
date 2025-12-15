# 試験問題フォーマッター (saisei01)

## 概要
複数の教員から回収した試験問題（穴埋め問題）を統一フォーマットに整形するWebアプリケーション。

## デプロイ環境
- Synology NAS + Portainer Stack
- ポート: 8701
- URL: `http://<NAS_IP>:8701`

## ファイル構成
```
saisei01/
├── CLAUDE.md           # このファイル（プロジェクト説明）
├── docker-compose.yml  # Portainer用構成ファイル
├── Dockerfile          # コンテナビルド定義
├── app.py              # Flaskアプリ本体
├── requirements.txt    # Python依存ライブラリ
└── templates/
    └── index.html      # 画面テンプレート
```

## 整形ルール

### 1. 空欄の入力形式（様々な形式に対応）
- `(A)` `（A）` `(A）` `（A)` - 括弧付きアルファベット
- `( )` `（ ）` - 空の括弧
- `___` - アンダースコア
- `A` `B` `C` - 単独アルファベット（日本語文中）

### 2. 空欄の出力形式
- 空欄1つ: `（　　　　　）`
- 空欄2つ以上: `（　　A　　）`、`（　　B　　）` ...

### 3. 指示文の自動付与
- 空欄あり: 「以下の記述の空欄に適切な語句を記入せよ。」を冒頭に追加
- 空欄なし: 指示文なし

### 4. 文体変換
- ですます調 → である調に変換
- 例: 「〜します」→「〜する」、「〜です」→「〜である」

### 5. 正解の形式
- 空欄1つ: `正解：○○`
- 空欄2つ以上: `正解：A. ○○　B. △△`

### 6. 除外される専門用語（空欄として認識しない）
- A型、B型（血液型など）
- T細胞、B細胞、NK細胞
- その他の医学用語（〜抗原、〜受容体など）

## Portainerからのデプロイ手順

1. Portainer にログイン
2. Stacks → Add stack
3. 名前: `saisei01`
4. Build method: **Repository** を選択
5. Repository URL: `https://github.com/<username>/saisei01`
6. Compose path: `docker-compose.yml`
7. Deploy the stack

## 更新手順

1. GitHubのファイルを更新
2. Portainer → Stacks → saisei01
3. 「Pull and redeploy」をクリック

## トラブルシューティング

### コンテナが起動しない
Portainer → Containers → saisei01 → Logs でエラーを確認

### ポートが使用中
docker-compose.ymlの `8701:5000` を別のポートに変更

### 変更が反映されない
Portainer → Stacks → saisei01 → 「Pull and redeploy」
