"""Job management for background execution using GCS or local storage."""

import json
import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").lower()
GCS_BUCKET = os.getenv("GCS_BUCKET")
GCS_PREFIX = os.getenv("GCS_PREFIX", "")
DATA_BASE_DIR = os.getenv("DATA_DIR", "data")


class JobManager:
    """ジョブの作成・更新・取得を管理するクラス"""

    def __init__(self):
        self.backend = STORAGE_BACKEND
        if self.backend == "gcs":
            from google.cloud import storage
            if not GCS_BUCKET:
                raise ValueError("GCS_BUCKET is required for GCS storage")
            self.client = storage.Client()
            self.bucket = self.client.bucket(GCS_BUCKET)
            self.prefix = GCS_PREFIX.rstrip('/')
            logger.info(f"JobManager initialized with GCS backend (bucket: {GCS_BUCKET})")
        else:
            self.base_dir = DATA_BASE_DIR
            logger.info(f"JobManager initialized with local backend (dir: {self.base_dir})")

    def _job_path_local(self, project_id: str, job_id: str) -> str:
        """ローカルストレージのジョブファイルパス"""
        return os.path.join(self.base_dir, "projects", project_id, "jobs", f"{job_id}.json")

    def _job_path_gcs(self, project_id: str, job_id: str) -> str:
        """GCSのジョブファイルパス"""
        parts = [p for p in [self.prefix, "projects", project_id, "jobs", f"{job_id}.json"] if p]
        return "/".join(parts)

    def create_job(self, conversation_id: str, project_id: str = "default") -> Dict[str, Any]:
        """
        新しいジョブを作成

        Args:
            conversation_id: 会話ID
            project_id: プロジェクトID

        Returns:
            作成されたジョブデータ
        """
        job_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        job_data = {
            "job_id": job_id,
            "conversation_id": conversation_id,
            "status": "pending",  # pending, running, completed, failed
            "created_at": now,
            "updated_at": now,
            "progress": {
                "current_stage": None,  # stage1, stage2, stage3, complete
                "stage1": {
                    "status": "pending",  # pending, running, completed
                    "data": None,
                    "completed_at": None
                },
                "stage2": {
                    "status": "pending",
                    "data": None,
                    "metadata": None,
                    "completed_at": None
                },
                "stage3": {
                    "status": "pending",
                    "data": None,
                    "completed_at": None
                }
            },
            "usage": None,  # 使用量データ
            "error": None
        }

        # ストレージに保存
        self._save_job(job_id, job_data, project_id)
        logger.info(f"Job created: {job_id[:8]} for conversation {conversation_id[:8]}")

        return job_data

    def get_job(self, job_id: str, project_id: str = "default") -> Optional[Dict[str, Any]]:
        """
        ジョブデータを取得

        Args:
            job_id: ジョブID
            project_id: プロジェクトID

        Returns:
            ジョブデータ（存在しない場合はNone）
        """
        if self.backend == "gcs":
            blob = self.bucket.blob(self._job_path_gcs(project_id, job_id))
            if not blob.exists():
                return None
            try:
                data = blob.download_as_text()
                return json.loads(data)
            except Exception as e:
                logger.error(f"Failed to get job from GCS: {e}")
                return None
        else:
            # ローカルストレージ
            path = self._job_path_local(project_id, job_id)
            if not os.path.exists(path):
                return None
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to get job from local storage: {e}")
                return None

    def update_job(self, job_id: str, updates: Dict[str, Any], project_id: str = "default") -> Optional[Dict[str, Any]]:
        """
        ジョブデータを更新

        Args:
            job_id: ジョブID
            updates: 更新する内容
            project_id: プロジェクトID

        Returns:
            更新後のジョブデータ（ジョブが存在しない場合はNone）
        """
        job_data = self.get_job(job_id, project_id)
        if job_data is None:
            logger.warning(f"Job not found for update: {job_id[:8]}")
            return None

        # updated_atを更新
        updates["updated_at"] = datetime.utcnow().isoformat()
        job_data.update(updates)

        # 保存
        self._save_job(job_id, job_data, project_id)

        return job_data

    def update_job_stage(
        self,
        job_id: str,
        stage: str,  # "stage1", "stage2", "stage3"
        status: str,  # "running", "completed"
        data: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
        project_id: str = "default"
    ) -> Optional[Dict[str, Any]]:
        """
        ジョブの特定ステージを更新

        Args:
            job_id: ジョブID
            stage: ステージ名 ("stage1", "stage2", "stage3")
            status: ステータス ("running", "completed")
            data: ステージのデータ
            metadata: メタデータ（stage2の場合）
            project_id: プロジェクトID

        Returns:
            更新後のジョブデータ
        """
        job_data = self.get_job(job_id, project_id)
        if job_data is None:
            logger.warning(f"Job not found for stage update: {job_id[:8]}")
            return None

        # ステージ情報を更新
        if stage in job_data["progress"]:
            job_data["progress"][stage]["status"] = status
            if data is not None:
                job_data["progress"][stage]["data"] = data
            if metadata is not None and stage == "stage2":
                job_data["progress"][stage]["metadata"] = metadata
            if status == "completed":
                job_data["progress"][stage]["completed_at"] = datetime.utcnow().isoformat()

        # current_stageを更新
        job_data["progress"]["current_stage"] = stage

        # 全体ステータスを更新（stage1開始時はrunningに）
        if stage == "stage1" and status == "running" and job_data["status"] == "pending":
            job_data["status"] = "running"

        job_data["updated_at"] = datetime.utcnow().isoformat()

        # 保存
        self._save_job(job_id, job_data, project_id)
        logger.debug(f"Job {job_id[:8]} stage {stage} updated to {status}")

        return job_data

    def complete_job(self, job_id: str, usage: Optional[Dict[str, Any]] = None, project_id: str = "default") -> Optional[Dict[str, Any]]:
        """
        ジョブを完了状態に更新

        Args:
            job_id: ジョブID
            usage: 使用量データ
            project_id: プロジェクトID

        Returns:
            更新後のジョブデータ
        """
        updates = {
            "status": "completed",
            "progress": {}
        }

        job_data = self.get_job(job_id, project_id)
        if job_data:
            updates["progress"] = job_data["progress"].copy()
            updates["progress"]["current_stage"] = "complete"

        if usage:
            updates["usage"] = usage

        logger.info(f"Job {job_id[:8]} completed")
        return self.update_job(job_id, updates, project_id)

    def fail_job(self, job_id: str, error: str, project_id: str = "default") -> Optional[Dict[str, Any]]:
        """
        ジョブを失敗状態に更新

        Args:
            job_id: ジョブID
            error: エラーメッセージ
            project_id: プロジェクトID

        Returns:
            更新後のジョブデータ
        """
        logger.error(f"Job {job_id[:8]} failed: {error}")
        return self.update_job(job_id, {
            "status": "failed",
            "error": error
        }, project_id)

    def _save_job(self, job_id: str, job_data: Dict[str, Any], project_id: str):
        """ジョブデータを保存（内部関数）"""
        if self.backend == "gcs":
            blob = self.bucket.blob(self._job_path_gcs(project_id, job_id))
            blob.upload_from_string(
                json.dumps(job_data, ensure_ascii=False, indent=2),
                content_type="application/json"
            )
        else:
            # ローカルストレージ
            path = self._job_path_local(project_id, job_id)
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(job_data, f, indent=2, ensure_ascii=False)


# グローバルインスタンス
_job_manager = None


def get_job_manager() -> JobManager:
    """JobManagerのシングルトンインスタンスを取得"""
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager
