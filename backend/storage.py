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

    def _memory_path(self, project_id: str) -> str:
        return os.path.join(self.base_dir, "projects", project_id, "memory.json")

    def _summaries_path(self, project_id: str) -> str:
        return os.path.join(self.base_dir, "projects", project_id, "summaries.json")

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

    def delete_conversation(self, project_id: str, conversation_id: str) -> bool:
        """会話を削除"""
        path = self._conv_path(project_id, conversation_id)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

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

    # ========== メモリ操作 ==========

    def get_memory(self, project_id: str) -> Dict[str, Any]:
        """ユーザーメモリを取得"""
        path = self._memory_path(project_id)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        # デフォルトの空メモリ
        return {
            "version": 1,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "entries": []
        }

    def save_memory(self, project_id: str, memory: Dict[str, Any]):
        """ユーザーメモリを保存"""
        path = self._memory_path(project_id)
        self._ensure_dir(os.path.dirname(path))
        memory["updated_at"] = datetime.utcnow().isoformat()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)

    def add_memory_entry(self, project_id: str, entry: Dict[str, Any]) -> Dict[str, Any]:
        """メモリエントリを追加"""
        memory = self.get_memory(project_id)
        # IDがなければ生成
        if "id" not in entry:
            import uuid
            entry["id"] = f"mem_{uuid.uuid4().hex[:12]}"
        if "extracted_at" not in entry:
            entry["extracted_at"] = datetime.utcnow().isoformat()
        memory["entries"].append(entry)
        self.save_memory(project_id, memory)
        return entry

    def update_memory_entry(self, project_id: str, memory_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """メモリエントリを更新"""
        memory = self.get_memory(project_id)
        for entry in memory["entries"]:
            if entry["id"] == memory_id:
                entry.update(updates)
                self.save_memory(project_id, memory)
                return entry
        return None

    def delete_memory_entry(self, project_id: str, memory_id: str) -> bool:
        """メモリエントリを削除"""
        memory = self.get_memory(project_id)
        original_len = len(memory["entries"])
        memory["entries"] = [e for e in memory["entries"] if e["id"] != memory_id]
        if len(memory["entries"]) < original_len:
            self.save_memory(project_id, memory)
            return True
        return False

    def clear_memory(self, project_id: str):
        """全メモリを削除"""
        memory = self.get_memory(project_id)
        memory["entries"] = []
        self.save_memory(project_id, memory)

    # ========== サマリー操作 ==========

    def get_summaries(self, project_id: str) -> Dict[str, Any]:
        """会話サマリー一覧を取得"""
        path = self._summaries_path(project_id)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        # デフォルトの空サマリー
        return {
            "version": 1,
            "max_entries": 15,
            "entries": []
        }

    def save_summaries(self, project_id: str, summaries: Dict[str, Any]):
        """会話サマリーを保存"""
        path = self._summaries_path(project_id)
        self._ensure_dir(os.path.dirname(path))
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(summaries, f, indent=2, ensure_ascii=False)

    def add_summary(self, project_id: str, summary: Dict[str, Any], max_entries: int = 15):
        """サマリーを追加（max_entries超過時は古いものを削除）"""
        summaries = self.get_summaries(project_id)
        if "summarized_at" not in summary:
            summary["summarized_at"] = datetime.utcnow().isoformat()
        summaries["entries"].insert(0, summary)  # 新しいものを先頭に
        # 古いものを削除
        if len(summaries["entries"]) > max_entries:
            summaries["entries"] = summaries["entries"][:max_entries]
        self.save_summaries(project_id, summaries)

    def delete_summary(self, project_id: str, conversation_id: str) -> bool:
        """特定の会話サマリーを削除"""
        summaries = self.get_summaries(project_id)
        original_len = len(summaries["entries"])
        summaries["entries"] = [s for s in summaries["entries"] if s["conversation_id"] != conversation_id]
        if len(summaries["entries"]) < original_len:
            self.save_summaries(project_id, summaries)
            return True
        return False

    def clear_summaries(self, project_id: str):
        """全サマリーを削除"""
        summaries = self.get_summaries(project_id)
        summaries["entries"] = []
        self.save_summaries(project_id, summaries)


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

    def delete_conversation(self, project_id: str, conversation_id: str) -> bool:
        """会話を削除"""
        blob = self.bucket.blob(self._path(project_id, "conversations", f"{conversation_id}.json"))
        if blob.exists():
            blob.delete()
            return True
        return False

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
        # プロジェクト一覧用の正しいprefixを構築
        # _path()を使うと誤ったパスになるため直接構築
        if self.prefix:
            prefix = f"{self.prefix}/projects/"
        else:
            prefix = "projects/"
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

    # ========== メモリ操作 ==========

    def get_memory(self, project_id: str) -> Dict[str, Any]:
        """ユーザーメモリを取得"""
        blob = self.bucket.blob(self._path(project_id, "", "memory.json"))
        if blob.exists():
            try:
                return json.loads(blob.download_as_text())
            except Exception:
                pass
        return {
            "version": 1,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "entries": []
        }

    def save_memory(self, project_id: str, memory: Dict[str, Any]):
        """ユーザーメモリを保存"""
        memory["updated_at"] = datetime.utcnow().isoformat()
        blob = self.bucket.blob(self._path(project_id, "", "memory.json"))
        blob.upload_from_string(json.dumps(memory, ensure_ascii=False, indent=2), content_type="application/json")

    def add_memory_entry(self, project_id: str, entry: Dict[str, Any]) -> Dict[str, Any]:
        """メモリエントリを追加"""
        memory = self.get_memory(project_id)
        if "id" not in entry:
            import uuid
            entry["id"] = f"mem_{uuid.uuid4().hex[:12]}"
        if "extracted_at" not in entry:
            entry["extracted_at"] = datetime.utcnow().isoformat()
        memory["entries"].append(entry)
        self.save_memory(project_id, memory)
        return entry

    def update_memory_entry(self, project_id: str, memory_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """メモリエントリを更新"""
        memory = self.get_memory(project_id)
        for entry in memory["entries"]:
            if entry["id"] == memory_id:
                entry.update(updates)
                self.save_memory(project_id, memory)
                return entry
        return None

    def delete_memory_entry(self, project_id: str, memory_id: str) -> bool:
        """メモリエントリを削除"""
        memory = self.get_memory(project_id)
        original_len = len(memory["entries"])
        memory["entries"] = [e for e in memory["entries"] if e["id"] != memory_id]
        if len(memory["entries"]) < original_len:
            self.save_memory(project_id, memory)
            return True
        return False

    def clear_memory(self, project_id: str):
        """全メモリを削除"""
        memory = self.get_memory(project_id)
        memory["entries"] = []
        self.save_memory(project_id, memory)

    # ========== サマリー操作 ==========

    def get_summaries(self, project_id: str) -> Dict[str, Any]:
        """会話サマリー一覧を取得"""
        blob = self.bucket.blob(self._path(project_id, "", "summaries.json"))
        if blob.exists():
            try:
                return json.loads(blob.download_as_text())
            except Exception:
                pass
        return {
            "version": 1,
            "max_entries": 15,
            "entries": []
        }

    def save_summaries(self, project_id: str, summaries: Dict[str, Any]):
        """会話サマリーを保存"""
        blob = self.bucket.blob(self._path(project_id, "", "summaries.json"))
        blob.upload_from_string(json.dumps(summaries, ensure_ascii=False, indent=2), content_type="application/json")

    def add_summary(self, project_id: str, summary: Dict[str, Any], max_entries: int = 15):
        """サマリーを追加（max_entries超過時は古いものを削除）"""
        summaries = self.get_summaries(project_id)
        if "summarized_at" not in summary:
            summary["summarized_at"] = datetime.utcnow().isoformat()
        summaries["entries"].insert(0, summary)
        if len(summaries["entries"]) > max_entries:
            summaries["entries"] = summaries["entries"][:max_entries]
        self.save_summaries(project_id, summaries)

    def delete_summary(self, project_id: str, conversation_id: str) -> bool:
        """特定の会話サマリーを削除"""
        summaries = self.get_summaries(project_id)
        original_len = len(summaries["entries"])
        summaries["entries"] = [s for s in summaries["entries"] if s["conversation_id"] != conversation_id]
        if len(summaries["entries"]) < original_len:
            self.save_summaries(project_id, summaries)
            return True
        return False

    def clear_summaries(self, project_id: str):
        """全サマリーを削除"""
        summaries = self.get_summaries(project_id)
        summaries["entries"] = []
        self.save_summaries(project_id, summaries)


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


def delete_conversation(conversation_id: str, project_id: str = "default") -> bool:
    """会話を削除"""
    return _get_backend().delete_conversation(project_id, conversation_id)


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


# ========== メモリ Public API ==========

def get_memory(project_id: str = "default") -> Dict[str, Any]:
    """ユーザーメモリを取得"""
    return _get_backend().get_memory(project_id)


def save_memory(memory: Dict[str, Any], project_id: str = "default"):
    """ユーザーメモリを保存"""
    return _get_backend().save_memory(project_id, memory)


def add_memory_entry(entry: Dict[str, Any], project_id: str = "default") -> Dict[str, Any]:
    """メモリエントリを追加"""
    return _get_backend().add_memory_entry(project_id, entry)


def update_memory_entry(memory_id: str, updates: Dict[str, Any], project_id: str = "default") -> Optional[Dict[str, Any]]:
    """メモリエントリを更新"""
    return _get_backend().update_memory_entry(project_id, memory_id, updates)


def delete_memory_entry(memory_id: str, project_id: str = "default") -> bool:
    """メモリエントリを削除"""
    return _get_backend().delete_memory_entry(project_id, memory_id)


def clear_memory(project_id: str = "default"):
    """全メモリを削除"""
    return _get_backend().clear_memory(project_id)


# ========== サマリー Public API ==========

def get_summaries(project_id: str = "default") -> Dict[str, Any]:
    """会話サマリー一覧を取得"""
    return _get_backend().get_summaries(project_id)


def add_summary(summary: Dict[str, Any], project_id: str = "default", max_entries: int = 15):
    """サマリーを追加"""
    return _get_backend().add_summary(project_id, summary, max_entries)


def delete_summary(conversation_id: str, project_id: str = "default") -> bool:
    """特定の会話サマリーを削除"""
    return _get_backend().delete_summary(project_id, conversation_id)


def clear_summaries(project_id: str = "default"):
    """全サマリーを削除"""
    return _get_backend().clear_summaries(project_id)
