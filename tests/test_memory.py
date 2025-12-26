"""メモリシステムの単体テスト"""

import pytest
import tempfile
import shutil
import os
import sys

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import storage


class TestMemoryStorage:
    """メモリストレージの単体テスト"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """テスト用の一時ディレクトリを作成"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_dir = storage.DATA_BASE_DIR
        storage.DATA_BASE_DIR = self.temp_dir
        # バックエンドをリセット
        storage._backend = None
        yield
        # クリーンアップ
        storage.DATA_BASE_DIR = self.original_data_dir
        storage._backend = None
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_memory_empty(self):
        """空のメモリを取得"""
        memory = storage.get_memory("test_project")
        assert memory["version"] == 1
        assert memory["entries"] == []
        assert "created_at" in memory
        assert "updated_at" in memory

    def test_add_memory_entry(self):
        """メモリエントリを追加"""
        entry = {
            "category": "personal",
            "key": "name",
            "value": "田中太郎"
        }
        result = storage.add_memory_entry(entry, "test_project")

        assert "id" in result
        assert result["id"].startswith("mem_")
        assert result["category"] == "personal"
        assert result["key"] == "name"
        assert result["value"] == "田中太郎"
        assert "extracted_at" in result

        # 保存されたか確認
        memory = storage.get_memory("test_project")
        assert len(memory["entries"]) == 1
        assert memory["entries"][0]["key"] == "name"

    def test_add_multiple_entries(self):
        """複数のメモリエントリを追加"""
        entries = [
            {"category": "personal", "key": "name", "value": "田中太郎"},
            {"category": "preference", "key": "style", "value": "詳細な説明"},
            {"category": "goal", "key": "project", "value": "React開発"},
        ]
        for entry in entries:
            storage.add_memory_entry(entry, "test_project")

        memory = storage.get_memory("test_project")
        assert len(memory["entries"]) == 3

    def test_update_memory_entry(self):
        """メモリエントリを更新"""
        entry = {"category": "personal", "key": "name", "value": "田中太郎"}
        result = storage.add_memory_entry(entry, "test_project")
        memory_id = result["id"]

        # 更新
        updated = storage.update_memory_entry(
            memory_id,
            {"value": "山田花子"},
            "test_project"
        )

        assert updated is not None
        assert updated["value"] == "山田花子"
        assert updated["key"] == "name"  # 変更していない項目は保持

        # 存在しないIDの更新
        result = storage.update_memory_entry("nonexistent", {"value": "test"}, "test_project")
        assert result is None

    def test_delete_memory_entry(self):
        """メモリエントリを削除"""
        entry = {"category": "personal", "key": "name", "value": "田中太郎"}
        result = storage.add_memory_entry(entry, "test_project")
        memory_id = result["id"]

        # 削除
        deleted = storage.delete_memory_entry(memory_id, "test_project")
        assert deleted is True

        # 確認
        memory = storage.get_memory("test_project")
        assert len(memory["entries"]) == 0

        # 存在しないIDの削除
        deleted = storage.delete_memory_entry("nonexistent", "test_project")
        assert deleted is False

    def test_clear_memory(self):
        """全メモリを削除"""
        entries = [
            {"category": "personal", "key": "name", "value": "田中太郎"},
            {"category": "preference", "key": "style", "value": "詳細な説明"},
        ]
        for entry in entries:
            storage.add_memory_entry(entry, "test_project")

        # クリア
        storage.clear_memory("test_project")

        # 確認
        memory = storage.get_memory("test_project")
        assert len(memory["entries"]) == 0


