"""Storage abstraction for conversations and configs (local JSON or GCS)."""

import json
import os
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").lower()
GCS_BUCKET = os.getenv("GCS_BUCKET")
GCS_PREFIX = os.getenv("GCS_PREFIX", "")

DATA_BASE_DIR = os.getenv("DATA_DIR", "data")


def _project_prefix(project_id: str) -> str:
    return os.path.join(DATA_BASE_DIR, "projects", project_id)


# -------- Local backend --------
class LocalStorage:
    def __init__(self):
        self.base_dir = DATA_BASE_DIR
        self.base_project_dir = os.path.join(self.base_dir, "projects")

    def _ensure_dir(self, path: str):
        Path(path).mkdir(parents=True, exist_ok=True)

    def _conv_dir(self, project_id: str) -> str:
        return os.path.join(self.base_dir, "projects", project_id, "conversations")

    def _conv_path(self, project_id: str, conversation_id: str) -> str:
        return os.path.join(self._conv_dir(project_id), f"{conversation_id}.json")

    def _config_path(self, project_id: str) -> str:
        return os.path.join(self.base_dir, "projects", project_id, "config.json")

    def list_projects(self) -> List[str]:
        Path(self.base_project_dir).mkdir(parents=True, exist_ok=True)
        projects = [d for d in os.listdir(self.base_project_dir) if os.path.isdir(os.path.join(self.base_project_dir, d))]
        if not projects:
            projects.append("default")
        return sorted(set(projects))

    def delete_project(self, project_id: str):
        path = os.path.join(self.base_project_dir, project_id)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)

    def create_project(self, project_id: str) -> Dict[str, str]:
        path = os.path.join(self.base_project_dir, project_id)
        self._ensure_dir(path)
        self._ensure_dir(os.path.join(path, "conversations"))
        return {"id": project_id, "status": "created"}

    # Conversations
    def create_conversation(self, project_id: str, conversation_id: str) -> Dict[str, Any]:
        self._ensure_dir(self._conv_dir(project_id))
        conversation = {
            "id": conversation_id,
            "created_at": datetime.utcnow().isoformat(),
            "title": "New Conversation",
            "messages": []
        }
        with open(self._conv_path(project_id, conversation_id), 'w') as f:
            json.dump(conversation, f, indent=2)
        return conversation

    def get_conversation(self, project_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        path = self._conv_path(project_id, conversation_id)
        if not os.path.exists(path):
            return None
        with open(path, 'r') as f:
            return json.load(f)

    def save_conversation(self, project_id: str, conversation: Dict[str, Any]):
        self._ensure_dir(self._conv_dir(project_id))
        with open(self._conv_path(project_id, conversation['id']), 'w') as f:
            json.dump(conversation, f, indent=2)

    def list_conversations(self, project_id: str) -> List[Dict[str, Any]]:
        dir_path = self._conv_dir(project_id)
        self._ensure_dir(dir_path)
        conversations = []
        for filename in os.listdir(dir_path):
            if filename.endswith('.json'):
                path = os.path.join(dir_path, filename)
                with open(path, 'r') as f:
                    data = json.load(f)
                    conversations.append({
                        "id": data["id"],
                        "created_at": data["created_at"],
                        "title": data.get("title", "New Conversation"),
                        "message_count": len(data["messages"])
                    })
        conversations.sort(key=lambda x: x["created_at"], reverse=True)
        return conversations

    # Config
    def get_config(self, project_id: str, default_config: Dict[str, Any]) -> Dict[str, Any]:
        path = self._config_path(project_id)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        self._ensure_dir(os.path.dirname(path))
        return default_config.copy()

    def save_config(self, project_id: str, config: Dict[str, Any]):
        path = self._config_path(project_id)
        self._ensure_dir(os.path.dirname(path))
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)


