# ==============================================================================
# LLM Council - Makefile
# ==============================================================================
# 使用方法: make help

.PHONY: help \
        install install-dev install-frontend install-all \
        dev dev-backend dev-frontend \
        test test-unit test-memory test-cov \
        lint build build-check \
        docker-build docker-run docker-run-detached docker-stop docker-logs docker-shell docker-push \
        ar-setup \
        clean clean-all \
        data-backup data-reset \
        deploy deploy-with-gcs deploy-status deploy-logs deploy-url \
        secret-create-openrouter secret-create-tavily secret-update-openrouter secret-update-tavily secret-list \
        iam-setup gcs-cleanup gcs-delete-bucket \
        env-check status

# デフォルトターゲット
.DEFAULT_GOAL := help

# ------------------------------------------------------------------------------
# 設定
# ------------------------------------------------------------------------------
DOCKER_IMAGE := llm-council
DOCKER_TAG := latest
BACKEND_PORT := 8000
FRONTEND_PORT := 5173

# ------------------------------------------------------------------------------
# ヘルプ
# ------------------------------------------------------------------------------
help: ## このヘルプを表示
	@echo "LLM Council - 利用可能なコマンド:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "開発フロー:"
	@echo "  1. make install-all     - 依存関係をインストール"
	@echo "  2. make dev             - バックエンド＋フロントエンド同時起動"
	@echo ""
	@echo "デプロイフロー（初回）:"
	@echo "  1. make ar-setup              - Artifact Registryをセットアップ"
	@echo "  2. make secret-create-openrouter - OpenRouter APIキーを登録"
	@echo "  3. make secret-create-tavily  - Tavily APIキーを登録"
	@echo "  4. make deploy                - Cloud Runにデプロイ"
	@echo "  5. make iam-setup             - 権限設定（必要な場合）"
	@echo ""
	@echo "デプロイフロー（更新）:"
	@echo "  - make deploy                 - Cloud Runにデプロイ（常にキャッシュなしビルド）"
	@echo ""

# ------------------------------------------------------------------------------
# インストール
# ------------------------------------------------------------------------------
install: ## Python依存関係をインストール
	uv sync

install-dev: ## 開発用依存関係をインストール（テスト含む）
	uv sync --all-extras

install-frontend: ## フロントエンド依存関係をインストール
	cd frontend && npm install

install-all: install-dev install-frontend ## すべての依存関係をインストール

# ------------------------------------------------------------------------------
# 開発サーバー
# ------------------------------------------------------------------------------
dev: ## バックエンド＋フロントエンドを同時起動
	@echo "バックエンド: http://localhost:$(BACKEND_PORT)"
	@echo "フロントエンド: http://localhost:$(FRONTEND_PORT)"
	@echo "Ctrl+C で両方停止"
	@trap 'kill 0' EXIT; \
		uv run uvicorn backend.main:app --reload --port $(BACKEND_PORT) & \
		cd frontend && npm run dev

dev-backend: ## バックエンドのみ起動（ホットリロード有効）
	uv run uvicorn backend.main:app --reload --port $(BACKEND_PORT)

dev-frontend: ## フロントエンドのみ起動
	cd frontend && npm run dev

# ------------------------------------------------------------------------------
# テスト
# ------------------------------------------------------------------------------
test: ## すべてのテストを実行
	uv run pytest -v

test-unit: ## 単体テストのみ実行
	uv run pytest tests/ -v --ignore=tests/e2e/

test-memory: ## メモリ関連テストを実行
	uv run pytest tests/test_memory.py -v

test-cov: ## カバレッジ付きでテストを実行
	uv run pytest --cov=backend --cov-report=term-missing

# ------------------------------------------------------------------------------
# リント・フォーマット
# ------------------------------------------------------------------------------
lint: ## フロントエンドのESLintを実行
	cd frontend && npm run lint

# ------------------------------------------------------------------------------
# ビルド
# ------------------------------------------------------------------------------
build: ## フロントエンドをビルド
	cd frontend && npm run build

