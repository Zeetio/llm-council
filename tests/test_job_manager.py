"""Unit tests for job_manager module."""

import pytest
import os
import json
import tempfile
import shutil
from backend.job_manager import JobManager


@pytest.fixture
def temp_data_dir():
    """一時的なデータディレクトリを作成"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def job_manager(temp_data_dir, monkeypatch):
    """JobManagerのインスタンスを作成（ローカルストレージモード）"""
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("DATA_DIR", temp_data_dir)
    manager = JobManager()
    return manager


def test_create_job(job_manager):
    """ジョブ作成のテスト"""
    conversation_id = "test-conversation-1"
    project_id = "test-project"

    # ジョブを作成
    job_data = job_manager.create_job(conversation_id, project_id)

    # 検証
    assert job_data["job_id"] is not None
    assert job_data["conversation_id"] == conversation_id
    assert job_data["status"] == "pending"
    assert job_data["created_at"] is not None
    assert job_data["updated_at"] is not None
    assert job_data["progress"]["current_stage"] is None
    assert job_data["progress"]["stage1"]["status"] == "pending"
    assert job_data["progress"]["stage2"]["status"] == "pending"
    assert job_data["progress"]["stage3"]["status"] == "pending"
    assert job_data["usage"] is None
    assert job_data["error"] is None


def test_get_job(job_manager):
    """ジョブ取得のテスト"""
    conversation_id = "test-conversation-1"
    project_id = "test-project"

    # ジョブを作成
    created_job = job_manager.create_job(conversation_id, project_id)
    job_id = created_job["job_id"]

    # ジョブを取得
    retrieved_job = job_manager.get_job(job_id, project_id)

    # 検証
    assert retrieved_job is not None
    assert retrieved_job["job_id"] == job_id
    assert retrieved_job["conversation_id"] == conversation_id


def test_get_nonexistent_job(job_manager):
    """存在しないジョブの取得テスト"""
    job = job_manager.get_job("nonexistent-job-id", "test-project")
    assert job is None


def test_update_job(job_manager):
    """ジョブ更新のテスト"""
    conversation_id = "test-conversation-1"
    project_id = "test-project"

    # ジョブを作成
    job_data = job_manager.create_job(conversation_id, project_id)
    job_id = job_data["job_id"]

    # ジョブを更新
    updates = {"status": "running"}
    updated_job = job_manager.update_job(job_id, updates, project_id)

    # 検証
    assert updated_job is not None
    assert updated_job["status"] == "running"
    assert updated_job["updated_at"] != job_data["updated_at"]  # 更新日時が変更されている


def test_update_job_stage(job_manager):
    """ステージ更新のテスト"""
    conversation_id = "test-conversation-1"
    project_id = "test-project"

    # ジョブを作成
    job_data = job_manager.create_job(conversation_id, project_id)
    job_id = job_data["job_id"]

    # Stage 1を開始
    updated_job = job_manager.update_job_stage(job_id, "stage1", "running", project_id=project_id)

    assert updated_job["progress"]["stage1"]["status"] == "running"
    assert updated_job["progress"]["current_stage"] == "stage1"
    assert updated_job["status"] == "running"  # pending -> running に変更される

    # Stage 1を完了
    stage1_data = [{"id": "model1", "response": "test response"}]
    updated_job = job_manager.update_job_stage(
        job_id, "stage1", "completed", data=stage1_data, project_id=project_id
    )

    assert updated_job["progress"]["stage1"]["status"] == "completed"
    assert updated_job["progress"]["stage1"]["data"] == stage1_data
    assert updated_job["progress"]["stage1"]["completed_at"] is not None

    # Stage 2を開始
    updated_job = job_manager.update_job_stage(job_id, "stage2", "running", project_id=project_id)

    assert updated_job["progress"]["stage2"]["status"] == "running"
    assert updated_job["progress"]["current_stage"] == "stage2"

    # Stage 2を完了（メタデータ付き）
    stage2_data = [{"id": "model1", "ranking": "1. Response A"}]
    metadata = {"label_to_id": {"Response A": "model1"}}
    updated_job = job_manager.update_job_stage(
        job_id, "stage2", "completed", data=stage2_data, metadata=metadata, project_id=project_id
    )

    assert updated_job["progress"]["stage2"]["status"] == "completed"
    assert updated_job["progress"]["stage2"]["data"] == stage2_data
    assert updated_job["progress"]["stage2"]["metadata"] == metadata
    assert updated_job["progress"]["stage2"]["completed_at"] is not None


def test_complete_job(job_manager):
    """ジョブ完了のテスト"""
    conversation_id = "test-conversation-1"
    project_id = "test-project"

    # ジョブを作成
    job_data = job_manager.create_job(conversation_id, project_id)
    job_id = job_data["job_id"]

    # ジョブを完了
    usage = {"total_tokens": 1000, "total_cost_usd": 0.01}
    completed_job = job_manager.complete_job(job_id, usage, project_id)

    # 検証
    assert completed_job is not None
    assert completed_job["status"] == "completed"
    assert completed_job["usage"] == usage
    assert completed_job["progress"]["current_stage"] == "complete"


def test_fail_job(job_manager):
    """ジョブ失敗のテスト"""
    conversation_id = "test-conversation-1"
    project_id = "test-project"

    # ジョブを作成
    job_data = job_manager.create_job(conversation_id, project_id)
    job_id = job_data["job_id"]

    # ジョブを失敗状態にする
    error_message = "Test error occurred"
    failed_job = job_manager.fail_job(job_id, error_message, project_id)

    # 検証
    assert failed_job is not None
    assert failed_job["status"] == "failed"
    assert failed_job["error"] == error_message


def test_full_job_lifecycle(job_manager):
    """ジョブのライフサイクル全体のテスト"""
    conversation_id = "test-conversation-1"
    project_id = "test-project"

    # 1. ジョブ作成
    job_data = job_manager.create_job(conversation_id, project_id)
    job_id = job_data["job_id"]
    assert job_data["status"] == "pending"

    # 2. Stage 1 実行
    job_manager.update_job_stage(job_id, "stage1", "running", project_id=project_id)
    stage1_data = [{"id": "model1", "response": "response1"}]
    job_manager.update_job_stage(job_id, "stage1", "completed", data=stage1_data, project_id=project_id)

    # 3. Stage 2 実行
    job_manager.update_job_stage(job_id, "stage2", "running", project_id=project_id)
    stage2_data = [{"id": "model1", "ranking": "1. Response A"}]
    metadata = {"label_to_id": {"Response A": "model1"}}
    job_manager.update_job_stage(
        job_id, "stage2", "completed", data=stage2_data, metadata=metadata, project_id=project_id
    )

    # 4. Stage 3 実行
    job_manager.update_job_stage(job_id, "stage3", "running", project_id=project_id)
    stage3_data = {"response": "final response"}
    job_manager.update_job_stage(job_id, "stage3", "completed", data=stage3_data, project_id=project_id)

    # 5. ジョブ完了
    usage = {"total_tokens": 5000, "total_cost_usd": 0.05}
    final_job = job_manager.complete_job(job_id, usage, project_id)

    # 6. 最終検証
    assert final_job["status"] == "completed"
    assert final_job["progress"]["current_stage"] == "complete"
    assert final_job["progress"]["stage1"]["status"] == "completed"
    assert final_job["progress"]["stage2"]["status"] == "completed"
    assert final_job["progress"]["stage3"]["status"] == "completed"
    assert final_job["usage"] == usage

    # 7. ジョブを再取得して永続化を確認
    retrieved_job = job_manager.get_job(job_id, project_id)
    assert retrieved_job["status"] == "completed"
    assert retrieved_job["progress"]["stage1"]["data"] == stage1_data
    assert retrieved_job["progress"]["stage2"]["data"] == stage2_data
    assert retrieved_job["progress"]["stage3"]["data"] == stage3_data