# -------- GCS backend --------
class GCSStorage:
    def __init__(self):
        from google.cloud import storage  # lazy import
        if not GCS_BUCKET:
            raise ValueError("GCS_BUCKET is required for GCS storage")
        self.client = storage.Client()
        self.bucket = self.client.bucket(GCS_BUCKET)
        self.prefix = GCS_PREFIX.rstrip('/')

    def _path(self, project_id: str, kind: str, filename: str) -> str:
        parts = [p for p in [self.prefix, "projects", project_id, kind, filename] if p]
        return "/".join(parts)

    def create_conversation(self, project_id: str, conversation_id: str) -> Dict[str, Any]:
        conversation = {
            "id": conversation_id,
            "created_at": datetime.utcnow().isoformat(),
            "title": "New Conversation",
            "messages": []
        }
        self.save_conversation(project_id, conversation)
        return conversation

    def get_conversation(self, project_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        blob = self.bucket.blob(self._path(project_id, "conversations", f"{conversation_id}.json"))
        if not blob.exists():
            return None
        try:
            data = blob.download_as_text()
            return json.loads(data)
        except Exception:
            return None

    def save_conversation(self, project_id: str, conversation: Dict[str, Any]):
        blob = self.bucket.blob(self._path(project_id, "conversations", f"{conversation['id']}.json"))
        blob.upload_from_string(json.dumps(conversation, ensure_ascii=False, indent=2), content_type="application/json")

    def list_conversations(self, project_id: str) -> List[Dict[str, Any]]:
        prefix = self._path(project_id, "conversations", "")
        blobs = self.client.list_blobs(self.bucket, prefix=prefix)
        conversations = []
        for blob in blobs:
            if not blob.name.endswith('.json'):
                continue
            try:
                data = json.loads(blob.download_as_text())
                conversations.append({
                    "id": data["id"],
                    "created_at": data["created_at"],
                    "title": data.get("title", "New Conversation"),
                    "message_count": len(data.get("messages", []))
                })
            except Exception:
                continue
        conversations.sort(key=lambda x: x["created_at"], reverse=True)
        return conversations

    def get_config(self, project_id: str, default_config: Dict[str, Any]) -> Dict[str, Any]:
        blob = self.bucket.blob(self._path(project_id, "", "config.json"))
        if blob.exists():
            try:
                return json.loads(blob.download_as_text())
            except Exception:
                pass
        return default_config.copy()

    def save_config(self, project_id: str, config: Dict[str, Any]):
        blob = self.bucket.blob(self._path(project_id, "", "config.json"))
        blob.upload_from_string(json.dumps(config, ensure_ascii=False, indent=2), content_type="application/json")

    def list_projects(self) -> List[str]:
        prefix = self._path("", "projects", "")
        blobs = self.client.list_blobs(self.bucket, prefix=prefix)
        projects = set()
        for blob in blobs:
            # blob.name like 'projects/<pid>/conversations/xxx.json'
            parts = blob.name.split("/")
            if "projects" in parts:
                idx = parts.index("projects")
                if len(parts) > idx + 1:
                    projects.add(parts[idx + 1])
        if not projects:
            projects.add("default")
        return sorted(projects)

    def delete_project(self, project_id: str):
        prefix = self._path(project_id, "", "")
        blobs = list(self.client.list_blobs(self.bucket, prefix=prefix))
        if blobs:
            self.bucket.delete_blobs(blobs)

    def create_project(self, project_id: str) -> Dict[str, str]:
        # Create placeholder to ensure project appears in listings
        placeholder = self.bucket.blob(self._path(project_id, "conversations", ".keep"))
        placeholder.upload_from_string("", content_type="text/plain")
        return {"id": project_id, "status": "created"}


_backend = None


def _get_backend():
    global _backend
    if _backend:
        return _backend
    if STORAGE_BACKEND == "gcs":
        _backend = GCSStorage()
    else:
        _backend = LocalStorage()
    return _backend


# Public API wrappers -------------------------------------------------
def create_conversation(conversation_id: str, project_id: str = "default") -> Dict[str, Any]:
    return _get_backend().create_conversation(project_id, conversation_id)


def get_conversation(conversation_id: str, project_id: str = "default") -> Optional[Dict[str, Any]]:
    return _get_backend().get_conversation(project_id, conversation_id)


def save_conversation(conversation: Dict[str, Any], project_id: str = "default"):
    return _get_backend().save_conversation(project_id, conversation)


def list_conversations(project_id: str = "default") -> List[Dict[str, Any]]:
    return _get_backend().list_conversations(project_id)


def add_user_message(conversation_id: str, content: str, project_id: str = "default"):
    conversation = get_conversation(conversation_id, project_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({
        "role": "user",
        "content": content
    })

    save_conversation(conversation, project_id)


def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any],
    project_id: str = "default"
):
    conversation = get_conversation(conversation_id, project_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({
        "role": "assistant",
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3
    })

    save_conversation(conversation, project_id)


def update_conversation_title(conversation_id: str, title: str, project_id: str = "default"):
    conversation = get_conversation(conversation_id, project_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["title"] = title
    save_conversation(conversation, project_id)


def get_config(project_id: str, default_config: Dict[str, Any]) -> Dict[str, Any]:
    return _get_backend().get_config(project_id, default_config)


def save_config(config: Dict[str, Any], project_id: str):
    return _get_backend().save_config(project_id, config)


def list_projects() -> List[str]:
    return _get_backend().list_projects()


def delete_project(project_id: str):
    return _get_backend().delete_project(project_id)


def create_project(project_id: str) -> Dict[str, str]:
    return _get_backend().create_project(project_id)