build-check: build ## ビルド後に成果物を確認
	@echo "ビルド成果物:"
	@ls -la frontend/dist/

# ------------------------------------------------------------------------------
# Docker & Artifact Registry
# ------------------------------------------------------------------------------
AR_REGION := asia-northeast1
AR_REPO := llm-council
# 遅延評価（=）でGCP_PROJECTが後で定義されても正しく展開される
AR_IMAGE = $(AR_REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(AR_REPO)/app

docker-build: ## Dockerイメージをビルド
	docker build -t $(DOCKER_IMAGE):$(DOCKER_TAG) .

docker-run: ## Dockerコンテナを起動
	docker run -p 8080:8080 --env-file .env $(DOCKER_IMAGE):$(DOCKER_TAG)

docker-run-detached: ## Dockerコンテナをバックグラウンドで起動
	docker run -d -p 8080:8080 --env-file .env --name $(DOCKER_IMAGE) $(DOCKER_IMAGE):$(DOCKER_TAG)

docker-stop: ## Dockerコンテナを停止
	docker stop $(DOCKER_IMAGE) || true
	docker rm $(DOCKER_IMAGE) || true

docker-logs: ## Dockerコンテナのログを表示
	docker logs -f $(DOCKER_IMAGE)

docker-shell: ## Dockerコンテナにシェルで接続
	docker exec -it $(DOCKER_IMAGE) /bin/bash

docker-push: ## Artifact RegistryにDockerイメージをビルド＆push（常にキャッシュなし）
	@echo "=== キャッシュなしでビルド＆プッシュ ==="
	docker build --no-cache -t $(AR_IMAGE):$(DOCKER_TAG) .
	docker push $(AR_IMAGE):$(DOCKER_TAG)
	@echo "✓ プッシュ完了: $(AR_IMAGE):$(DOCKER_TAG)"

ar-setup: ## Artifact Registryのリポジトリを作成（初回のみ）
	@echo "Artifact Registryリポジトリを作成..."
	gcloud artifacts repositories create $(AR_REPO) \
		--repository-format=docker \
		--location=$(AR_REGION) \
		--description="LLM Council Docker images" || echo "既に存在します"
	@echo "Docker認証を設定..."
	gcloud auth configure-docker $(AR_REGION)-docker.pkg.dev --quiet
	@echo "✓ セットアップ完了"

# ------------------------------------------------------------------------------
# クリーンアップ
# ------------------------------------------------------------------------------
clean: ## ビルド成果物とキャッシュを削除
	rm -rf frontend/dist
	rm -rf frontend/node_modules/.vite
	rm -rf __pycache__
	rm -rf backend/__pycache__
	rm -rf tests/__pycache__
	rm -rf .pytest_cache
	rm -rf .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

clean-all: clean ## すべての依存関係も含めて削除
	rm -rf frontend/node_modules
	rm -rf .venv

# ------------------------------------------------------------------------------
# データ管理
# ------------------------------------------------------------------------------
data-backup: ## データディレクトリをバックアップ
	@mkdir -p backups
	@tar -czvf backups/data-$$(date +%Y%m%d-%H%M%S).tar.gz data/

data-reset: ## ローカルデータをリセット（注意: データが消えます）
	@read -p "本当にデータをリセットしますか？ [y/N] " confirm && [ "$$confirm" = "y" ] && rm -rf data/projects/*/conversations/* data/projects/*/memory.json data/projects/*/summaries.json || echo "キャンセルしました"

# ------------------------------------------------------------------------------
# GCP デプロイ（Secret Manager対応）
# ------------------------------------------------------------------------------
# 設定（必要に応じて変更）
GCP_PROJECT := $(shell gcloud config get-value project 2>/dev/null)
GCP_REGION := asia-northeast1
CLOUD_RUN_SERVICE := llm-council
SECRET_OPENROUTER := openrouter-api-key
SECRET_TAVILY := tavily-api-key

# シークレット管理
secret-create-openrouter: ## OpenRouter APIキーをSecret Managerに作成
	@echo "シークレット '$(SECRET_OPENROUTER)' を作成します..."
	@read -p "OPENROUTER_API_KEYを入力: " key && \
		echo -n "$$key" | gcloud secrets create $(SECRET_OPENROUTER) --data-file=- --replication-policy="automatic" || \
		echo "既に存在する場合は secret-update-openrouter を使用してください"

secret-create-tavily: ## Tavily APIキーをSecret Managerに作成
	@echo "シークレット '$(SECRET_TAVILY)' を作成します..."
	@read -p "TAVILY_API_KEYを入力: " key && \
		echo -n "$$key" | gcloud secrets create $(SECRET_TAVILY) --data-file=- --replication-policy="automatic" || \
		echo "既に存在する場合は secret-update-tavily を使用してください"

secret-update-openrouter: ## OpenRouter APIキーを更新
	@echo "シークレット '$(SECRET_OPENROUTER)' を更新します..."
	@read -p "新しいOPENROUTER_API_KEYを入力: " key && \
		echo -n "$$key" | gcloud secrets versions add $(SECRET_OPENROUTER) --data-file=-
	@echo "✓ 新しいバージョンが追加されました"

secret-update-tavily: ## Tavily APIキーを更新
	@echo "シークレット '$(SECRET_TAVILY)' を更新します..."
	@read -p "新しいTAVILY_API_KEYを入力: " key && \
		echo -n "$$key" | gcloud secrets versions add $(SECRET_TAVILY) --data-file=-
	@echo "✓ 新しいバージョンが追加されました"

secret-list: ## シークレット一覧を表示
	@echo "=== OpenRouter API Key ==="
	gcloud secrets versions list $(SECRET_OPENROUTER) 2>/dev/null || echo "未作成"
	@echo ""
	@echo "=== Tavily API Key ==="
	gcloud secrets versions list $(SECRET_TAVILY) 2>/dev/null || echo "未作成"

# Cloud Run デプロイ
deploy: docker-push ## Cloud Runにデプロイ（常にキャッシュなしビルド）
	@echo "=== GCP Cloud Run デプロイ ==="
	@echo "プロジェクト: $(GCP_PROJECT)"
	@echo "リージョン: $(GCP_REGION)"
	@echo "サービス: $(CLOUD_RUN_SERVICE)"
	@echo "イメージ: $(AR_IMAGE):$(DOCKER_TAG)"
	@echo ""
	gcloud run deploy $(CLOUD_RUN_SERVICE) \
		--image $(AR_IMAGE):$(DOCKER_TAG) \
		--region $(GCP_REGION) \
		--platform managed \
		--no-allow-unauthenticated \
		--set-secrets="OPENROUTER_API_KEY=$(SECRET_OPENROUTER):latest,TAVILY_API_KEY=$(SECRET_TAVILY):latest" \
		--memory 4Gi \
		--cpu 1 \
		--min-instances 0 \
		--max-instances 1
	@echo ""
	@echo "✓ デプロイ完了（IAM認証有効）"
	@echo "アクセスするには: gcloud run services proxy $(CLOUD_RUN_SERVICE) --region $(GCP_REGION)"

deploy-with-gcs: docker-push ## Cloud Runにデプロイ（GCSバケット指定・IAM認証）
	@read -p "GCSバケット名を入力: " bucket && \
	gcloud run deploy $(CLOUD_RUN_SERVICE) \
		--image $(AR_IMAGE):$(DOCKER_TAG) \
		--region $(GCP_REGION) \
		--platform managed \
		--no-allow-unauthenticated \
		--set-secrets="OPENROUTER_API_KEY=$(SECRET_OPENROUTER):latest,TAVILY_API_KEY=$(SECRET_TAVILY):latest" \
		--set-env-vars="STORAGE_BACKEND=gcs,GCS_BUCKET=$$bucket" \
		--memory 8Gi \
		--cpu 2 \
		--min-instances 0 \
		--max-instances 2

deploy-status: ## デプロイ状況を確認
	gcloud run services describe $(CLOUD_RUN_SERVICE) --region $(GCP_REGION) --format="yaml(status)"

deploy-logs: ## Cloud Runのログを表示
	gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$(CLOUD_RUN_SERVICE)" \
		--limit 50 --format "table(timestamp,textPayload)"

deploy-url: ## デプロイされたサービスのURLを表示
	@gcloud run services describe $(CLOUD_RUN_SERVICE) --region $(GCP_REGION) --format="value(status.url)"

# IAM設定
iam-setup: ## Secret Managerへのアクセス権限を設定
	@echo "Cloud Runサービスアカウントにシークレットアクセス権限を付与..."
	@SA=$$(gcloud run services describe $(CLOUD_RUN_SERVICE) --region $(GCP_REGION) --format="value(spec.template.spec.serviceAccountName)" 2>/dev/null || echo "$(GCP_PROJECT)-compute@developer.gserviceaccount.com"); \
	echo "サービスアカウント: $$SA"; \
	gcloud secrets add-iam-policy-binding $(SECRET_OPENROUTER) \
		--member="serviceAccount:$$SA" \
		--role="roles/secretmanager.secretAccessor" --quiet && \
	gcloud secrets add-iam-policy-binding $(SECRET_TAVILY) \
		--member="serviceAccount:$$SA" \
		--role="roles/secretmanager.secretAccessor" --quiet
	@echo "✓ 両シークレットへの権限が付与されました"

gcs-cleanup: ## ソースデプロイ用GCSバケットの古いファイルを削除
	@echo "=== GCSバケットのクリーンアップ ==="
	@BUCKET="run-sources-$(GCP_PROJECT)-$(GCP_REGION)"; \
	echo "バケット: gs://$$BUCKET"; \
	FILES=$$(gsutil ls "gs://$$BUCKET/services/$(CLOUD_RUN_SERVICE)/" 2>/dev/null | head -n -1); \
	if [ -n "$$FILES" ]; then \
		echo "削除対象（最新1つを除く）:"; \
		echo "$$FILES"; \
		echo "$$FILES" | xargs -I {} gsutil rm {}; \
		echo "✓ クリーンアップ完了"; \
	else \
		echo "削除対象なし"; \
	fi

gcs-delete-bucket: ## ソースデプロイ用GCSバケットを完全削除（--image移行後）
	@echo "=== GCSバケットを削除 ==="
	@BUCKET="run-sources-$(GCP_PROJECT)-$(GCP_REGION)"; \
	read -p "gs://$$BUCKET を削除しますか？ [y/N] " confirm && [ "$$confirm" = "y" ] && \
		gsutil -m rm -r "gs://$$BUCKET" && echo "✓ 削除完了" || echo "キャンセルしました"

# ------------------------------------------------------------------------------
# ユーティリティ
# ------------------------------------------------------------------------------
env-check: ## 環境変数の設定状況を確認
	@echo "=== 環境変数チェック ==="
	@test -f .env && echo "✓ .env ファイルが存在します" || echo "✗ .env ファイルがありません"
	@test -n "$$OPENROUTER_API_KEY" && echo "✓ OPENROUTER_API_KEY が設定されています" || echo "✗ OPENROUTER_API_KEY が未設定です"
	@test -n "$$STORAGE_BACKEND" && echo "✓ STORAGE_BACKEND: $$STORAGE_BACKEND" || echo "- STORAGE_BACKEND: 未設定（デフォルト: local）"
	@test -n "$$GCS_BUCKET" && echo "✓ GCS_BUCKET: $$GCS_BUCKET" || echo "- GCS_BUCKET: 未設定"

status: ## プロジェクトの状態を表示
	@echo "=== Git Status ==="
	@git status --short
	@echo ""
	@echo "=== Python Version ==="
	@python --version
	@echo ""
	@echo "=== Node Version ==="
	@node --version
	@echo ""
	@echo "=== uv Version ==="
	@uv --version
