"""FastAPI backend for LLM Council."""

import os
import logging
from fastapi import FastAPI, HTTPException, Query, Header, Depends

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import bcrypt
import uuid
import json
import asyncio

from . import storage
from .config import get_config, save_config
from .council import run_full_council, generate_conversation_title, stage1_collect_responses, stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings
from .memory_extractor import extract_memory_from_conversation, generate_conversation_summary
from .llm_logger import LLMLogger
from .tools import ToolLogger
from .job_manager import get_job_manager

app = FastAPI(title="LLM Council API")

# CORS configuration from environment variable (comma-separated origins, or "*" for all)
allowed_origins = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass


class CreateProjectRequest(BaseModel):
    """Request to create a new project."""
    project_id: str


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str
    user_comments: List[Dict[str, Any]] = []  # ユーザーコメント（フィードバック）
    session_metadata: Optional[Dict[str, Any]] = None  # セッションメタデータ（デバイス、OS等）


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


class PasswordVerifyRequest(BaseModel):
    """パスワード検証リクエスト"""
    password: str


class PasswordSetRequest(BaseModel):
    """パスワード設定リクエスト"""
    password: str
    current_password: Optional[str] = None


class MemoryCreateRequest(BaseModel):
    """メモリ作成リクエスト"""
    category: str
    key: str
    value: str


class MemoryUpdateRequest(BaseModel):
    """メモリ更新リクエスト"""
    key: Optional[str] = None
    value: Optional[str] = None
    category: Optional[str] = None


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "LLM Council API"}


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations(project_id: str = Query("default", alias="project_id")):
    """List all conversations (metadata only)."""
    return storage.list_conversations(project_id)


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest, project_id: str = Query("default", alias="project_id")):
    """Create a new conversation."""
    # 新規会話作成前に、前回会話のサマリーを生成（非同期）
    existing_conversations = storage.list_conversations(project_id)
    if existing_conversations:
        # 最新の会話（メッセージがあるもの）をサマリー化
        for conv in existing_conversations:
            if conv.get("message_count", 0) > 0:
                # 既にサマリーが存在するかチェック
                summaries = storage.get_summaries(project_id)
                existing_ids = [s["conversation_id"] for s in summaries.get("entries", [])]
                if conv["id"] not in existing_ids:
                    logger.info(f"Generating summary for previous conversation: {conv['id'][:8]}")
                    asyncio.create_task(
                        generate_conversation_summary(conv["id"], project_id)
                    )
                break  # 最新の1件のみ

    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id, project_id)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str, project_id: str = Query("default", alias="project_id")):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id, project_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, project_id: str = Query("default", alias="project_id")):
    """会話を削除"""
    if not storage.delete_conversation(conversation_id, project_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted", "conversation_id": conversation_id}


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest, project_id: str = Query("default", alias="project_id")):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id, project_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get conversation history before adding new message
    conversation_history = conversation.get("messages", [])

    # Check if this is the first message
    is_first_message = len(conversation_history) == 0

    # Add user message
    storage.add_user_message(conversation_id, request.content, project_id)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title, project_id)

    # Run the 3-stage council process with conversation history, user comments, and session metadata
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        request.content, conversation_history, request.user_comments, project_id, request.session_metadata
    )

    # Add assistant message with all stages
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result,
        project_id
    )

    # メモリ抽出を非同期で実行（レスポンスをブロックしない）
    asyncio.create_task(
        extract_memory_from_conversation(
            request.content,
            stage3_result.get("response", ""),
            conversation_id,
            project_id
        )
    )
    # 会話サマリー更新を非同期で実行
    asyncio.create_task(
        generate_conversation_summary(conversation_id, project_id)
    )

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest, project_id: str = Query("default", alias="project_id")):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events as each stage completes.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id, project_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get conversation history before adding new message
    conversation_history = conversation.get("messages", [])

    # Check if this is the first message
    is_first_message = len(conversation_history) == 0

    async def event_generator():
        try:
            logger.info(f"[{conversation_id[:8]}] Starting council process")

            # LLMロガーとツールロガーを初期化
            llm_logger = LLMLogger()
            tool_logger = ToolLogger()

            # Add user message
            storage.add_user_message(conversation_id, request.content, project_id)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Stage 1: Collect responses with conversation history, user comments, and session metadata
            logger.info(f"[{conversation_id[:8]}] Stage 1: Starting")
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(
                request.content,
                conversation_history,
                request.user_comments,
                project_id,
                request.session_metadata,
                llm_logger=llm_logger,
                tool_logger=tool_logger
            )
            logger.info(f"[{conversation_id[:8]}] Stage 1: Complete ({len(stage1_results)} responses)")
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2: Collect rankings
            logger.info(f"[{conversation_id[:8]}] Stage 2: Starting")
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_id = await stage2_collect_rankings(
                request.content,
                stage1_results,
                project_id,
                llm_logger=llm_logger
            )
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_id)
            logger.info(f"[{conversation_id[:8]}] Stage 2: Complete ({len(stage2_results)} rankings)")
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_id': label_to_id, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3: Synthesize final answer
            logger.info(f"[{conversation_id[:8]}] Stage 3: Starting")
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(
                request.content,
                stage1_results,
                stage2_results,
                project_id,
                llm_logger=llm_logger
            )
            logger.info(f"[{conversation_id[:8]}] Stage 3: Complete")
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title, project_id)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Save complete assistant message
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result,
                project_id
            )

            # メモリ抽出を非同期で実行（ストリームをブロックしない）
            asyncio.create_task(
                extract_memory_from_conversation(
                    request.content,
                    stage3_result.get("response", ""),
                    conversation_id,
                    project_id
                )
            )
            # 会話サマリー更新を非同期で実行
            asyncio.create_task(
                generate_conversation_summary(conversation_id, project_id)
            )

            # ツールログをLLMロガーに統合
            llm_logger.add_tool_logs(tool_logger.get_logs())

            # 使用量サマリーを取得
            usage_summary = llm_logger.get_summary()
            logger.info(
                f"[{conversation_id[:8]}] Usage: {usage_summary.get('total_tokens', 0)} tokens, "
                f"${usage_summary.get('total_cost_usd', 0):.6f}"
            )

            # Send completion event（使用量情報付き）
            logger.info(f"[{conversation_id[:8]}] Council process complete")
            yield f"data: {json.dumps({'type': 'complete', 'usage': usage_summary})}\n\n"

        except Exception as e:
            logger.error(f"[{conversation_id[:8]}] Error: {e}")
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


