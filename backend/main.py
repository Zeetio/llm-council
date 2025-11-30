"""FastAPI backend for LLM Council."""

import os
import logging
from fastapi import FastAPI, HTTPException, Query

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
from typing import List, Dict, Any
import uuid
import json
import asyncio

from . import storage
from .config import get_config, save_config
from .council import run_full_council, generate_conversation_title, stage1_collect_responses, stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings

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

    # Run the 3-stage council process with conversation history
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        request.content, conversation_history, project_id
    )

    # Add assistant message with all stages
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result,
        project_id
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

            # Add user message
            storage.add_user_message(conversation_id, request.content, project_id)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Stage 1: Collect responses with conversation history
            logger.info(f"[{conversation_id[:8]}] Stage 1: Starting")
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(request.content, conversation_history, project_id)
            logger.info(f"[{conversation_id[:8]}] Stage 1: Complete ({len(stage1_results)} responses)")
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2: Collect rankings
            logger.info(f"[{conversation_id[:8]}] Stage 2: Starting")
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_id = await stage2_collect_rankings(request.content, stage1_results, project_id)
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_id)
            logger.info(f"[{conversation_id[:8]}] Stage 2: Complete ({len(stage2_results)} rankings)")
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_id': label_to_id, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3: Synthesize final answer
            logger.info(f"[{conversation_id[:8]}] Stage 3: Starting")
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(request.content, stage1_results, stage2_results, project_id)
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

            # Send completion event
            logger.info(f"[{conversation_id[:8]}] Council process complete")
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

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


@app.get("/api/config")
async def get_council_config(project_id: str = Query("default", alias="project_id")):
    """Get current council configuration."""
    return get_config(project_id)


@app.put("/api/config")
async def update_council_config(config: Dict[str, Any], project_id: str = Query("default", alias="project_id")):
    """Update council configuration."""
    save_config(config, project_id)
    return {"status": "ok", "config": config}


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


# Mount frontend static files (must be after all API routes)
# Only mount if frontend_dist directory exists (Cloud Run deployment)
if os.path.isdir("frontend_dist"):
    app.mount("/", StaticFiles(directory="frontend_dist", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