class TestSummaryStorage:
    """サマリーストレージの単体テスト"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """テスト用の一時ディレクトリを作成"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_dir = storage.DATA_BASE_DIR
        storage.DATA_BASE_DIR = self.temp_dir
        storage._backend = None
        yield
        storage.DATA_BASE_DIR = self.original_data_dir
        storage._backend = None
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_summaries_empty(self):
        """空のサマリーを取得"""
        summaries = storage.get_summaries("test_project")
        assert summaries["version"] == 1
        assert summaries["max_entries"] == 15
        assert summaries["entries"] == []

    def test_add_summary(self):
        """サマリーを追加"""
        summary = {
            "conversation_id": "conv_123",
            "title": "テスト会話",
            "summary": "これはテストの会話です",
            "key_topics": ["テスト", "API"],
            "user_intent": "テスト実行",
            "outcome": "成功",
            "message_count": 5,
            "created_at": "2025-12-27T10:00:00Z"
        }
        storage.add_summary(summary, "test_project")

        summaries = storage.get_summaries("test_project")
        assert len(summaries["entries"]) == 1
        assert summaries["entries"][0]["conversation_id"] == "conv_123"
        assert "summarized_at" in summaries["entries"][0]

    def test_summary_rotation(self):
        """サマリーのローテーション（最大15件）"""
        # 20件追加
        for i in range(20):
            summary = {
                "conversation_id": f"conv_{i:03d}",
                "title": f"会話 {i}",
                "summary": f"サマリー {i}",
                "key_topics": [],
                "user_intent": "",
                "outcome": "",
                "message_count": 1,
                "created_at": f"2025-12-27T{i:02d}:00:00Z"
            }
            storage.add_summary(summary, "test_project", max_entries=15)

        summaries = storage.get_summaries("test_project")
        # 15件に制限される
        assert len(summaries["entries"]) == 15
        # 新しいものが先頭（conv_019が最新）
        assert summaries["entries"][0]["conversation_id"] == "conv_019"
        # 古いもの（conv_004以前）は削除されている
        ids = [s["conversation_id"] for s in summaries["entries"]]
        assert "conv_004" not in ids

    def test_delete_summary(self):
        """特定のサマリーを削除"""
        for i in range(3):
            storage.add_summary({
                "conversation_id": f"conv_{i}",
                "title": f"会話 {i}",
                "summary": "",
                "key_topics": [],
                "user_intent": "",
                "outcome": "",
                "message_count": 1,
                "created_at": "2025-12-27T10:00:00Z"
            }, "test_project")

        # conv_1を削除
        deleted = storage.delete_summary("conv_1", "test_project")
        assert deleted is True

        summaries = storage.get_summaries("test_project")
        assert len(summaries["entries"]) == 2
        ids = [s["conversation_id"] for s in summaries["entries"]]
        assert "conv_1" not in ids

        # 存在しないIDの削除
        deleted = storage.delete_summary("nonexistent", "test_project")
        assert deleted is False

    def test_clear_summaries(self):
        """全サマリーを削除"""
        for i in range(5):
            storage.add_summary({
                "conversation_id": f"conv_{i}",
                "title": f"会話 {i}",
                "summary": "",
                "key_topics": [],
                "user_intent": "",
                "outcome": "",
                "message_count": 1,
                "created_at": "2025-12-27T10:00:00Z"
            }, "test_project")

        storage.clear_summaries("test_project")

        summaries = storage.get_summaries("test_project")
        assert len(summaries["entries"]) == 0


class TestProjectIsolation:
    """プロジェクト間のデータ隔離テスト"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_dir = storage.DATA_BASE_DIR
        storage.DATA_BASE_DIR = self.temp_dir
        storage._backend = None
        yield
        storage.DATA_BASE_DIR = self.original_data_dir
        storage._backend = None
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_memory_isolation(self):
        """異なるプロジェクトのメモリは分離される"""
        storage.add_memory_entry(
            {"category": "personal", "key": "name", "value": "Project A User"},
            "project_a"
        )
        storage.add_memory_entry(
            {"category": "personal", "key": "name", "value": "Project B User"},
            "project_b"
        )

        memory_a = storage.get_memory("project_a")
        memory_b = storage.get_memory("project_b")

        assert len(memory_a["entries"]) == 1
        assert len(memory_b["entries"]) == 1
        assert memory_a["entries"][0]["value"] == "Project A User"
        assert memory_b["entries"][0]["value"] == "Project B User"

    def test_summary_isolation(self):
        """異なるプロジェクトのサマリーは分離される"""
        storage.add_summary({
            "conversation_id": "conv_a",
            "title": "Project A Conv",
            "summary": "",
            "key_topics": [],
            "user_intent": "",
            "outcome": "",
            "message_count": 1,
            "created_at": "2025-12-27T10:00:00Z"
        }, "project_a")

        storage.add_summary({
            "conversation_id": "conv_b",
            "title": "Project B Conv",
            "summary": "",
            "key_topics": [],
            "user_intent": "",
            "outcome": "",
            "message_count": 1,
            "created_at": "2025-12-27T10:00:00Z"
        }, "project_b")

        summaries_a = storage.get_summaries("project_a")
        summaries_b = storage.get_summaries("project_b")

        assert len(summaries_a["entries"]) == 1
        assert len(summaries_b["entries"]) == 1
        assert summaries_a["entries"][0]["title"] == "Project A Conv"
        assert summaries_b["entries"][0]["title"] == "Project B Conv"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