async def execute_council_job(
    job_id: str,
    conversation_id: str,
    content: str,
    user_comments: List[Dict[str, Any]],
    project_id: str,
    session_metadata: Optional[Dict[str, Any]]
):
    """
    バックグラウンドで3ステージ評議会を実行し、ジョブ状態を逐次更新

    Args:
        job_id: ジョブID
        conversation_id: 会話ID
        content: ユーザーメッセージ
        user_comments: ユーザーコメント
        project_id: プロジェクトID
        session_metadata: セッションメタデータ
    """
    job_mgr = get_job_manager()

    try:
        logger.info(f"[Job {job_id[:8]}] Starting background execution for conversation {conversation_id[:8]}")

        # LLMロガーとツールロガーを初期化
        llm_logger = LLMLogger()
        tool_logger = ToolLogger()

        # 会話履歴取得
        conversation = storage.get_conversation(conversation_id, project_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        conversation_history = conversation.get("messages", [])
        is_first_message = len(conversation_history) == 0

        # ユーザーメッセージ追加
        storage.add_user_message(conversation_id, content, project_id)

        # タイトル生成（並列実行）
        title_task = None
        if is_first_message:
            title_task = asyncio.create_task(generate_conversation_title(content))

        # Stage 1: 個別モデルの回答収集
        logger.info(f"[Job {job_id[:8]}] Stage 1: Starting")
        job_mgr.update_job_stage(job_id, "stage1", "running", project_id=project_id)

        stage1_results = await stage1_collect_responses(
            content,
            conversation_history,
            user_comments,
            project_id,
            session_metadata,
            llm_logger=llm_logger,
            tool_logger=tool_logger
        )

        job_mgr.update_job_stage(job_id, "stage1", "completed", data=stage1_results, project_id=project_id)
        logger.info(f"[Job {job_id[:8]}] Stage 1: Complete ({len(stage1_results)} responses)")

        # Stage 2: ランキング収集
        logger.info(f"[Job {job_id[:8]}] Stage 2: Starting")
        job_mgr.update_job_stage(job_id, "stage2", "running", project_id=project_id)

        stage2_results, label_to_id = await stage2_collect_rankings(
            content,
            stage1_results,
            project_id,
            llm_logger=llm_logger
        )
        aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_id)

        metadata = {
            "label_to_id": label_to_id,
            "aggregate_rankings": aggregate_rankings
        }
        job_mgr.update_job_stage(job_id, "stage2", "completed", data=stage2_results, metadata=metadata, project_id=project_id)
        logger.info(f"[Job {job_id[:8]}] Stage 2: Complete ({len(stage2_results)} rankings)")

        # Stage 3: 最終合成
        logger.info(f"[Job {job_id[:8]}] Stage 3: Starting")
        job_mgr.update_job_stage(job_id, "stage3", "running", project_id=project_id)

        stage3_result = await stage3_synthesize_final(
            content,
            stage1_results,
            stage2_results,
            project_id,
            llm_logger=llm_logger
        )

        job_mgr.update_job_stage(job_id, "stage3", "completed", data=stage3_result, project_id=project_id)
        logger.info(f"[Job {job_id[:8]}] Stage 3: Complete")

        # タイトル生成待機
        if title_task:
            title = await title_task
            storage.update_conversation_title(conversation_id, title, project_id)

        # アシスタントメッセージ保存
        storage.add_assistant_message(
            conversation_id,
            stage1_results,
            stage2_results,
            stage3_result,
            project_id
        )

        # メモリ抽出を非同期で実行
        asyncio.create_task(
            extract_memory_from_conversation(
                content,
                stage3_result.get("response", ""),
                conversation_id,
                project_id
            )
        )
        # 会話サマリー更新を非同期で実行
        asyncio.create_task(
            generate_conversation_summary(conversation_id, project_id)
        )

        # ツールログをLLMロガーに統合
        llm_logger.add_tool_logs(tool_logger.get_logs())

        # 使用量サマリーを取得
        usage_summary = llm_logger.get_summary()
        logger.info(
            f"[Job {job_id[:8]}] Usage: {usage_summary.get('total_tokens', 0)} tokens, "
            f"${usage_summary.get('total_cost_usd', 0):.6f}"
        )

        # ジョブ完了
        job_mgr.complete_job(job_id, usage=usage_summary, project_id=project_id)
        logger.info(f"[Job {job_id[:8]}] Background execution complete")

    except Exception as e:
        logger.error(f"[Job {job_id[:8]}] Error: {e}")
        job_mgr.fail_job(job_id, str(e), project_id=project_id)


