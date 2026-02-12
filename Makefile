# ==============================================================================
# LLM Council - Makefile
# ==============================================================================
# 使用方法: make help

.PHONY: help \
        install install-dev install-frontend install-all \
        dev dev-backend dev-frontend \
        test test-unit test-memory test-cov \
        lint build \
        docker-build docker-run docker-stop docker-logs \
        deploy deploy-status deploy-logs deploy-url \
        secret-update-openrouter secret-update-tavily secret-list \
        clean clean-all status

# デフォルトターゲット
.DEFAULT_GOAL := help

# ------------------------------------------------------------------------------
# GCP設定（固定値）
# ------------------------------------------------------------------------------
GCP_PROJECT := gen-lang-client-0381091775
GCP_REGION := asia-northeast1
CLOUD_RUN_SERVICE := llm-council
GCS_BUCKET := llm-council-data-gen-lang-client-0381091775
SECRET_OPENROUTER := openrouter-api-key
SECRET_TAVILY := tavily-api-key

# Docker設定
DOCKER_IMAGE := llm-council
DOCKER_TAG := latest
AR_REGION := $(GCP_REGION)
AR_REPO := llm-council
AR_IMAGE := $(AR_REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(AR_REPO)/app
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
	@echo "基本フロー:"
	@echo "  開発:   make dev"
	@echo "  デプロイ: make deploy"
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

dev-backend: ## バックエンドのみ起動
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
# リント・ビルド
# ------------------------------------------------------------------------------
lint: ## フロントエンドのESLintを実行
	cd frontend && npm run lint

build: ## フロントエンドをビルド
	cd frontend && npm run build

# ------------------------------------------------------------------------------
# Docker（ローカル開発用）
# ------------------------------------------------------------------------------
docker-build: ## Dockerイメージをビルド
	docker build -t $(DOCKER_IMAGE):$(DOCKER_TAG) .

docker-run: ## Dockerコンテナを起動
	docker run -p 8080:8080 --env-file .env $(DOCKER_IMAGE):$(DOCKER_TAG)

docker-stop: ## Dockerコンテナを停止
	docker stop $(DOCKER_IMAGE) || true
	docker rm $(DOCKER_IMAGE) || true

docker-logs: ## Dockerコンテナのログを表示
	docker logs -f $(DOCKER_IMAGE)

# ------------------------------------------------------------------------------
# デプロイ（Cloud Run + GCS永続化）
# ------------------------------------------------------------------------------
deploy: ## Cloud Runにデプロイ（コード更新）
	@echo "=== Cloud Run デプロイ ==="
	@echo "イメージビルド中..."
	docker build --no-cache -t $(AR_IMAGE):$(DOCKER_TAG) .
	@echo "プッシュ中..."
	docker push $(AR_IMAGE):$(DOCKER_TAG)
	@echo "デプロイ中..."
	gcloud run deploy $(CLOUD_RUN_SERVICE) \
		--image $(AR_IMAGE):$(DOCKER_TAG) \
		--region $(GCP_REGION) \
		--platform managed \
		--allow-unauthenticated \
		--set-secrets="OPENROUTER_API_KEY=$(SECRET_OPENROUTER):latest,TAVILY_API_KEY=$(SECRET_TAVILY):latest" \
		--set-env-vars="STORAGE_BACKEND=gcs,GCS_BUCKET=$(GCS_BUCKET)" \
		--memory 4Gi \
		--cpu 1 \
		--min-instances 0 \
		--max-instances 1 \
		--timeout 300
	@echo ""
	@echo "✓ デプロイ完了"
	@echo "URL: $$(gcloud run services describe $(CLOUD_RUN_SERVICE) --region $(GCP_REGION) --format='value(status.url)')"

deploy-status: ## デプロイ状況を確認
	gcloud run services describe $(CLOUD_RUN_SERVICE) --region $(GCP_REGION) --format="yaml(status)"

deploy-logs: ## Cloud Runのログを表示
	gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$(CLOUD_RUN_SERVICE)" \
		--limit 50 --format "table(timestamp,textPayload)"

deploy-url: ## デプロイURLを表示
	@gcloud run services describe $(CLOUD_RUN_SERVICE) --region $(GCP_REGION) --format="value(status.url)"

# ------------------------------------------------------------------------------
# シークレット管理
# ------------------------------------------------------------------------------
secret-update-openrouter: ## OpenRouter APIキーを更新
	@read -p "新しいOPENROUTER_API_KEYを入力: " key && \
		echo -n "$$key" | gcloud secrets versions add $(SECRET_OPENROUTER) --data-file=-
	@echo "✓ 更新完了"

secret-update-tavily: ## Tavily APIキーを更新
	@read -p "新しいTAVILY_API_KEYを入力: " key && \
		echo -n "$$key" | gcloud secrets versions add $(SECRET_TAVILY) --data-file=-
	@echo "✓ 更新完了"

secret-list: ## シークレット一覧を表示
	@echo "=== OpenRouter API Key ==="
	gcloud secrets versions list $(SECRET_OPENROUTER) 2>/dev/null || echo "未作成"
	@echo ""
	@echo "=== Tavily API Key ==="
	gcloud secrets versions list $(SECRET_TAVILY) 2>/dev/null || echo "未作成"

# ------------------------------------------------------------------------------
# クリーンアップ
# ------------------------------------------------------------------------------
clean: ## ビルド成果物とキャッシュを削除
	rm -rf frontend/dist
	rm -rf frontend/node_modules/.vite
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .coverage

clean-all: clean ## すべての依存関係も含めて削除
	rm -rf frontend/node_modules
	rm -rf .venv

# ------------------------------------------------------------------------------
# ユーティリティ
# ------------------------------------------------------------------------------
status: ## プロジェクトの状態を表示
	@echo "=== Git Status ==="
	@git status --short
	@echo ""
	@echo "=== デプロイURL ==="
	@gcloud run services describe $(CLOUD_RUN_SERVICE) --region $(GCP_REGION) --format="value(status.url)" 2>/dev/null || echo "未デプロイ"
	@echo ""
	@echo "=== GCSバケット ==="
	@echo "gs://$(GCS_BUCKET)"
