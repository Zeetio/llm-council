"""メモリシステムのPydanticモデル定義

4レイヤーメモリシステム:
1. セッションメタデータ（短期）- デバイス、OS、タイムゾーン等
2. ユーザーメモリ（長期）- 名前、好み、目標等
3. 会話サマリー（中期）- 最近15件の会話要約
4. 現在の会話ログ（既存機能）
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum
import uuid


class MemoryCategory(str, Enum):
    """メモリのカテゴリ"""
    PERSONAL = "personal"      # 名前、職業、所属など
    PREFERENCE = "preference"  # 好みのスタイル、形式、言語など
    GOAL = "goal"              # 目標、プロジェクト、学習中のこと
    SKILL = "skill"            # スキルレベル、専門分野
    CONTEXT = "context"        # 継続的な文脈（進行中の作業など）


class MemoryEntry(BaseModel):
    """ユーザーメモリの個別エントリ"""
    id: str = Field(default_factory=lambda: f"mem_{uuid.uuid4().hex[:12]}")
    category: MemoryCategory
    key: str                   # 短い識別子（例: "name", "preferred_language"）
    value: str                 # 詳細な内容
    confidence: float = 1.0    # 確信度 (0.0-1.0)
    source_conversation_id: Optional[str] = None  # 抽出元の会話ID
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    last_confirmed_at: Optional[datetime] = None  # 最後に確認された日時


class MemoryCreateRequest(BaseModel):
    """メモリ作成リクエスト"""
    category: MemoryCategory
    key: str
    value: str


class MemoryUpdateRequest(BaseModel):
    """メモリ更新リクエスト"""
    key: Optional[str] = None
    value: Optional[str] = None
    category: Optional[MemoryCategory] = None


class UserMemory(BaseModel):
    """プロジェクト単位のユーザーメモリ全体"""
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    entries: List[MemoryEntry] = []


class ConversationSummary(BaseModel):
    """会話サマリー"""
    conversation_id: str
    title: str
    summary: str                    # 2-3文の要約
    key_topics: List[str] = []      # 主要トピック（3-5個）
    user_intent: str = ""           # ユーザーの目的や意図
    outcome: str = ""               # 会話の結果や成果
    message_count: int = 0
    created_at: datetime            # 元の会話の作成日時
    summarized_at: datetime = Field(default_factory=datetime.utcnow)


class ConversationSummaries(BaseModel):
    """プロジェクト単位の会話サマリー全体"""
    version: int = 1
    max_entries: int = 15           # 最大保持数
    entries: List[ConversationSummary] = []


class SessionMetadata(BaseModel):
    """セッションメタデータ（非永続）"""
    device: Optional[str] = None    # "Desktop" / "Mobile"
    os: Optional[str] = None        # "Windows 11" / "macOS"
    browser: Optional[str] = None   # "Chrome 120"
    timezone: Optional[str] = None  # "Asia/Tokyo"
    language: Optional[str] = None  # "ja-JP"
    screen_resolution: Optional[str] = None  # "1920x1080"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MemorySettings(BaseModel):
    """メモリシステムの設定"""
    enabled: bool = True
    utility_model: str = "deepseek/deepseek-r1-distill-qwen-8b"  # 安価なモデル
    auto_extract: bool = True       # 自動メモリ抽出
    max_summaries: int = 15         # 保持するサマリー数
    max_history_messages: int = 10  # LLMに送る会話履歴の最大数


# デフォルトのメモリ設定
DEFAULT_MEMORY_SETTINGS = MemorySettings()