@app.post("/api/conversations/{conversation_id}/message/job")
async def send_message_job(conversation_id: str, request: SendMessageRequest, project_id: str = Query("default", alias="project_id")):
    """
    メッセージを送信してバックグラウンドで評議会を実行。
    ジョブIDを即座に返し、クライアントはポーリングで進捗を取得する。
    """
    # 会話の存在確認
    conversation = storage.get_conversation(conversation_id, project_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # ジョブを作成
    job_mgr = get_job_manager()
    job_data = job_mgr.create_job(conversation_id, project_id)
    job_id = job_data["job_id"]

    # バックグラウンドタスクを開始
    asyncio.create_task(
        execute_council_job(
            job_id,
            conversation_id,
            request.content,
            request.user_comments,
            project_id,
            request.session_metadata
        )
    )

    # ジョブIDを即座に返す
    return {
        "job_id": job_id,
        "status": "accepted",
        "message": "Job started in background"
    }


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str, project_id: str = Query("default", alias="project_id")):
    """
    ジョブの状態を取得

    Returns:
        ジョブデータ（status, progress, usage等）
    """
    job_mgr = get_job_manager()
    job_data = job_mgr.get_job(job_id, project_id)

    if job_data is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return job_data


@app.get("/api/config")
async def get_council_config(project_id: str = Query("default", alias="project_id")):
    """Get current council configuration."""
    config = get_config(project_id)
    # password_hashは除外して返す（セキュリティ対策）
    return {k: v for k, v in config.items() if k != "password_hash"}


