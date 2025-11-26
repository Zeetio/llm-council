# ----------------
# frontend build
# ----------------
FROM node:20-slim AS fe
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm ci
COPY frontend .
RUN npm run build  # => /fe/dist

# ----------------
# backend build
# ----------------
FROM python:3.11-slim AS be
WORKDIR /app

# uv を入れる（READMEで uv 利用とある） :contentReference[oaicite:1]{index=1}
RUN pip install --no-cache-dir uv

# Python deps
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# App code
COPY backend ./backend

# Create data directories (will be ephemeral in Cloud Run)
RUN mkdir -p data/conversations

# frontend dist を backend 側へコピー
# (FastAPIで静的配信するディレクトリに合わせてる。必要なら後述の説明通り修正)
COPY --from=fe /fe/dist ./frontend_dist

ENV PORT=8080
EXPOSE 8080

# 起動コマンド：
# backend側のapp位置は repoの実体に合わせて調整が必要。
# まずは READMEの "uv run python -m backend.main" を uvicorn で置き換えた形。 :contentReference[oaicite:2]{index=2}
CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
