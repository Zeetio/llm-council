# LLM Council

![llmcouncil](header.jpg)

複数のLLMを「評議会」として集め、クエリに対して協調的に回答を生成するWebアプリケーション。

## 概要

単一のLLMに質問する代わりに、複数のLLM（OpenAI、Google、Anthropic、xAI等）を評議会メンバーとしてグループ化し、以下の3段階プロセスで最終回答を生成します：

1. **Stage 1: 個別回答** - 各LLMが独立してクエリに回答
2. **Stage 2: 相互レビュー** - 各LLMが他のLLMの回答を匿名でレビュー・ランキング
3. **Stage 3: 最終回答** - 議長LLMが全ての回答を統合して最終回答を生成

## 主要機能

- 複数LLMへの同時クエリ
- 回答の相互レビューとランキング
- プロジェクト別の設定管理
- パスワード保護プロジェクト
- ユーザーメモリ機能
- 会話履歴の管理（作成・削除）
- SSEストリーミングによるリアルタイム回答表示

## セットアップ

### 前提条件

- Python 3.11+
- Node.js 20+
- [uv](https://docs.astral.sh/uv/) (Pythonパッケージマネージャー)
- Docker（デプロイ用）
- Google Cloud CLI（Cloud Runデプロイ用）

### 1. 依存関係のインストール

```bash
# 全ての依存関係をインストール
make install-all

# または個別に
uv sync                    # Python
cd frontend && npm install  # フロントエンド
```

### 2. 環境変数の設定

プロジェクトルートに `.env` ファイルを作成：

```bash
OPENROUTER_API_KEY=sk-or-v1-...
TAVILY_API_KEY=tvly-...          # オプション: Web検索機能用
STORAGE_BACKEND=local            # local または gcs
GCS_BUCKET=your-bucket-name      # GCS使用時のみ
```

APIキーは [openrouter.ai](https://openrouter.ai/) で取得できます。

## ローカル開発

```bash
# バックエンド + フロントエンドを同時起動
make dev

# または個別に
make dev-backend   # バックエンド: http://localhost:8001
make dev-frontend  # フロントエンド: http://localhost:5173
```

ブラウザで <http://localhost:5173> を開きます。

## Cloud Run デプロイ

### 初回セットアップ

```bash
# 1. Artifact Registryをセットアップ
make ar-setup

# 2. シークレットを登録
make secret-create-openrouter
make secret-create-tavily

# 3. デプロイ
make deploy

# 4. 権限設定（必要な場合）
make iam-setup
```

### 更新デプロイ

```bash
make deploy
```

### ローカルからCloud Runにアクセス

```bash
gcloud run services proxy llm-council --region asia-northeast1
```

## 主要なMakeコマンド

| コマンド | 説明 |
| ------- | ---- |
| `make help` | 利用可能なコマンド一覧 |
| `make install-all` | 全依存関係のインストール |
| `make dev` | ローカル開発サーバー起動 |
| `make build` | フロントエンドビルド |
| `make docker-build` | Dockerイメージビルド |
| `make deploy` | Cloud Runにデプロイ |
| `make deploy-status` | デプロイ状況確認 |
| `make deploy-logs` | デプロイログ表示 |
| `make test` | テスト実行 |

## プロジェクト構造

```text
llm-council/
├── backend/
│   ├── main.py          # FastAPI エンドポイント
│   ├── council.py       # LLM評議会ロジック
│   ├── storage.py       # ストレージバックエンド（Local/GCS）
│   └── config.py        # デフォルト設定
├── frontend/
│   ├── src/
│   │   ├── App.jsx      # メインアプリ
│   │   ├── api.js       # APIクライアント
│   │   └── components/  # UIコンポーネント
│   └── .env.development # 開発環境設定
├── Makefile             # ビルド・デプロイコマンド
├── Dockerfile           # マルチステージビルド
└── pyproject.toml       # Python依存関係
```

## 技術スタック

- **バックエンド:** FastAPI, Python 3.11+, async httpx, OpenRouter API
- **フロントエンド:** React 19, Vite, react-markdown
- **ストレージ:** JSON (ローカル) / GCS (本番)
- **デプロイ:** Docker, Google Cloud Run, Artifact Registry
- **パッケージ管理:** uv (Python), npm (JavaScript)

## ライセンス

MIT