@app.put("/api/config")
async def update_council_config(
    config: Dict[str, Any],
    project_id: str = Query("default", alias="project_id"),
    password: str = Header(None, alias="X-Project-Password")
):
    """Update council configuration."""
    current = get_config(project_id)

    # パスワード保護されている場合は認証必須
    stored_hash = current.get("password_hash")
    if stored_hash:
        if not password or not bcrypt.checkpw(password.encode(), stored_hash.encode()):
            raise HTTPException(status_code=401, detail="Invalid password")

    # password_hashは上書き禁止（専用APIを使用）
    if "password_hash" in config:
        del config["password_hash"]

    # 既存のpassword_hashを保持
    if stored_hash:
        config["password_hash"] = stored_hash

    save_config(config, project_id)
    # レスポンスからもpassword_hashを除外
    return {"status": "ok", "config": {k: v for k, v in config.items() if k != "password_hash"}}


@app.get("/api/projects")
async def list_projects_api():
    """List available projects."""
    return storage.list_projects()


@app.post("/api/projects")
async def create_project_api(request: CreateProjectRequest):
    """Create a new project."""
    pid = (request.project_id or "").strip()
    if not pid:
        raise HTTPException(status_code=400, detail="project_id required")
    storage.create_project(pid)
    return {"status": "ok", "project_id": pid}


@app.delete("/api/projects/{project_id}")
async def delete_project_api(project_id: str):
    """Delete a project and all its data."""
    if project_id == "default":
        raise HTTPException(status_code=400, detail="Cannot delete default project")
    storage.delete_project(project_id)
    return {"status": "deleted", "project_id": project_id}


# =============================================================================
# プロジェクト認証API
# =============================================================================

@app.get("/api/projects/{project_id}/auth/status")
async def get_auth_status(project_id: str):
    """プロジェクトのパスワード設定状態を取得"""
    config = get_config(project_id)
    has_password = bool(config.get("password_hash"))
    return {"has_password": has_password, "project_id": project_id}


@app.post("/api/projects/{project_id}/auth/verify")
async def verify_password(project_id: str, request: PasswordVerifyRequest):
    """パスワードを検証"""
    config = get_config(project_id)
    stored_hash = config.get("password_hash")

    if not stored_hash:
        # パスワードなしのプロジェクト
        return {"valid": True, "message": "No password required"}

    # bcryptで検証
    if bcrypt.checkpw(request.password.encode('utf-8'), stored_hash.encode('utf-8')):
        return {"valid": True}
    else:
        raise HTTPException(status_code=401, detail="Invalid password")


@app.post("/api/projects/{project_id}/auth/set")
async def set_password(project_id: str, request: PasswordSetRequest):
    """パスワードを設定/変更"""
    config = get_config(project_id)
    existing_hash = config.get("password_hash")

    # 既存パスワードがある場合は検証が必要
    if existing_hash:
        if not request.current_password:
            raise HTTPException(status_code=400, detail="Current password required")
        if not bcrypt.checkpw(request.current_password.encode('utf-8'), existing_hash.encode('utf-8')):
            raise HTTPException(status_code=401, detail="Current password is incorrect")

    # 新しいパスワードをハッシュ化
    salt = bcrypt.gensalt()
    new_hash = bcrypt.hashpw(request.password.encode('utf-8'), salt)

    config["password_hash"] = new_hash.decode('utf-8')
    save_config(config, project_id)

    return {"status": "ok", "message": "Password set successfully"}


@app.delete("/api/projects/{project_id}/auth")
async def remove_password(project_id: str, request: PasswordVerifyRequest):
    """パスワードを削除（現在のパスワードで認証必要）"""
    config = get_config(project_id)
    existing_hash = config.get("password_hash")

    if not existing_hash:
        return {"status": "ok", "message": "No password to remove"}

    # 現在のパスワードを検証
    if not bcrypt.checkpw(request.password.encode('utf-8'), existing_hash.encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid password")

    config["password_hash"] = None
    save_config(config, project_id)

    return {"status": "ok", "message": "Password removed"}


# =============================================================================
# パスワード認証ヘルパー
# =============================================================================

async def verify_project_access(
    project_id: str = Query("default", alias="project_id"),
    x_project_password: Optional[str] = Header(None, alias="X-Project-Password")
):
    """
    プロジェクトのパスワード検証（Dependency Injection用）
    パスワード設定済みプロジェクトは X-Project-Password ヘッダーで認証
    """
    config = get_config(project_id)
    stored_hash = config.get("password_hash")

    if stored_hash:
        if not x_project_password:
            raise HTTPException(status_code=401, detail="Password required")
        if not bcrypt.checkpw(x_project_password.encode('utf-8'), stored_hash.encode('utf-8')):
            raise HTTPException(status_code=401, detail="Invalid password")

    return project_id


# =============================================================================
# メモリAPI（パスワード保護対応）
# =============================================================================

@app.get("/api/memory")
async def get_memory_api(project_id: str = Depends(verify_project_access)):
    """ユーザーメモリを取得"""
    return storage.get_memory(project_id)


@app.post("/api/memory")
async def add_memory_api(
    request: MemoryCreateRequest,
    project_id: str = Depends(verify_project_access)
):
    """メモリエントリを手動追加"""
    entry = {
        "category": request.category,
        "key": request.key,
        "value": request.value,
        "confidence": 1.0,  # 手動追加は確信度100%
        "source_conversation_id": None
    }
    return storage.add_memory_entry(entry, project_id)


@app.put("/api/memory/{memory_id}")
async def update_memory_api(
    memory_id: str,
    request: MemoryUpdateRequest,
    project_id: str = Depends(verify_project_access)
):
    """メモリエントリを更新"""
    updates = {}
    if request.key is not None:
        updates["key"] = request.key
    if request.value is not None:
        updates["value"] = request.value
    if request.category is not None:
        updates["category"] = request.category

    result = storage.update_memory_entry(memory_id, updates, project_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    return result


@app.delete("/api/memory/{memory_id}")
async def delete_memory_api(
    memory_id: str,
    project_id: str = Depends(verify_project_access)
):
    """メモリエントリを削除"""
    if not storage.delete_memory_entry(memory_id, project_id):
        raise HTTPException(status_code=404, detail="Memory entry not found")
    return {"status": "deleted", "memory_id": memory_id}


@app.delete("/api/memory")
async def clear_memory_api(project_id: str = Depends(verify_project_access)):
    """全メモリを削除"""
    storage.clear_memory(project_id)
    return {"status": "cleared", "project_id": project_id}


# =============================================================================
# サマリーAPI（パスワード保護対応）
# =============================================================================

@app.get("/api/summaries")
async def get_summaries_api(project_id: str = Depends(verify_project_access)):
    """会話サマリー一覧を取得"""
    return storage.get_summaries(project_id)


@app.delete("/api/summaries/{conversation_id}")
async def delete_summary_api(
    conversation_id: str,
    project_id: str = Depends(verify_project_access)
):
    """特定の会話サマリーを削除"""
    if not storage.delete_summary(conversation_id, project_id):
        raise HTTPException(status_code=404, detail="Summary not found")
    return {"status": "deleted", "conversation_id": conversation_id}


@app.delete("/api/summaries")
async def clear_summaries_api(project_id: str = Depends(verify_project_access)):
    """全サマリーを削除"""
    storage.clear_summaries(project_id)
    return {"status": "cleared", "project_id": project_id}


# Mount frontend static files (must be after all API routes)
# Only mount if frontend_dist directory exists (Cloud Run deployment)
if os.path.isdir("frontend_dist"):
    app.mount("/", StaticFiles(directory="frontend_dist", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
